#!/usr/bin/env python3
"""Prints a live Bedrock cost estimate for all enabled scenarios and blocks on typed approval.

Used by `make provision` and by the fine-tune launcher (scripts/run_pipeline.py). Never
provisions or launches anything itself — callers gate their own action on this script's
approval outcome.
"""

import argparse
import sys

from bedrock_platform.aws.cost_estimator import (
    CostEstimate,
    PriceUnavailableError,
    estimate_scenario_cost,
)
from bedrock_platform.aws.finetune_client import APPROVAL_TOKEN
from bedrock_platform.config.scenario_loader import enabled_scenarios

# Kept as a module-level alias so scripts/run_pipeline.py's existing
# `cost_cli._estimate_scenario_cost(...)` call site keeps working unchanged.
_estimate_scenario_cost = estimate_scenario_cost


def print_cost_table(estimates: list[CostEstimate]) -> None:
    width = 104
    print()
    print("Live Bedrock cost estimate (AWS Price List API)")
    print("=" * width)
    print(
        f"{'Scenario':<14}{'Base model':<32}{'Training $':>12}{'Storage $/mo':>14}"
        f"{'Input $':>10}{'Output $':>10}{'One-time $':>12}"
    )
    print("-" * width)
    total_one_time = 0.0
    total_recurring = 0.0
    for e in estimates:
        print(
            f"{e.scenario_id:<14}{e.base_model_id:<32}{e.training_cost_usd:>12.4f}"
            f"{e.storage_cost_usd_per_month:>14.4f}"
            f"{e.input_cost_usd:>10.4f}{e.output_cost_usd:>10.4f}"
            f"{e.total_one_time_cost_usd:>12.4f}"
        )
        total_one_time += e.total_one_time_cost_usd
        total_recurring += e.storage_cost_usd_per_month
    print("-" * width)
    print(f"{'TOTAL':<14}{'':<32}{'':>12}{'':>14}{'':>10}{'':>10}{total_one_time:>12.4f}")
    print()
    print(f"One-time cost (training + demo inference): ~${total_one_time:.4f}")
    print(f"Recurring cost while models exist: ~${total_recurring:.4f}/month")
    print()
    # Per-scenario, not a single line: scenarios may run on different base models,
    # which have different per-token training prices.
    print("Live per-unit prices used:")
    for e in estimates:
        print(
            f"  {e.scenario_id:<14}{e.base_model_id:<32}"
            f"training ${e.training_price_per_1k_usd}/1K tok, "
            f"storage ${e.storage_price_per_model_month_usd}/model/month"
        )
    print()


def block_on_approval() -> bool:
    typed = input(f"Type '{APPROVAL_TOKEN}' to proceed, anything else to abort: ")
    return typed.strip() == APPROVAL_TOKEN


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the cost table and exit without prompting for approval or provisioning.",
    )
    args = parser.parse_args()

    scenarios = enabled_scenarios()

    try:
        estimates = [_estimate_scenario_cost(s) for s in scenarios]
    except PriceUnavailableError as exc:
        print(f"ERROR: could not fetch live pricing: {exc}", file=sys.stderr)
        return 1

    print_cost_table(estimates)

    if args.dry_run:
        print("Dry run — exiting without provisioning anything.")
        return 0

    if block_on_approval():
        print("Approved.")
        return 0

    print("Not approved — aborting.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
