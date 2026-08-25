"""Phase 11 Stage B1 / Stage C `OI2` -- the single live invoke, three separately-asserted claims.

Marco's instruction (2026-08-16): one real invoke may serve both `OI2`'s run 2 (proof the PII log
filter is installed in the deployed Lambda's own runtime) and Stage B1's panel-liveness proof (a real
guardrail intervention, `blocked`/`masked`/`units` reflecting it) -- but the two claims, plus a third
(units compared against Stage 7 Stage 8's recorded values), must be asserted and reported independently.
A single pass/fail that collapsed them would say nothing about which one actually failed.

WHY `CheckClaimStatus` WITH A REAL CLAIM NUMBER
    `check_claim_status.py`'s response template is `f"Your claim {claim.claim_number} is currently
    {claim.status}."` -- a real corpus claim number (`CLM-2608-00042-4`, `data/synthetic/claims/claims.json`,
    policy `PY4821`, status `RepairInProgress`) substituted in verbatim reaches `guardrails_output_check`,
    which calls the real Bedrock guardrail on `OUTPUT`. `guardrails/client.py`'s own module comment records
    that a `CLM-####-#####-#`-shaped string in OUTPUT text has been live-verified to trigger `ANONYMIZE`
    (mask) since Phase 7 Stage 8's v3 guardrail -- this reuses that same known-to-fire trigger rather than
    guessing a new one.

    The event is hand-built (same technique `verify_lambda_execution.py`'s own event #9 uses for `D79`):
    `sessionState.intent.slots` carries `claim_number` directly. This is a direct `lambda:Invoke`, not a
    real Lex `RecognizeText` call, so nothing here depends on Lex's own NLU already having split a combined
    `claim_or_policy_number` slot -- `_lex_interpreted_slots` (`api/lex_codehook.py`) copies whatever slot
    keys the event carries verbatim into `filled_slots`, and `check_claim_status.py` reads `filled_slots
    ["claim_number"]` directly, so this event is genuine input to the real deployed code, not a bypass of it.

CLAIM (c)'S SCOPE, CORRECTED BEFORE THE CALL, NOT AFTER
    Checked against `RESULTS.md` before running this: Stage 8 recorded the guardrail's *action* outcomes
    live (masked/blocked/clean per probe) and one specific numeric figure -- `sensitiveInformationPolicyUnits:
    0` on INPUT, confirmed across three INPUT probes. It did **not** record a numeric OUTPUT-side `usage`
    snapshot for the masked-claim-number case anywhere on record (checked: no raw `usage` dict for that
    probe exists in `RESULTS.md`, `COSTS.md`, or `evals/`). So claim (c) below is two different things, kept
    separate rather than forced into one comparison: (i) a real re-check of the one INPUT figure Stage 8 DID
    record (`sensitiveInformationPolicyUnits: 0`) -- agreement or disagreement reported plainly; (ii) the
    OUTPUT-side units this call actually measures, reported as the **first** number of its kind on record,
    not a re-measurement of one that already existed.

COST, ESTIMATED BEFORE RUNNING, PER THIS PROJECT'S OWN DISCIPLINE
    One `lambda:Invoke` (always-free tier) triggering: 1 `ApplyGuardrail` INPUT call (~2 units,
    ~$0.0003), 1 Nova Micro router call (a fraction of a cent), 1 `ApplyGuardrail` OUTPUT call (~2 units,
    ~$0.0003). Estimated **~$0.0007 total** -- same shape and order of magnitude as one event in
    `verify_lambda_execution.py`'s own matrix.
"""

from __future__ import annotations

import base64
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parent))
# mypy can't see this sibling-module import (no scripts/__init__.py, resolved at runtime via the
# sys.path.insert above).
from verify_lambda_execution import (  # type: ignore[import-not-found]  # noqa: E402
    _event,
    _slot,
    terraform_outputs,
)

REGION = "us-west-2"
_REAL_CLAIM_NUMBER = (
    "CLM-2608-00042-4"  # data/synthetic/claims/claims.json -- policy PY4821, RepairInProgress
)
_ESTIMATED_COST_USD = 0.0007


def main() -> int:
    print(f"=== Stage B1 / OI2 live invoke: estimated cost ~${_ESTIMATED_COST_USD} ===")

    outputs = terraform_outputs()
    function_name = str(outputs["codehook_function_name"])
    log_group = f"/aws/lambda/{function_name}"

    lambda_client = boto3.client("lambda", region_name=REGION)
    logs_client = boto3.client("logs", region_name=REGION)

    event = _event(
        intent_name="CheckClaimStatus",
        transcript="what's the status of my claim",
        slots={"claim_number": _slot(_REAL_CLAIM_NUMBER)},
    )

    call_started = datetime.now(UTC)
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=json.dumps(event).encode("utf-8"),
    )
    raw_payload = response["Payload"].read()
    function_error = response.get("FunctionError")
    tail_log = base64.b64decode(response.get("LogResult", "")).decode("utf-8", errors="replace")

    if function_error:
        print(f"FAIL: FunctionError={function_error!r} payload={raw_payload!r}")
        return 1

    payload = json.loads(raw_payload)
    message = ((payload.get("messages") or [{}])[0]).get("content", "")
    print(f"\nResponse text: {message!r}")

    # -----------------------------------------------------------------------------------------------
    # Claim (b): a forced intervention actually happened, read from THIS invoke's own log tail
    # (`LogType=Tail` -- unambiguous, no separate CloudWatch query needed to attribute the line to this
    # specific call).
    # -----------------------------------------------------------------------------------------------
    print("\n--- Claim (b): forced guardrail intervention, this invoke's own log tail ---")
    usage_lines_tail = [line for line in tail_log.splitlines() if "guardrail_usage" in line]
    if not usage_lines_tail:
        print("FAIL: no guardrail_usage line in this invoke's log tail")
        return 1
    for line in usage_lines_tail:
        print(f"  {line.strip()}")
    output_lines = [
        json.loads(line.split("guardrail_usage ", 1)[1])
        for line in usage_lines_tail
        if '"source": "OUTPUT"' in line
    ]
    if not output_lines:
        print("FAIL: no OUTPUT-side guardrail_usage line found")
        return 1
    output_usage = output_lines[-1]
    masked_claim_ok = _REAL_CLAIM_NUMBER not in message
    print(f"  claim number absent from spoken response (masked): {masked_claim_ok}")
    print(f"  OUTPUT guardrail_usage payload: {output_usage}")
    if not (output_usage["masked"] is True and not output_usage["blocked"]):
        print(
            f"FAIL: expected a real mask (masked=True, blocked=False), got "
            f"masked={output_usage['masked']!r} blocked={output_usage['blocked']!r} -- "
            f"the guardrail may not have fired the way Stage 8 recorded it firing"
        )
        return 1
    print("  PASS: real forced intervention confirmed (masked=True, blocked=False)")

    input_lines = [
        json.loads(line.split("guardrail_usage ", 1)[1])
        for line in usage_lines_tail
        if '"source": "INPUT"' in line
    ]
    input_usage = input_lines[-1] if input_lines else None

    # -----------------------------------------------------------------------------------------------
    # Claim (a): `OI2` -- filter-install self-report, read from the real CloudWatch log stream (not the
    # tail -- the install line only logs on a COLD start, which may have already happened during
    # `make verify-lambda-execution`'s own 9 invokes moments earlier, not necessarily during this call).
    # -----------------------------------------------------------------------------------------------
    print("\n--- Claim (a): pii_log_filter_installed, real CloudWatch Logs, since this deploy ---")
    start_ms = int((call_started - timedelta(minutes=15)).timestamp() * 1000)
    time.sleep(
        5
    )  # CloudWatch Logs ingestion lag -- real, not instant even for a just-completed invoke
    install_lines: list[str] = []
    for _ in range(6):
        resp = logs_client.filter_log_events(
            logGroupName=log_group,
            startTime=start_ms,
            filterPattern='"pii_log_filter_installed"',
        )
        install_lines = [e["message"].strip() for e in resp.get("events", [])]
        if install_lines:
            break
        time.sleep(5)
    if not install_lines:
        print("FAIL: no pii_log_filter_installed line found in CloudWatch Logs since this deploy")
        return 1
    for line in install_lines:
        print(f"  {line}")
    nonzero = [line for line in install_lines if "handlers=0" not in line]
    if not nonzero:
        print(
            "FAIL: every pii_log_filter_installed line since this deploy reads handlers=0 -- "
            "the filter never attached to a real handler on any cold start observed"
        )
        return 1
    print(
        f"  PASS: {len(nonzero)} cold-start attachment(s) found, e.g. {nonzero[0]!r} -- OI2 closed"
    )

    # -----------------------------------------------------------------------------------------------
    # Claim (c): units vs. Stage 8. INPUT sensitiveInformationPolicyUnits is the one Stage 8 numeric
    # figure on record (0, confirmed live). OUTPUT has no Stage 8 numeric figure to compare against --
    # reported as the first number of its kind, not a re-measurement, per this script's own docstring.
    # -----------------------------------------------------------------------------------------------
    print("\n--- Claim (c): units vs. Stage 8's recorded values ---")
    if input_usage is not None:
        siu = input_usage["units"].get("sensitiveInformationPolicyUnits")
        print(f"  INPUT sensitiveInformationPolicyUnits this call: {siu!r}")
        print("  Stage 8 recorded: 0 (RESULTS.md, three live INPUT probes)")
        print("  AGREE" if siu == 0 else "  DISAGREE -- this is a finding, not a rounding error")
    else:
        print("  No INPUT guardrail_usage line captured this call -- cannot compare")
    print(f"  OUTPUT units this call: {output_usage['units']}")
    print(
        "  Stage 8 recorded no numeric OUTPUT usage figure for the masked-claim-number case -- "
        "this is the FIRST number of its kind on record, not a re-measurement."
    )

    print("\n=== Stage B1 / OI2 live invoke: all three claims asserted above ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
