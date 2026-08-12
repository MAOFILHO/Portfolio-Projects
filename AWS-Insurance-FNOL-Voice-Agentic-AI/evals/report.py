"""Report rendering and the `make eval` entry point.

Every line is labelled with its tier, and Tier A results are never printed in a way that could be read as
an evaluation of the system as a whole. The header says so in one sentence rather than relying on the
reader to know the distinction.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .schema import load_golden_set
from .tier_a import (
    L1NotMeasured,
    L1Result,
    TierAReport,
    escalation_outcome_consistency,
    gate_failures,
    run_tier_a,
)


def _render_l1(result: L1Result | L1NotMeasured, label: str, *, gated: bool) -> list[str]:
    kind = "GATE" if gated else "OBSERVED"
    if isinstance(result, L1NotMeasured):
        return [
            f"  [{kind}] {label}: NOT MEASURED",
            f"           {result.reason}",
            "           (reported as absent, never as 0.0)",
        ]
    c = result.counts
    lines = [
        f"  [{kind}] {label}",
        f"           recall              {c.recall}",
        f"           false-escalation    {c.false_escalation_rate}",
        f"           precision           {c.precision}",
    ]
    for miss in result.missed:
        lines.append(f"           MISSED  {miss}")
    for alarm in result.false_alarms:
        lines.append(f"           FALSE+  {alarm}")
    for deferred in result.deferred_to_l2:
        lines.append(
            f"           ->L2    {deferred}  (excluded from L1 counts; Tier B evaluates it)"
        )
    return lines


def render(report: TierAReport) -> str:
    lines: list[str] = [
        "=" * 96,
        "FNOL voice agent -- evaluation report",
        "=" * 96,
        "",
        "TIER A ONLY (deterministic, no model calls, $0.00).",
        "These results say nothing about model quality: intent accuracy, groundedness and answer",
        "quality all need real calls and are reported separately by the Tier B run (Stage 6).",
        "",
        "-- Safety: L1 deterministic detector " + "-" * 58,
    ]
    lines += _render_l1(report.l1_golden, "L1 on the labelled golden safety set", gated=True)
    lines.append("")
    lines += _render_l1(
        report.l1_holdout_weak,
        "L1 on the WEAKLY held-out set (same author as lexicon.py -- self-assessment)",
        gated=False,
    )
    lines.append("")
    lines += _render_l1(
        report.l1_holdout_independent,
        "L1 on the INDEPENDENT held-out set (isolated author, never read lexicon.py)",
        gated=False,
    )

    if report.retrieval is not None:
        ret = report.retrieval
        lines += [
            "",
            "-- Retrieval (real Titan vectors, committed fixture, $0.00 to re-run) " + "-" * 26,
            f"  [GATE]     recall@5   {ret.recall_at_5}   (threshold 0.90)",
            f"  [TARGET]   MRR        {ret.mrr:.3f}" if ret.mrr is not None else "  MRR n/a",
            f"             model      {ret.model_id}",
            "             per-query rank of the gold passage:",
        ]
        for qid, rank in ret.per_query_rank.items():
            flag = "" if (rank is not None and rank <= 5) else "   <- outside top 5"
            lines.append(f"               {qid:10} {rank}{flag}")

    lines += [
        "",
        "-- Corpus composition " + "-" * 73,
        f"  conversations           {report.conversation_count}",
        f"  turns                   {report.turn_count}",
        f"  mandatory escalations   {report.mandatory_escalation_count} "
        f"(excluded from the containment denominator)",
    ]
    for name, count in report.category_counts.items():
        lines.append(f"    {name:<16} {count}")

    failures = gate_failures(report)
    lines += ["", "-- Gates " + "-" * 86]
    if failures:
        lines += [f"  FAIL  {f}" for f in failures]
    else:
        lines.append("  All Tier A gates passed.")
    lines.append("=" * 96)
    return "\n".join(lines)


def to_dict(report: TierAReport) -> dict[str, Any]:
    """Baseline-serialisable form. Counts are stored, not just rates, so a future comparison can
    re-derive any rate rather than being limited to the ones this version happened to compute."""

    def l1(result: L1Result | L1NotMeasured) -> dict[str, Any] | None:
        if isinstance(result, L1NotMeasured):
            # The reason travels into the baseline JSON as well as the console report: a stored
            # baseline whose independent-set entry is a bare `null` cannot be told apart from one
            # taken before the set existed, and a future comparison would read it as a regression.
            return {"not_measured": result.reason}
        c = result.counts
        return {
            "set_name": result.set_name,
            "true_positives": c.true_positives,
            "false_positives": c.false_positives,
            "true_negatives": c.true_negatives,
            "false_negatives": c.false_negatives,
            "recall": c.recall.value,
            "false_escalation_rate": c.false_escalation_rate.value,
            "missed": result.missed,
            "false_alarms": result.false_alarms,
        }

    return {
        "tier": "A",
        "l1_golden": l1(report.l1_golden),
        "l1_holdout_weak": l1(report.l1_holdout_weak),
        "l1_holdout_independent": l1(report.l1_holdout_independent),
        "retrieval": (
            {
                "recall_at_5": report.retrieval.recall_at_5.value,
                "recall_at_5_counts": [
                    report.retrieval.recall_at_5.numerator,
                    report.retrieval.recall_at_5.denominator,
                ],
                "mrr": report.retrieval.mrr,
                "per_query_rank": report.retrieval.per_query_rank,
                "model_id": report.retrieval.model_id,
            }
            if report.retrieval is not None
            else None
        ),
        "broken_gold_labels": report.broken_gold_labels,
        "conversation_count": report.conversation_count,
        "turn_count": report.turn_count,
        "category_counts": report.category_counts,
        "mandatory_escalation_count": report.mandatory_escalation_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the FNOL evaluation harness.")
    parser.add_argument(
        "--tier",
        choices=["a"],
        default="a",
        help="Only tier A exists so far. Tier B (real model calls, cost-gated) lands at Stage 6 and "
        "will be opt-in rather than the default, so `make eval` can never spend money by accident.",
    )
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--check-regression",
        action="store_true",
        help="Compare against the committed baseline and fail on any GATE breach or any TARGET "
        "degrading by more than 3 points. This is what CI runs.",
    )
    args = parser.parse_args(argv)

    conversations = load_golden_set()
    problems = escalation_outcome_consistency(conversations)
    if problems:
        print(
            "Corpus labelling is inconsistent; refusing to report numbers from it:", file=sys.stderr
        )
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 2

    report = run_tier_a(conversations)
    print(render(report))

    regressed = False
    if args.check_regression:
        from .regression import compare, load_baseline

        regressions = compare(load_baseline(), to_dict(report))
        print("\n-- Regression vs committed baseline " + "-" * 59)
        if regressions:
            regressed = True
            for r in regressions:
                before = "n/a" if r.baseline is None else f"{r.baseline:.3f}"
                after = "GONE" if r.current is None else f"{r.current:.3f}"
                print(f"  REGRESSION  {r.metric}: {before} -> {after} ({r.detail})")
        else:
            print("  No regression against the committed baseline.")
    if args.json_out:
        # Create the parent directory. Without this the write raises after the report has already been
        # printed to stdout, which reads as a successful run with a stack trace after it -- and a
        # baseline that was never written while the numbers scrolled past looking fine.
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(to_dict(report), indent=2) + "\n")
        print(f"\nwrote {args.json_out}")
    return 1 if (gate_failures(report) or regressed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
