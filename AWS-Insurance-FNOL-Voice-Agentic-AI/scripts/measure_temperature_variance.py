"""Phase 7 Stage 0.5 — quantify `D27` before fixing it.

Stage 0 found the router sampling at Nova's default temperature (0.7) and showed, from two runs, that
intent macro-F1 moved 0.623 → 0.474 on identical inputs. **Two runs establish that the variance is large.
They do not establish the distribution**, and `RESULTS.md` currently says so.

Marco's decision at Stage 0: quantify, then fix. This script measures **k=5 runs over all 78 labelled
golden first turns at each of two settings** — the shipped default (no `temperature` key sent) and
`temperature=0.0` — before the shipped default changes. 780 real Nova Micro calls, ≈$0.03.

Four things it produces that the fix alone would not:

1. **A spread rather than a point** for every Tier B intent metric, which is what Phase 6 should have
   published and what `RESULTS.md` §3.1 currently owes.
2. **Evidence that temperature is the cause**, not a coincidence — if 0.0 collapses the spread and 0.7
   reproduces it, the mechanism is established rather than assumed.
3. **The per-item stability profile.** Which turns flip between runs matters more than the aggregate: a
   metric that is stable except on the injury boundary is a different problem from one that is noisy
   everywhere.
4. **A rehearsal of the exact k-sample protocol C1 requires**, on a set that is not the independent
   held-out set, so the protocol is debugged before it is pointed at the one measurement that cannot be
   re-spent.

**Temperature 0 is not determinism.** Bedrock makes no bit-reproducibility guarantee — batching and
hardware scheduling can still move a token. k-sampling therefore stays necessary at 0.0; the question this
script answers is how much the spread shrinks, not whether it vanishes.

`ADR-013`: no `mock_aws()` here. Every call is real and billed.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from fnol_voice_agent.aws.bedrock_router import (
    BedrockRouterError,
    BotoBedrockConverseClient,
    classify_turn,
)
from fnol_voice_agent.models.enums import Intent

from evals.metrics import BinaryClassificationCounts, macro_f1
from evals.schema import Category, load_golden_set
from evals.tier_b import CostLog, LoggingCaller

OUT_PATH = Path("evals/baselines/temperature_variance_20260812.json")

# The two settings under test. `None` means "send no temperature key", i.e. exactly what shipped
# through Phase 6 -- reproducing the defect is the control, so it has to be expressible.
SETTINGS: tuple[tuple[str, float | None], ...] = (("default_unset", None), ("zero", 0.0))

DEFAULT_K = 5


def _metrics(runs: list[dict[str, dict[str, Any]]]) -> dict[str, Any]:
    labels = [i.value for i in Intent]
    per_run: list[dict[str, float | None]] = []
    for run in runs:
        per_class = {label: BinaryClassificationCounts() for label in labels}
        oos = BinaryClassificationCounts()
        flagged = 0
        for row in run.values():
            expected, actual = row["expected_intent"], row["intent"]
            for label in labels:
                per_class[label] = per_class[label].observe(
                    expected=(label == expected), actual=(label == actual)
                )
            oos = oos.observe(
                expected=row["expected_oos"], actual=(actual == Intent.OUT_OF_SCOPE.value)
            )
            flagged += int(row["safety_flag"])
        f1 = macro_f1(per_class)
        per_run.append(
            {
                "macro_f1": None if f1 is None else f1.value,
                "accuracy": sum(1 for r in run.values() if r["intent"] == r["expected_intent"])
                / len(run),
                "oos_recall": oos.recall.value,
                "safety_flag_rate": flagged / len(run),
            }
        )

    summary: dict[str, Any] = {"per_run": per_run}
    for key in ("macro_f1", "accuracy", "oos_recall", "safety_flag_rate"):
        vals: list[float] = [v for r in per_run if (v := r[key]) is not None]
        summary[key] = {
            "values": vals,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "spread": (max(vals) - min(vals)) if vals else None,
            "mean": statistics.fmean(vals) if vals else None,
            "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
        }
    return summary


def _stability(runs: list[dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """Per-item agreement across runs. The aggregate hides which turns are actually unstable."""
    # Only items present in EVERY run. A turn whose classification was dropped in one run has no
    # comparable value there, and treating a dropped turn as "stable" because it appears fewer times
    # would let the defect hide inside the stability figure.
    ids = sorted(set.intersection(*(set(r) for r in runs))) if runs else []
    unstable_intent: dict[str, dict[str, int]] = {}
    unstable_flag: dict[str, dict[str, int]] = {}
    for cid in ids:
        intents = Counter(r[cid]["intent"] for r in runs)
        flags = Counter(r[cid]["safety_flag"] for r in runs)
        if len(intents) > 1:
            unstable_intent[cid] = dict(intents)
        if len(flags) > 1:
            unstable_flag[cid] = {str(k): v for k, v in flags.items()}
    return {
        "items": len(ids),
        "intent_unstable_count": len(unstable_intent),
        "safety_flag_unstable_count": len(unstable_flag),
        "intent_unstable": unstable_intent,
        "safety_flag_unstable": unstable_flag,
    }


def run_setting(
    temperature: float | None, k: int, caller: Any
) -> tuple[list[dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    """Returns (runs, dropped_field_events).

    **A `ValidationError` here is a measurement, not a crash.** The first attempt at this script aborted
    on one, and that abort was the finding: at temperature 0.7 the merged call sometimes omits
    `safety_flag` entirely — a field the forced tool-use schema marks required.

    `ADR-004` argued that a schema-required field *"cannot be silently omitted without the call itself
    failing validation — which is the mechanism, not just the intention"* behind Q10. That argument is
    **correct and holds**: the call raised rather than returning a classification with the safety field
    quietly absent. What it did not anticipate is how often the model would exercise it. A turn whose
    classification raises is a turn the caller does not get routed on, so the property is safe-by-failure
    but not free, and the rate is exactly what this counts.

    Excluding these turns from the metrics rather than scoring them would understate the defect, so they
    are counted separately and reported next to the rates they are missing from.
    """
    conversations = [
        c for c in load_golden_set() if (c.turns[0].expect.intent or c.intent) is not None
    ]
    runs = []
    dropped: list[dict[str, Any]] = []
    for i in range(k):
        run: dict[str, dict[str, Any]] = {}
        for conv in conversations:
            expected = conv.turns[0].expect.intent or conv.intent
            assert expected is not None
            try:
                cls = classify_turn(
                    [{"role": "user", "content": [{"text": conv.turns[0].caller}]}],
                    caller=caller,
                    temperature=temperature,
                )
            except (ValidationError, BedrockRouterError) as exc:
                dropped.append(
                    {
                        "run": i,
                        "id": conv.id,
                        "text": conv.turns[0].caller,
                        "error": type(exc).__name__,
                        "detail": str(exc).splitlines()[0],
                    }
                )
                print(f"    DROPPED  run {i + 1}  {conv.id}  {type(exc).__name__}")
                continue
            run[conv.id] = {
                "expected_intent": expected.value,
                "expected_oos": conv.category is Category.OUT_OF_SCOPE,
                "intent": cls.intent,
                "safety_flag": bool(cls.safety_flag),
            }
        runs.append(run)
        print(f"    run {i + 1}/{k} done ({len(run)} classified, {len(dropped)} dropped so far)")
    return runs, dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure D27's variance at two temperatures.")
    parser.add_argument("-k", type=int, default=DEFAULT_K, help="samples per setting")
    args = parser.parse_args(argv)

    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    payload: dict[str, Any] = {"k": args.k, "settings": {}}
    for name, temperature in SETTINGS:
        print(f"=== {name} (temperature={temperature}) ===")
        runs, dropped = run_setting(temperature, args.k, caller)
        payload["settings"][name] = {
            "temperature": temperature,
            "metrics": _metrics(runs),
            "stability": _stability(runs),
            "dropped_safety_flag": {
                "count": len(dropped),
                "of_attempts": args.k * len(runs[0] if runs else {}) + len(dropped),
                "events": dropped,
            },
        }

    payload["cost"] = log.summary()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")

    print("\n" + "=" * 78)
    for name, _ in SETTINGS:
        m = payload["settings"][name]["metrics"]
        s = payload["settings"][name]["stability"]
        print(f"{name:>14}  macro-F1 {m['macro_f1']['min']:.3f}-{m['macro_f1']['max']:.3f}", end="")
        print(f"  (spread {m['macro_f1']['spread']:.3f}, sd {m['macro_f1']['stdev']:.4f})", end="")
        d = payload["settings"][name]["dropped_safety_flag"]
        print(
            f"  unstable: intent {s['intent_unstable_count']},"
            f" flag {s['safety_flag_unstable_count']},"
            f" DROPPED safety_flag {d['count']}"
        )
    print(f"\ncost {log.summary()}\nwrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
