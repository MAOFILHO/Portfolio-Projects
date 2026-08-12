"""L2's false-escalation rate — the measurement that corrected the layered-design conclusion.

**This script is committed retroactively, in Phase 7 Stage 0, and that is itself the finding.**

It produced `evals/baselines/l2_precision_20260812.json` — the 0.529 that reversed Phase 6's headline
claim — while living in a scratchpad directory outside the repository. A clean checkout could read the
number but not reproduce it, and the population the rate was computed over existed nowhere in version
control. It was recovered from the session transcript, which is luck rather than process.

The rule that follows: **a number that appears in `RESULTS.md` must be reproducible from a clean
checkout.** Committed here exactly as it ran, so `0.529` remains reproducible rather than merely recorded.

## The population, and its honest weakness

34 cases that must not escalate:

* **17** — every negative in the independent held-out set (rule-based, complete).
* **9** — every golden conversation labelled KABCO B/C/O (rule-based, complete).
* **8** — ordinary non-safety opening turns, **hand-picked by ID** (`_ORDINARY_OPENINGS` below).

That last group is a named selection, not a rule, and the rate depends on which eight were chosen.
`0.529` is therefore a real measurement over a partly-hand-selected denominator. Phase 7 does not
retrofit a rule onto it — changing the population would change the number and break comparability with
the committed baseline — but any *new* false-escalation population must be rule-based, and the Phase 7
tuning set is built that way.

`ADR-013`: no `mock_aws()` anywhere in this file. Every call here is a real, billed Bedrock call.

**One change since it ran** (Phase 7 Stage 2): the body is wrapped in a declared `verification_run`.
This script reads the independent set *and* constructs a real Bedrock client, which is exactly the pair
`evals/holdout_ledger.py` now guards, so without the declaration it would raise. The measurement itself —
population, order, call, scoring — is untouched, because changing it would break comparability with the
committed `0.529`. The declaration costs a ledger entry, which is the intended cost of measuring against
this set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient, classify_turn

from evals.holdout import HoldoutKind, load_holdout
from evals.holdout_ledger import VerificationRun, verification_run
from evals.metrics import BinaryClassificationCounts
from evals.schema import load_golden_set
from evals.tier_b import CostLog, LoggingCaller

# Hand-picked, not derived. See the module docstring — this is the part of the denominator that a
# reader is entitled to argue with.
_ORDINARY_OPENINGS = (
    "fac-001",
    "fac-002",
    "fac-003",
    "ccs-001",
    "cq-001",
    "uci-001",
    "rte-001",
    "oos-004",
)

_MUST_NOT_ESCALATE_KABCO = ("B", "C", "O")


def build_population() -> list[tuple[str, str]]:
    """The 34 must-not-escalate cases, in the order the original run used."""
    cases: list[tuple[str, str]] = []
    for p in load_holdout(HoldoutKind.INDEPENDENT):
        if not p.should_escalate:
            cases.append((f"indep[{p.kabco}]", p.text))
    golden = load_golden_set()
    for c in golden:
        if c.kabco is not None and str(c.kabco) in _MUST_NOT_ESCALATE_KABCO:
            cases.append((c.id, c.turns[0].caller))
    for cid in _ORDINARY_OPENINGS:
        c = next(x for x in golden if x.id == cid)
        cases.append((cid, c.turns[0].caller))
    return cases


def main(out_path: Path) -> int:
    with verification_run(
        reason="re-run of the Phase 6 L2 false-escalation measurement (scripts/measure_l2_precision.py)",
        samples_per_item=1,
    ) as run:
        return _measure(out_path, run)


def _measure(out_path: Path, run: VerificationRun) -> int:
    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    cases = build_population()
    l1c = BinaryClassificationCounts()
    l2c = BinaryClassificationCounts()
    unionc = BinaryClassificationCounts()
    fires: list[list[str]] = []

    print(f"=== L2 false-escalation over {len(cases)} cases that must NOT escalate ===")
    for cid, text in cases:
        a1 = detect_safety_trigger(text)[0]
        a2 = bool(
            classify_turn(
                [{"role": "user", "content": [{"text": text}]}], caller=caller
            ).safety_flag
        )
        l1c = l1c.observe(expected=False, actual=a1)
        l2c = l2c.observe(expected=False, actual=a2)
        unionc = unionc.observe(expected=False, actual=(a1 or a2))
        if a2:
            fires.append([cid, text])
            print(f"  L2 FIRES  {cid:16} L1={a1}  {text[:78]!r}")

    print(f"\n  L1 false-escalation:    {l1c.false_escalation_rate}")
    print(f"  L2 false-escalation:    {l2c.false_escalation_rate}")
    print(
        f"  UNION false-escalation: {unionc.false_escalation_rate}   <- what the caller experiences"
    )
    print(f"\n=== Cost: {log.summary()} ===")

    payload: dict[str, Any] = {
        "cases": len(cases),
        "l1_fe": l1c.false_escalation_rate.value,
        "l2_fe": l2c.false_escalation_rate.value,
        "union_fe": unionc.false_escalation_rate.value,
        "l2_fires_on": fires,
        "cost": log.summary(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out_path}")
    run.record(
        cases=len(cases),
        l1_fe=l1c.false_escalation_rate.value,
        l2_fe=l2c.false_escalation_rate.value,
        union_fe=unionc.false_escalation_rate.value,
    )
    run.note("Population includes 8 hand-picked ordinary openings -- see the module docstring.")
    return 0


if __name__ == "__main__":
    import sys

    default = Path("evals/baselines") / "l2_precision_rerun.json"
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else default))
