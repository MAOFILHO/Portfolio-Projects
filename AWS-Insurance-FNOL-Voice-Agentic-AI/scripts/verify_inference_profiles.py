"""Assert that the application inference profiles preserved cross-region routing.

`ADR-016`. Constraint 17 requires Bedrock invocation through US cross-region inference profiles. Wrapping
a system-defined `us.*` profile in an *application* profile is what makes the spend attributable to a cost
allocation tag, and it is the only mechanism AWS offers for that. The question this script answers is the
one Marco attached to approving it:

    "verify the wrapped profile actually routes cross-region rather than pinning to one region. That is
    the property 17 exists to protect, and 'application profile wrapping a system profile' is exactly the
    shape where an assumption could hold in the docs and not in the response metadata."

So the check reads `GetInferenceProfile` from the live API rather than Terraform state or the plan.
Terraform's own `models` attribute would answer the same question, but it answers it from a value the
provider stored at apply time; this reads what Bedrock says now. The difference matters for exactly the
same reason `live_guardrail_config_sha()` exists alongside `config_fingerprint()` in Phase 7 -- one hashes
the artifact, the other reads the outcome.

Exits non-zero on any collapse, so it is usable as a CI gate. Free: `GetInferenceProfile` is a control
plane read and makes no model call.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import boto3

from fnol_voice_agent.aws.mock_guard import assert_real_aws_allowed
from fnol_voice_agent.config.settings import DEFAULT_REGION

STACK_DIR = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "stacks" / "inference"

# What each profile must report. The three cross-region wrappers inherit us-east-1 / us-east-2 /
# us-west-2 from the `us.*` profile they copy from. `embedding` wraps a plain foundation model because
# `amazon.titan-embed-text-v2:0` has no `us.*` profile in existence -- so 1 region is correct for it and
# would be a defect for any of the others. Encoding the expectation per profile, rather than asserting
# ">= 1 region" across the board, is the difference between a check and a formality.
EXPECTED_REGION_COUNT = {
    "router": 3,
    "generation": 3,
    "judge": 3,
    "embedding": 1,
}


def _terraform_output() -> dict[str, str]:
    """Profile ARNs from the stack. Fails loudly if the stack has not been applied."""
    result = subprocess.run(
        ["terraform", "output", "-json", "model_ids"],
        cwd=STACK_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"verify-inference: no terraform output in {STACK_DIR}.\n"
            f"Run `terraform apply` there first.\n{result.stderr.strip()}"
        )
    parsed: dict[str, str] = json.loads(result.stdout)
    return parsed


def main() -> int:
    arns = _terraform_output()
    # `boto3.client("bedrock", ...)` is the control-plane client -- not one of ADR-013's three guarded
    # wrapper classes (BotoBedrockConverseClient / BedrockEmbedder / BedrockGuardrailClient), so it gets
    # no guard by construction. This call is that guard, added directly at the point of construction
    # (found missing 2026-08-15, CF4 correction -- RESULTS.md §12.4/§12.6).
    assert_real_aws_allowed("bedrock (control plane) / verify_inference_profiles.GetInferenceProfile")
    client = boto3.client("bedrock", region_name=DEFAULT_REGION)

    failures: list[str] = []
    print(f"verify-inference: reading GetInferenceProfile in {DEFAULT_REGION}\n")

    for name in sorted(EXPECTED_REGION_COUNT):
        expected = EXPECTED_REGION_COUNT[name]
        arn = arns.get(name)
        if arn is None:
            failures.append(f"{name}: absent from terraform output")
            continue

        response = client.get_inference_profile(inferenceProfileIdentifier=arn)
        status = response.get("status")
        profile_type = response.get("type")
        regions = sorted({str(m["modelArn"]).split(":")[3] for m in response.get("models", [])})

        ok = len(regions) == expected and status == "ACTIVE" and profile_type == "APPLICATION"
        print(
            f"  {'ok  ' if ok else 'FAIL'} {name:11} {profile_type:12} {status:8} "
            f"{len(regions)}/{expected} regions  {','.join(regions)}"
        )
        if len(regions) != expected:
            failures.append(
                f"{name}: {len(regions)} region(s) {regions}, expected {expected}. "
                "The application profile did not inherit the wrapped profile's region set -- "
                "constraint 17's routing property is lost, not merely renamed."
            )
        if status != "ACTIVE":
            failures.append(f"{name}: status {status}, not ACTIVE")
        if profile_type != "APPLICATION":
            failures.append(f"{name}: type {profile_type}, not APPLICATION")

    if failures:
        print("\nverify-inference: FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nverify-inference: all profiles ACTIVE and routing as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
