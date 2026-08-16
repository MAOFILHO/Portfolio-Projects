from __future__ import annotations

import json
from pathlib import Path

from fnol_voice_agent.validation.coverage import (
    compute_covered_payout,
    compute_settlement,
    is_total_loss,
    rental_days_remaining,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "src" / "fnol_voice_agent" / "data" / "synthetic"


def test_total_loss_worked_example_from_coverage_logic_md() -> None:
    # coverage-logic.md's own worked example: 16000/18000 = 88.9% -> total loss, settlement 17000.
    assert is_total_loss(16000, 18000) is True
    assert compute_settlement(16000, 18000, deductible_cad=1000) == 17000


def test_rental_days_remaining_worked_example_from_endorsements_md() -> None:
    days_remaining, amount_remaining = rental_days_remaining(days_used=12)
    assert days_remaining == 8
    assert amount_remaining == 400


def test_covered_payout_respects_deductible_toggle() -> None:
    assert compute_covered_payout(6000, 1_000_000, 500, deductible_applies=True) == 5500
    assert compute_covered_payout(6000, 1_000_000, 500, deductible_applies=False) == 6000


def test_every_real_synthetic_claim_matches_settlement_arithmetic() -> None:
    claims = json.loads((DATA_DIR / "claims" / "claims.json").read_text())["claims"]
    for c in claims:
        repair, acv, ded = (
            c["repair_estimate_cad"],
            c["actual_cash_value_cad"],
            c["deductible_applied_cad"],
        )
        tow = c.get("towing_allowance_cad") or 0
        assert is_total_loss(repair, acv) == c["is_total_loss"], c["claim_number"]
        expected = compute_settlement(repair, acv, ded, tow)
        actual = (
            c["settlement_amount_cad"]
            if c["settlement_amount_cad"] is not None
            else c["estimated_settlement_cad"]
        )
        assert actual == expected, c["claim_number"]


def test_every_real_synthetic_rental_claim_matches_days_remaining_arithmetic() -> None:
    claims = json.loads((DATA_DIR / "claims" / "claims.json").read_text())["claims"]
    for c in claims:
        rental = c.get("rental")
        if not rental or not rental["elected_on_policy"] or rental["days_used"] is None:
            continue
        days_remaining, amount_remaining = rental_days_remaining(
            days_used=rental["days_used"], is_total_loss_claim=c["is_total_loss"]
        )
        assert days_remaining == rental["days_remaining"], c["claim_number"]
        assert amount_remaining == rental["amount_remaining_cad"], c["claim_number"]


def test_total_loss_claim_zeroes_out_rental_entitlement_per_endorsements_md() -> None:
    # endorsements.md: rental "does not apply if your automobile is settled as a total loss" -- caught
    # against the real corpus's CLM-2607-00042-5 (days_used=0, but days_remaining=0, not 20).
    days_remaining, amount_remaining = rental_days_remaining(days_used=0, is_total_loss_claim=True)
    assert (days_remaining, amount_remaining) == (0, 0.0)
