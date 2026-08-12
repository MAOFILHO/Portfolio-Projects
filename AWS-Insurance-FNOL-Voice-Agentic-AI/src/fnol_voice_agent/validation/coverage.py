"""Business-rule arithmetic, ported directly from `data/synthetic/policy/coverage-logic.md` (§1, §2) and
`data/synthetic/policy/endorsements.md`'s rental worked example -- not reimplemented from a paraphrase.
"""

from __future__ import annotations

TOTAL_LOSS_THRESHOLD = (
    0.80  # Example Mutual's own stated policy rule; Ontario sets no single legislated %
)


def is_total_loss(repair_estimate_cad: float, actual_cash_value_cad: float) -> bool:
    """coverage-logic.md §2: is_total_loss = repair_cost >= 0.80 * ACV."""
    return repair_estimate_cad >= TOTAL_LOSS_THRESHOLD * actual_cash_value_cad


def compute_settlement(
    repair_estimate_cad: float,
    actual_cash_value_cad: float,
    deductible_cad: float,
    towing_allowance_cad: float = 0,
) -> float:
    """coverage-logic.md §2: settlement = ACV - deductible if total loss, else
    min(repair, ACV) - deductible + towing allowance."""
    if is_total_loss(repair_estimate_cad, actual_cash_value_cad):
        return actual_cash_value_cad - deductible_cad
    return min(repair_estimate_cad, actual_cash_value_cad) - deductible_cad + towing_allowance_cad


def compute_covered_payout(
    cost_cad: float, limit_cad: float, deductible_cad: float, *, deductible_applies: bool
) -> float:
    """coverage-logic.md §1's general deductible arithmetic: covered_payout = min(cost, limit) -
    deductible_if_applicable. `deductible_applies=False` models DCPD's deductible-free-by-construction
    default (ONTARIO-INSURANCE-REFERENCE.md §4 -- optional in reality, none elected in this corpus).
    """
    return min(cost_cad, limit_cad) - (deductible_cad if deductible_applies else 0)


def rental_days_remaining(
    days_used: int,
    *,
    daily_cap_cad: float = 50,
    max_days: int = 20,
    total_cap_cad: float = 1000,
    is_total_loss_claim: bool = False,
) -> tuple[int, float]:
    """endorsements.md's worked example formula: days_remaining = min(20 - days_used,
    (1000 - days_used*50) / 50). Returns (days_remaining, amount_remaining_cad), both floored at zero.

    `is_total_loss_claim` implements endorsements.md's stated exception verbatim: "it does not apply if
    your automobile is settled as a total loss (a total-loss settlement compensates you for the vehicle
    itself, not a rental in the interim)" -- caught by testing against the real corpus (`CLM-2607-00042-5`,
    a total-loss claim with `days_used=0` but `days_remaining=0`, not the 20 the plain formula would give).
    """
    if is_total_loss_claim:
        return 0, 0.0
    days_left_by_duration = max_days - days_used
    amount_left = total_cap_cad - days_used * daily_cap_cad
    days_left_by_amount = amount_left / daily_cap_cad
    days_remaining = max(0, min(days_left_by_duration, int(days_left_by_amount)))
    return days_remaining, max(0.0, amount_left)
