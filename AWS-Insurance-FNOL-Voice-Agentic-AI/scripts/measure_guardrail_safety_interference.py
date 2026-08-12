"""Does the input guardrail block or alter the utterances the safety detector exists to hear?

**The only guardrail measurement that touches the safety guarantee**, and Marco asked for it separately
from the red-team results for that reason:

> *"The LOW setting is a reasoned choice, not a measured one -- and if it blocks even one phrasing that L1
> or L2 would have caught, the guardrail has become a recall defect sitting upstream of the detector that
> C1 protects."*

## Why this can fail, structurally

`ADR-010` sequences L1 strictly before `ApplyGuardrail`, so a block cannot pre-empt L1. But **L2 runs
after** the input guardrail. A blocked turn never reaches the router, so a phrasing that only L2 catches --
which is 73% of indirect injury phrasing, and the entire reason the layered design exists -- would be lost
to a guardrail intervention with nothing downstream to recover it. Union recall would drop without any
detector changing behaviour.

That makes the input filter a **potential recall defect upstream of the guarantee**, which is why
`VIOLENCE` is set to `LOW` on input and every other content filter to `NONE`. This script measures whether
that reasoning held.

## Scoring

| Outcome | Reading |
|---|---|
| `blocked` on a must-escalate phrasing | **C1 breach.** The turn never reaches L2 |
| text **modified** on a must-escalate phrasing | Reported and inspected -- PII anonymisation is expected and harmless, but a modification that removes the injury signal would be a silent recall defect |
| `blocked`/modified on a must-not-escalate phrasing | Reported. Not a safety issue; a caller-experience one |

**This is a verification run against the independent held-out set**, so it declares itself and appends to
the ledger. Reading the set and constructing a real Bedrock client is exactly the pair
`evals/holdout_ledger.py` guards, and the guardrail client was wired into that guard in this same stage.

**The guardrail must not be tuned in response to this measurement** without spending another fingerprint
and saying so. `BUILD-PLAN.md` §2.3's rule -- one configuration, any number of samples -- applies to the
guardrail exactly as it applies to the router.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.guardrails.client import BedrockGuardrailClient

from evals.holdout import HoldoutKind, load_holdout
from evals.holdout_ledger import VerificationRun, verification_run


def measure(
    client: BedrockGuardrailClient,
    run: VerificationRun | None,
    *,
    kind: HoldoutKind = HoldoutKind.INDEPENDENT,
    version: str = "1",
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    blocked_must_escalate: list[str] = []
    modified_must_escalate: list[str] = []

    for phrasing in load_holdout(kind):
        result = client.apply_guardrail("INPUT", phrasing.text)
        # `ApplyGuardrail` returns an `outputs` array **only when it intervenes**. On a clean pass the
        # action is NONE and there is no output text at all, so comparing `output_text` to the input
        # reports every clean pass as "modified". The first version of this script did exactly that
        # and produced 16 phantom modifications -- caught by checking `raw_action` before believing
        # the count, which is the same lesson as RESULTS.md section 3.5: the artifact (a string
        # differing) was not the outcome (the guardrail changing something).
        intervened = result.raw_action == "GUARDRAIL_INTERVENED"
        modified = (
            intervened
            and not result.blocked
            and result.output_text.strip() != phrasing.text.strip()
        )
        items.append(
            {
                "text": phrasing.text,
                "kabco": phrasing.kabco.value,
                "should_escalate": phrasing.should_escalate,
                "l1_would_catch": detect_safety_trigger(phrasing.text)[0],
                "blocked": result.blocked,
                "modified": modified,
                "output_text": result.output_text if modified else None,
                "reasons": list(result.intervention_reasons),
                "action": result.raw_action,
            }
        )
        if phrasing.should_escalate:
            if result.blocked:
                blocked_must_escalate.append(phrasing.text)
            elif modified:
                modified_must_escalate.append(phrasing.text)

    positives = [i for i in items if i["should_escalate"]]
    negatives = [i for i in items if not i["should_escalate"]]
    summary = {
        "guardrail_version": version,
        "population": kind.value,
        "positives": len(positives),
        "negatives": len(negatives),
        "blocked_must_escalate": len(blocked_must_escalate),
        "modified_must_escalate": len(modified_must_escalate),
        "blocked_must_not_escalate": sum(1 for i in negatives if i["blocked"]),
        "modified_must_not_escalate": sum(1 for i in negatives if i["modified"]),
        # The subset that matters most: phrasings L1 does NOT catch, so L2 is the only remaining
        # detector -- and L2 sits downstream of this filter.
        "l2_only_positives": sum(1 for i in positives if not i["l1_would_catch"]),
        "l2_only_positives_blocked": sum(
            1 for i in positives if not i["l1_would_catch"] and i["blocked"]
        ),
        "c1_breach": bool(blocked_must_escalate),
        "blocked_must_escalate_texts": blocked_must_escalate,
        "modified_must_escalate_texts": modified_must_escalate,
    }
    if run is not None:
        run.record(**{k: v for k, v in summary.items() if not k.endswith("_texts")})
    return {"summary": summary, "items": items}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guardrail-id", required=True)
    parser.add_argument("--guardrail-version", default="1")
    parser.add_argument(
        "--set",
        dest="kind",
        default="independent",
        choices=["independent", "tuning"],
        help="tuning runs are unguarded and cost no ledger fingerprint -- that set exists to be spent",
    )
    parser.add_argument(
        "--out", type=Path, default=Path("evals/baselines/guardrail_safety_interference.json")
    )
    args = parser.parse_args()

    kind = HoldoutKind(args.kind)
    client_kwargs = {
        "guardrail_id": args.guardrail_id,
        "guardrail_version": args.guardrail_version,
    }
    if kind is HoldoutKind.TUNING:
        # No ledger entry: the tuning set exists to be spent, and guardrail iteration belongs against
        # it rather than against the one uncontaminated measure of the union.
        result = measure(
            BedrockGuardrailClient(**client_kwargs), None, kind=kind, version=args.guardrail_version
        )
    else:
        with verification_run(
            reason=(
                "Stage 5: does the input guardrail block or alter injury phrasings the safety "
                "detector must see? The input filter sits upstream of L2, so a block is a recall "
                "defect C1 cannot see."
            ),
            samples_per_item=1,
        ) as run:
            result = measure(
                BedrockGuardrailClient(**client_kwargs),
                run,
                kind=kind,
                version=args.guardrail_version,
            )

    s = result["summary"]
    print(f"=== Input guardrail v{args.guardrail_version} vs the {args.kind} set "
          f"({s['positives']} positives) ===")
    print(f"  blocked, must-escalate       {s['blocked_must_escalate']}")
    print(f"  modified, must-escalate      {s['modified_must_escalate']}")
    print(
        f"  of which L2-only phrasings   {s['l2_only_positives_blocked']} blocked "
        f"of {s['l2_only_positives']}"
    )
    print(f"  blocked, must-NOT-escalate   {s['blocked_must_not_escalate']}")
    print(f"  modified, must-NOT-escalate  {s['modified_must_not_escalate']}")
    for text in s["blocked_must_escalate_texts"]:
        print(f"    *** C1 BREACH, BLOCKED: {text!r}")
    for text in s["modified_must_escalate_texts"]:
        print(f"    modified: {text!r}")
    if not s["c1_breach"]:
        print(
            "\n  No must-escalate phrasing was blocked. The LOW setting is now measured, not reasoned."
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
