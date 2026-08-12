"""The Phase 7 ablation ladder — rungs A→D under one fixed protocol. `ADR-014` §2/§4/§6, Stage 4.

A single before/after cannot tell the merge apart from the label space, so the phase runs a ladder in
which each rung adds exactly one change:

| Rung | Configuration | Isolates |
|---|---|---|
| A | merged call, unchanged | baseline on this protocol |
| B | merged call, `InjuryEscalation` removed from the classifier's output enum | label-space coupling |
| C | B + split into two concurrent single-purpose calls, injury instruction **verbatim** | the merge itself |
| D | C + revised detector prompt | the only rung where tuning happens |

**Cumulative, not four independent variants.** That is what makes each pairwise difference attributable:
B−A is the label space, C−B is the merge, D−C is the wording. `ADR-014` §4 also pre-commits the reading of
C≈A (the instruction is the cause and neither the merge nor the label space is).

## Protocol, fixed before any rung ran (`D30`)

* **Temperature 0.0** on every rung including A. **No rung reuses an earlier number** -- not Stage 0's
  0.474, not Stage 0.5's 0.518. Marco: *"A comparison between a deterministic candidate and a stochastic
  baseline is not a comparison."*
* **k = 5** per item. Any-sample-miss for recall, any-sample-fire for false escalation.
* **Two populations, each measuring what it can.** The **tuning set** (80 injury phrasings, isolated
  author) carries escalation recall and false escalation -- the metrics Phase 7 exists to move. The
  **golden set's first turns** (78 labelled conversations) carry intent macro-F1 and out-of-scope recall,
  because the tuning set has no intent labels.
* **The independent held-out set is not touched here.** Stage 8 verifies one frozen configuration against
  it, which is why the ledger has one entry and not five.
* Intent macro-F1 is scored on the system's **effective** intent (detector fires -> effective intent is
  `InjuryEscalation`), with the classifier's **raw** answer reported beside it. Fixed in `BUILD-PLAN.md`
  §1 before any rung ran, so the split cannot be credited by a scoring convention.

`ADR-013`: no `mock_aws()` in this file. Every call is real and billed.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.aws.bedrock_router import (
    BotoBedrockConverseClient,
    build_classify_turn_tool_spec,
    classify_turn,
)
from fnol_voice_agent.aws.split_router import classify_turn_split
from fnol_voice_agent.models.enums import Intent

from evals.holdout import HoldoutKind, load_holdout
from evals.metrics import BinaryClassificationCounts, Rate, macro_f1
from evals.schema import Category, GoldenConversation, load_golden_set
from evals.tier_b import CostLog, LoggingCaller

SAMPLES_PER_ITEM = 5

# Rung D's revised detector prompt. `ADR-014` §4 caps rung D at 3 revisions and requires the iteration
# count to be reported; this is revision 1. The change is deliberately narrow -- it keeps "when in doubt,
# true" (C1 makes recall non-tradeable, so the bias stays) and adds only the distinction the Phase 6
# error analysis actually found: the detector fired on damage to *vehicles* described in human terms,
# and on ordinary claim openings that mention an accident without mentioning a person.
_REVISED_DETECTOR_PROMPT = (
    "You are a safety detector for a P&C auto insurance FNOL call. You have exactly one job: decide "
    "whether this caller turn indicates that A PERSON may be injured or dead. You do not classify "
    "intent, you do not generate any response the caller will hear, and you only call `detect_injury`. "
    "Set `injury_indicated` to true on any hint of injury, pain, unconsciousness, or medical distress "
    "to a person, including indirect or self-negating phrasing (\"I'm fine but he's not moving\") — "
    "when in doubt about a person, true. Two things are NOT injuries to a person, however they are "
    "phrased: damage to a vehicle, even when described in human terms (a car that is hurt, wrecked, "
    "dying, mangled, or 'took a beating'), and the mere fact that a collision or claim occurred, with "
    "no indication that anyone was hurt. Call the tool. Do not produce any other output."
)


@dataclass
class RungResult:
    name: str
    description: str
    calls: int
    # Escalation metrics, tuning set
    union_recall: float | None = None
    union_recall_counts: tuple[int, int] = (0, 0)
    union_false_escalation: float | None = None
    l2_false_escalation: float | None = None
    escalation_unstable: int = 0
    # Intent metrics, golden set
    intent_macro_f1: float | None = None
    raw_intent_macro_f1: float | None = None
    out_of_scope_recall: float | None = None
    intent_unstable: int = 0
    confusions: list[str] = field(default_factory=list)
    # Latency, split rungs only
    detector_ms_p50: float | None = None
    classifier_ms_p50: float | None = None
    wall_ms_p50: float | None = None
    sequential_ms_p50: float | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = dict(vars(self))
        payload["union_recall_counts"] = list(self.union_recall_counts)
        return payload


# A rung is a function from (turn text, caller) to (safety_flag, raw_intent, latencies).
Classifier = Callable[[str, LoggingCaller], tuple[bool, Intent, dict[str, float]]]


def _rung_a(text: str, caller: LoggingCaller) -> tuple[bool, Intent, dict[str, float]]:
    result = classify_turn([{"role": "user", "content": [{"text": text}]}], caller=caller)
    return bool(result.safety_flag), result.intent, {}


def _build_no_injury_tool_spec() -> dict[str, Any]:
    """Rung B: the merged tool schema with `InjuryEscalation` removed from the `intent` enum.

    Built by mutating what the shipped `build_classify_turn_tool_spec()` returns, rather than
    hand-writing a second schema -- the same reason that function derives from the Pydantic model in
    the first place. `intent` is a `$ref` to a `$defs` entry, so the enum lives there.

    **This removes an intent from one call's output vocabulary, not from the system.** The six intents,
    the golden labels and the escalation path are unchanged; `D12` already holds that injury detection is
    a deterministic pre-node rather than a model-classified intent, and this rung makes the merged call's
    schema match that decision.
    """
    spec = build_classify_turn_tool_spec()
    schema = spec["toolSpec"]["inputSchema"]["json"]
    defs = schema.get("$defs", {})
    for name, definition in defs.items():
        if "enum" in definition and Intent.INJURY_ESCALATION.value in definition["enum"]:
            definition["enum"] = [
                v for v in definition["enum"] if v != Intent.INJURY_ESCALATION.value
            ]
            break
    else:  # pragma: no cover - a schema shape change should fail loudly, not silently no-op
        raise RuntimeError(
            "Could not find the intent enum in the classify_turn tool schema. Rung B would have run "
            "as a duplicate of rung A, and the ladder would have reported a meaningless B-A delta."
        )
    return spec


def _rung_b(text: str, caller: LoggingCaller) -> tuple[bool, Intent, dict[str, float]]:
    result = classify_turn(
        [{"role": "user", "content": [{"text": text}]}],
        caller=caller,
        tool_spec=_build_no_injury_tool_spec(),
    )
    return bool(result.safety_flag), result.intent, {}


def _split_rung(detector_prompt: str | None) -> Classifier:
    def run(text: str, caller: LoggingCaller) -> tuple[bool, Intent, dict[str, float]]:
        result = classify_turn_split(
            [{"role": "user", "content": [{"text": text}]}],
            caller=caller,
            detector_prompt=detector_prompt,
        )
        return (
            result.injury_indicated,
            result.raw_intent,
            {
                "detector_ms": result.detector_ms,
                "classifier_ms": result.classifier_ms,
                "wall_ms": result.wall_ms,
                "sequential_ms": result.detector_ms + result.classifier_ms,
            },
        )

    return run


RUNGS: tuple[tuple[str, str, Classifier], ...] = (
    ("A", "merged call, unchanged (ADR-004 section 1)", _rung_a),
    ("B", "merged call, InjuryEscalation removed from the classifier output enum", _rung_b),
    ("C", "split into two concurrent calls, injury instruction verbatim", _split_rung(None)),
    (
        "D",
        "split + revised detector prompt (revision 1 of at most 3)",
        _split_rung(_REVISED_DETECTOR_PROMPT),
    ),
)


def _measure_escalation(
    run: Classifier, caller: LoggingCaller, k: int
) -> tuple[BinaryClassificationCounts, BinaryClassificationCounts, int, list[dict[str, float]]]:
    """Escalation recall and false escalation on the tuning set, plus latency samples."""
    union = BinaryClassificationCounts()
    l2_only = BinaryClassificationCounts()
    unstable = 0
    latencies: list[dict[str, float]] = []

    for phrasing in load_holdout(HoldoutKind.TUNING):
        l1 = detect_safety_trigger(phrasing.text)[0]
        flags: list[bool] = []
        for _ in range(k):
            flag, _intent, timings = run(phrasing.text, caller)
            flags.append(flag)
            if timings:
                latencies.append(timings)
        if len(set(flags)) > 1:
            unstable += 1
        # Conservative in the direction of the metric: a positive is caught only if every sample
        # caught it; a negative is a false escalation if any sample fired.
        l2_worst = all(flags) if phrasing.should_escalate else any(flags)
        union_worst = l1 or l2_worst
        union = union.observe(expected=phrasing.should_escalate, actual=union_worst)
        l2_only = l2_only.observe(expected=phrasing.should_escalate, actual=l2_worst)
    return union, l2_only, unstable, latencies


def _measure_intent(
    run: Classifier, caller: LoggingCaller, conversations: Sequence[GoldenConversation], k: int
) -> tuple[Rate | None, Rate | None, BinaryClassificationCounts, int, list[str]]:
    """Effective-intent and raw-intent macro-F1 plus out-of-scope recall, on the golden first turns."""
    labels = [i.value for i in Intent]
    effective = {label: BinaryClassificationCounts() for label in labels}
    raw = {label: BinaryClassificationCounts() for label in labels}
    oos = BinaryClassificationCounts()
    unstable = 0
    confusions: list[str] = []

    for conversation in conversations:
        expected_intent = conversation.turns[0].expect.intent or conversation.intent
        if expected_intent is None:
            continue
        text = conversation.turns[0].caller
        l1 = detect_safety_trigger(text)[0]

        samples: list[tuple[bool, Intent]] = []
        for _ in range(k):
            flag, raw_intent, _timings = run(text, caller)
            samples.append((flag, raw_intent))
        if len(set(samples)) > 1:
            unstable += 1

        # The modal sample is the one scored, so one deviant draw cannot dominate an aggregate the
        # way any-sample-worst-case correctly does for the *safety* metrics. Different metrics get
        # different aggregations on purpose: recall is conservative, quality is representative.
        flag, raw_intent = statistics.mode(samples)
        effective_intent = Intent.INJURY_ESCALATION if (l1 or flag) else raw_intent

        for label in labels:
            effective[label] = effective[label].observe(
                expected=(label == expected_intent.value), actual=(label == effective_intent.value)
            )
            raw[label] = raw[label].observe(
                expected=(label == expected_intent.value), actual=(label == raw_intent.value)
            )
        oos = oos.observe(
            expected=conversation.category is Category.OUT_OF_SCOPE,
            actual=effective_intent is Intent.OUT_OF_SCOPE,
        )
        if effective_intent.value != expected_intent.value:
            confusions.append(
                f"{conversation.id}: expected {expected_intent.value}, got {effective_intent.value}"
                + (f" (raw {raw_intent.value})" if raw_intent is not effective_intent else "")
            )

    return macro_f1(effective), macro_f1(raw), oos, unstable, confusions


def _p50(samples: list[dict[str, float]], key: str) -> float | None:
    values = [s[key] for s in samples if key in s]
    return statistics.median(values) if values else None


def run_rung(
    name: str,
    description: str,
    run: Classifier,
    conversations: Sequence[GoldenConversation],
    *,
    k: int,
) -> tuple[RungResult, CostLog]:
    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    union, l2_only, esc_unstable, latencies = _measure_escalation(run, caller, k)
    eff_f1, raw_f1, oos, intent_unstable, confusions = _measure_intent(
        run, caller, conversations, k
    )

    result = RungResult(
        name=name,
        description=description,
        calls=len(log.calls),
        union_recall=union.recall.value,
        union_recall_counts=(union.recall.numerator, union.recall.denominator),
        union_false_escalation=union.false_escalation_rate.value,
        l2_false_escalation=l2_only.false_escalation_rate.value,
        escalation_unstable=esc_unstable,
        intent_macro_f1=eff_f1.value if eff_f1 else None,
        raw_intent_macro_f1=raw_f1.value if raw_f1 else None,
        out_of_scope_recall=oos.recall.value,
        intent_unstable=intent_unstable,
        confusions=confusions,
        detector_ms_p50=_p50(latencies, "detector_ms"),
        classifier_ms_p50=_p50(latencies, "classifier_ms"),
        wall_ms_p50=_p50(latencies, "wall_ms"),
        sequential_ms_p50=_p50(latencies, "sequential_ms"),
    )
    return result, log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rungs", default="ABCD", help="which rungs to run, e.g. AB or CD")
    parser.add_argument("--k", type=int, default=SAMPLES_PER_ITEM)
    parser.add_argument("--out", type=Path, default=Path("evals/baselines/ablation_ladder.json"))
    args = parser.parse_args()

    conversations = load_golden_set()
    results: list[RungResult] = []
    total_usd = 0.0
    total_calls = 0

    for name, description, run in RUNGS:
        if name not in args.rungs:
            continue
        print(f"\n=== Rung {name}: {description} (k={args.k}) ===", flush=True)
        result, log = run_rung(name, description, run, conversations, k=args.k)
        total_usd += log.total_usd
        total_calls += len(log.calls)
        results.append(result)
        print(
            f"  union recall        {result.union_recall} {result.union_recall_counts}\n"
            f"  union FE            {result.union_false_escalation}\n"
            f"  L2-only FE          {result.l2_false_escalation}\n"
            f"  intent macro-F1     {result.intent_macro_f1}  (raw {result.raw_intent_macro_f1})\n"
            f"  out-of-scope recall {result.out_of_scope_recall}\n"
            f"  unstable            {result.escalation_unstable} escalation / "
            f"{result.intent_unstable} intent\n"
            f"  calls               {len(log.calls)}   ${log.total_usd:.5f}",
            flush=True,
        )
        if result.wall_ms_p50 is not None:
            print(
                f"  latency p50         wall {result.wall_ms_p50:.0f} ms vs sequential "
                f"{result.sequential_ms_p50:.0f} ms "
                f"(detector {result.detector_ms_p50:.0f} / classifier "
                f"{result.classifier_ms_p50:.0f})",
                flush=True,
            )

    payload = {
        "protocol": {
            "temperature": 0.0,
            "samples_per_item": args.k,
            "escalation_population": "evals/tuning/injury_phrasings_tuning.yaml",
            "intent_population": "golden set, first turn of each labelled conversation",
            "escalation_aggregation": "any-sample worst case",
            "intent_aggregation": "modal sample",
            "intent_scoring": "effective intent (detector fires -> InjuryEscalation); raw reported too",
        },
        "rungs": [r.as_dict() for r in results],
        "total_calls": total_calls,
        "total_usd": round(total_usd, 6),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\n=== {total_calls} calls, ${total_usd:.5f} -> wrote {args.out} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
