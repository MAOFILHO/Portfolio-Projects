from __future__ import annotations

import json
from pathlib import Path

from fnol_voice_agent.validation.identifiers import (
    compute_claim_number,
    luhn_check_digit,
    validate_drivers_licence,
    validate_plate,
    validate_police_report_number,
    validate_policy_number,
    verify_claim_number,
    vin_is_deliberately_invalid,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def test_luhn_worked_example_from_data_contracts_md() -> None:
    # DATA-CONTRACTS.md §1's own worked example: payload 260800042 -> check digit 4.
    assert luhn_check_digit("260800042") == 4


def test_compute_claim_number_matches_data_contracts_worked_example() -> None:
    assert compute_claim_number(26, 8, 42) == "CLM-2608-00042-4"


def test_verify_claim_number_accepts_valid_and_rejects_corrupted() -> None:
    assert verify_claim_number("CLM-2608-00042-4") is True
    assert verify_claim_number("CLM-2608-00042-5") is False  # wrong check digit
    assert verify_claim_number("not-a-claim-number") is False


def test_every_real_synthetic_claim_number_verifies() -> None:
    claims = json.loads((DATA_DIR / "claims" / "claims.json").read_text())["claims"]
    for c in claims:
        assert verify_claim_number(c["claim_number"]), c["claim_number"]


def test_every_real_synthetic_vin_is_deliberately_invalid() -> None:
    vehicles = json.loads((DATA_DIR / "vehicles" / "vehicles.json").read_text())["vehicles"]
    for v in vehicles:
        assert vin_is_deliberately_invalid(v["vin"]), v["vin"]


def test_format_validators() -> None:
    assert validate_policy_number("PY4821") is True
    assert validate_policy_number("PY482") is False
    assert validate_plate("KJH-4523") is True
    assert validate_plate("kjh-4523") is False
    assert validate_drivers_licence("D08954142") is True
    assert validate_police_report_number("2026-0811-042") is True
    assert validate_police_report_number("2026-08-11-042") is False
