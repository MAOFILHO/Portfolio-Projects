"""Phase 7 Stage 0 — is `D25` literally true, or only plausible from the aggregate numbers?

`D25` claims intent macro-F1 0.623, out-of-scope detection 0.200 and false-escalation 0.529 are **one
finding**: the merged `classify_turn` call emits `safety_flag` and `intent` as one structured object, so
the recall bias on `safety_flag` propagates into `intent`.

That is a mechanism claim, and a mechanism claim is testable at the item level. Marco's condition, set at
Phase 7 approval: *"If the ten misclassifications are not the same turns as the false escalations, tell me
before building rungs."*

## Two passes

* **`--offline` (default, $0.00)** — cross-tabulates the two committed Phase 6 baselines. Answers the
  question for every case both runs happened to cover, and reports precisely which cases they did not.
* **`--live` (real Bedrock calls, ~$0.003)** — closes the gap.

## Why a gap exists at all, which is a finding in its own right

`classify_turn` returns `safety_flag` **and** `intent` in a single object. Phase 6's Tier B intent run
called it on all 73 labelled first turns and stored only `.intent`, discarding the `safety_flag` that came
back in the same response. The false-escalation run then paid for 34 fresh calls to recover part of what
had already been returned and thrown away.

**The harness measured half of a merged call's output and discarded the half that would have shown the
merge was the problem.** Nothing was wrong with either measurement on its own; the coupling was invisible
because no artifact ever held both fields for the same turn. `--live` re-runs the 73 turns storing the
whole `TurnClassification`, which is what should have been stored the first time.

`ADR-013`: no `mock_aws()` in this file. `--live` makes real, billed calls.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from fnol_voice_agent.models.enums import Intent

from evals.schema import load_golden_set

BASELINES = Path("evals/baselines")
JOINT_OUT = BASELINES / "stage0_joint_20260812.json"

_INJURY = Intent.INJURY_ESCALATION.value


# --- reading what Phase 6 committed ------------------------------------------------------------------


def confusions_to_injury() -> list[str]:
    """Golden IDs the merged call classified as `InjuryEscalation` when it should not have."""
    data = json.loads((BASELINES / "tier_b_20260812.json").read_text())
    out = []
    for line in data["intent"]["confusions"]:
        case_id, _, verdict = line.partition(": ")
        if verdict.endswith(f"got {_INJURY}"):
            out.append(case_id)
    return out


def false_escalations() -> tuple[list[str], list[str]]:
    """(golden IDs where L2's safety_flag fired, all golden IDs in the false-escalation population)."""
    data = json.loads((BASELINES / "l2_precision_20260812.json").read_text())
    fired = [cid for cid, _text in data["l2_fires_on"] if not cid.startswith("indep[")]

    import scripts.measure_l2_precision as m  # the population, now reproducible

    population = [cid for cid, _text in m.build_population() if not cid.startswith("indep[")]
    return fired, population


# --- statistics --------------------------------------------------------------------------------------


def fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-tailed Fisher exact p for a 2x2 table, testing association in the observed direction.

    Hand-rolled rather than pulling in scipy: one p-value does not justify a 40 MB dependency in a
    project that justifies every dependency in one line.
    """
    n = a + b + c + d
    row1, col1 = a + b, a + c

    def hyper(k: int) -> float:
        return math.comb(row1, k) * math.comb(n - row1, col1 - k) / math.comb(n, col1)

    lo = max(0, col1 - (n - row1))
    hi = min(row1, col1)
    return sum(hyper(k) for k in range(a, hi + 1) if lo <= k <= hi)


# --- the analysis ------------------------------------------------------------------------------------


def analyse(joint: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    injury_intents = confusions_to_injury()
    fired, fe_population = false_escalations()

    both_measured = sorted(set(fe_population))
    table: dict[str, list[str]] = {
        "flag_and_injury": [],
        "flag_only": [],
        "injury_only": [],
        "neither": [],
    }
    for cid in both_measured:
        f, i = cid in fired, cid in injury_intents
        key = (
            "flag_and_injury"
            if f and i
            else "flag_only" if f else "injury_only" if i else "neither"
        )
        table[key].append(cid)

    result: dict[str, Any] = {
        "source": "committed Phase 6 baselines only",
        "intent_eq_InjuryEscalation": injury_intents,
        "safety_flag_fired": fired,
        "jointly_measured": both_measured,
        "unmeasured_for_safety_flag": sorted(set(injury_intents) - set(fe_population)),
        "contingency": {k: sorted(v) for k, v in table.items()},
    }

    a, b = len(table["flag_and_injury"]), len(table["flag_only"])
    c, d = len(table["injury_only"]), len(table["neither"])
    result["counts"] = {
        "a_flag_and_injury": a,
        "b_flag_only": b,
        "c_injury_only": c,
        "d_neither": d,
    }
    result["fisher_p_one_tailed"] = round(fisher_exact_greater(a, b, c, d), 6)

    if joint is not None:
        rows = [(cid, v["safety_flag"], v["intent"]) for cid, v in joint.items()]
        ja = sum(1 for _, f, i in rows if f and i == _INJURY)
        jb = sum(1 for _, f, i in rows if f and i != _INJURY)
        jc = sum(1 for _, f, i in rows if not f and i == _INJURY)
        jd = sum(1 for _, f, i in rows if not f and i != _INJURY)
        result["joint_full_golden"] = {
            "n": len(rows),
            "a_flag_and_injury": ja,
            "b_flag_only": jb,
            "c_injury_without_flag": jc,
            "d_neither": jd,
            "fisher_p_one_tailed": round(fisher_exact_greater(ja, jb, jc, jd), 8),
            "injury_intent_without_flag": sorted(
                cid for cid, f, i in rows if not f and i == _INJURY
            ),
            "flag_without_injury_intent": sorted(cid for cid, f, i in rows if f and i != _INJURY),
        }
    return result


def capture_joint() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Re-run the merged call on all labelled first turns, storing the WHOLE classification."""
    from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient, classify_turn

    from evals.tier_b import CostLog, LoggingCaller

    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    joint: dict[str, dict[str, Any]] = {}
    for conv in load_golden_set():
        expected = conv.turns[0].expect.intent or conv.intent
        if expected is None:
            continue
        text = conv.turns[0].caller
        cls = classify_turn([{"role": "user", "content": [{"text": text}]}], caller=caller)
        joint[conv.id] = {
            "text": text,
            "expected_intent": expected.value,
            "intent": cls.intent,
            "safety_flag": bool(cls.safety_flag),
            "intent_confidence": cls.intent_confidence,
        }
    return joint, log.summary()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Make real Bedrock calls to close the coverage gap (~$0.003).",
    )
    args = parser.parse_args(argv)

    joint = None
    if args.live:
        captured, cost = capture_joint()
        JOINT_OUT.write_text(json.dumps({"cost": cost, "turns": captured}, indent=2) + "\n")
        print(f"wrote {JOINT_OUT}  cost={cost}")
        joint = captured
    elif JOINT_OUT.exists():
        joint = json.loads(JOINT_OUT.read_text())["turns"]

    report = analyse(joint)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
