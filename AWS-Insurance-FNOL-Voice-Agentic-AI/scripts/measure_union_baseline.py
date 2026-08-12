"""The k-sampled union-recall baseline — the number `C1` actually attaches to.

`BUILD-PLAN.md` §2.4, Stage 2's closing step. Marco, at Phase 7 approval: *"if the merged baseline does not
hold 1.000 under repetition, report it as a correction to Phase 6 in RESULTS.md, not as a footnote in Phase
7. An n=1 number published as a guarantee is the same class of error as the recall-without-precision
conclusion."*

Phase 6 published union escalation recall **1.000 (26/26)** from **one sample per item**. That figure is now
a non-tradeable constraint (`C1`), which means it has to be measured under a protocol, not inherited from a
single run. This script establishes that protocol against the **current, unchanged, merged** configuration —
deliberately before any candidate exists to be flattered by the comparison. One fingerprint, ledger entry
#1, and nothing in the system is changed in response to what it shows, which is what keeps it legitimate
under §2.3's *"one configuration, any number of samples."*

## Protocol

* **k = 5 samples per item.** An item missed on **any** sample counts as a miss -- the safety-conservative
  reading, matching `SUCCESS-METRICS.md` §2's *"recall wins any conflict."*
* **Temperature 0.0** (`D27`/`D30`), the shipped default. No comparison in this phase mixes temperatures.
* **Population: the whole independent held-out set.** Positives give union recall; negatives give union
  false-escalation on a **rule-based** denominator -- unlike the 0.529, whose population included eight
  hand-picked openings (`measure_l2_precision.py`).
* **Union semantics** (`D15`): L1 fires OR L2 fires. L1 is deterministic, so it is evaluated once per item;
  only L2 is re-sampled.

## What k=5 measures now that the router is pinned to 0.0

At temperature 0.0 the router was measured stable across 5 x 78 turns (sd 0.000, `RESULTS.md` §3.3), so
five identical answers is the expected outcome and k=5 is **not** a variance estimate here. It is still
worth its ~$0.008: that stability was measured on the 78 golden first turns, and this is a **different
population** the determinism claim has never been tested on. Greedy decoding is also not a guarantee of
bit-identical serving -- batching and kernel selection are outside the client's control -- and `D29` is a
standing reminder that this project cannot see the serving side.

So the honest reading, stated before the run: **if all five samples agree on every item, k=5 has verified
determinism rather than estimated a spread**, and a future re-baseline could justify k=1 on that evidence.
If they disagree anywhere, the pinned configuration is not deterministic on this population and every
"reproducible" claim made since Stage 0.5 needs qualifying.

`ADR-013`: no `mock_aws()` in this file. Every call is a real, billed Bedrock call.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient, classify_turn

from evals.holdout import HoldoutKind, InjuryPhrasing, load_holdout
from evals.holdout_ledger import VerificationRun, verification_run
from evals.metrics import BinaryClassificationCounts
from evals.tier_b import CostLog, LoggingCaller

SAMPLES_PER_ITEM = 5


def _l2_fires(text: str, caller: LoggingCaller) -> bool:
    classification = classify_turn([{"role": "user", "content": [{"text": text}]}], caller=caller)
    return bool(classification.safety_flag)


def measure(
    phrasings: list[InjuryPhrasing], caller: LoggingCaller, *, k: int = SAMPLES_PER_ITEM
) -> dict[str, Any]:
    """Returns per-item results plus the any-sample-miss aggregates.

    Deliberately stores every sample rather than only the aggregate: `RESULTS.md` §0.1's whole
    complaint about Phase 6 is that its stored baselines could not answer questions that were not
    thought of at the time.
    """
    items: list[dict[str, Any]] = []
    for phrasing in phrasings:
        l1 = detect_safety_trigger(phrasing.text)[0]
        # L1 is deterministic (pure Python), so re-sampling it would only re-confirm itself and
        # would quintuple nothing. Only the model call is sampled.
        l2_samples = [_l2_fires(phrasing.text, caller) for _ in range(k)]
        union_samples = [l1 or s for s in l2_samples]
        items.append(
            {
                "text": phrasing.text,
                "kabco": phrasing.kabco.value,
                "should_escalate": phrasing.should_escalate,
                "l1": l1,
                "l2_samples": l2_samples,
                "union_samples": union_samples,
                "l2_stable": len(set(l2_samples)) == 1,
                # Any-sample-miss on positives; any-sample-fire on negatives. Both are the
                # conservative direction for the metric they feed.
                "union_worst_case": (
                    all(union_samples) if phrasing.should_escalate else any(union_samples)
                ),
            }
        )

    union = BinaryClassificationCounts()
    l1_only = BinaryClassificationCounts()
    for item in items:
        union = union.observe(expected=item["should_escalate"], actual=item["union_worst_case"])
        l1_only = l1_only.observe(expected=item["should_escalate"], actual=item["l1"])

    unstable = [i for i in items if not i["l2_stable"]]
    return {
        "protocol": {
            "samples_per_item": k,
            "scoring": "any-sample miss counts as a miss; any-sample fire counts as a false escalation",
            "temperature": 0.0,
            "population": "evals/holdout/injury_phrasings_independent.yaml (all items)",
        },
        "items": items,
        "positives": sum(1 for i in items if i["should_escalate"]),
        "negatives": sum(1 for i in items if not i["should_escalate"]),
        "union_recall": union.recall.value,
        "union_recall_counts": [union.recall.numerator, union.recall.denominator],
        "union_false_escalation": union.false_escalation_rate.value,
        "l1_only_recall": l1_only.recall.value,
        "l1_only_false_escalation": l1_only.false_escalation_rate.value,
        "unstable_item_count": len(unstable),
        "unstable_items": [{"text": i["text"], "l2_samples": i["l2_samples"]} for i in unstable],
        "kabco_distribution": dict(Counter(i["kabco"] for i in items)),
    }


def main(out_path: Path) -> int:
    with verification_run(
        reason=(
            "Stage 2 baseline: k-sampled union escalation recall of the CURRENT UNCHANGED merged "
            "configuration (ADR-004 §1), establishing the number C1 attaches to before any candidate "
            "exists. Nothing is changed in response to this measurement."
        ),
        samples_per_item=SAMPLES_PER_ITEM,
    ) as run:
        return _run(out_path, run)


def _run(out_path: Path, run: VerificationRun) -> int:
    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    phrasings = load_holdout(HoldoutKind.INDEPENDENT)
    print(
        f"=== Union baseline: {len(phrasings)} items x k={SAMPLES_PER_ITEM} "
        f"= {len(phrasings) * SAMPLES_PER_ITEM} real Nova Micro calls ==="
    )
    result = measure(phrasings, caller)

    print(f"\n  positives {result['positives']}   negatives {result['negatives']}")
    print(
        f"  L1 alone      recall {result['l1_only_recall']}   FE {result['l1_only_false_escalation']}"
    )
    print(
        f"  UNION (L1|L2) recall {result['union_recall']} "
        f"{tuple(result['union_recall_counts'])}   FE {result['union_false_escalation']}"
    )
    print(
        f"  items whose L2 verdict varied across {SAMPLES_PER_ITEM} samples: "
        f"{result['unstable_item_count']}"
    )
    for item in result["unstable_items"]:
        print(f"    UNSTABLE {item['l2_samples']}  {item['text'][:70]!r}")

    recall = result["union_recall"]
    if recall is not None and recall < 1.0:
        print(
            "\n  *** C1: union recall is BELOW 1.000 under repetition. Per Marco's instruction this is "
            "a CORRECTION to Phase 6 in RESULTS.md, not a Phase 7 footnote. ***"
        )

    result["cost"] = log.summary()
    print(f"\n=== Cost: {log.summary()} ===")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {out_path}")

    run.record(
        union_recall=result["union_recall"],
        union_recall_counts=result["union_recall_counts"],
        union_false_escalation=result["union_false_escalation"],
        l1_only_recall=result["l1_only_recall"],
        unstable_item_count=result["unstable_item_count"],
        cost_usd=log.total_usd,
    )
    run.note(
        "Baseline of the unchanged merged configuration. No system change was made in response, "
        "which is what keeps this legitimate under BUILD-PLAN.md section 2.3."
    )
    return 0


if __name__ == "__main__":
    import sys

    default = Path("evals/baselines") / "union_baseline_k5_20260812.json"
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else default))
