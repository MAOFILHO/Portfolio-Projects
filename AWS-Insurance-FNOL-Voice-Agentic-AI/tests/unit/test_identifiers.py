from __future__ import annotations

import json
from pathlib import Path

from fnol_voice_agent.validation.identifiers import (
    compute_claim_number,
    luhn_check_digit,
    normalize_policy_number,
    resolve_policy_number_by_digits,
    validate_drivers_licence,
    validate_plate,
    validate_police_report_number,
    validate_policy_number,
    verify_claim_number,
    vin_is_deliberately_invalid,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "src" / "fnol_voice_agent" / "data" / "synthetic"


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


# `D207`/`OI125` follow-up, live evidence 2026-09-02 (contacts `07ec07e6`/`f5cd57b9`, 19:05/19:06):
# ASR mis-hears policy_number's leading letter(s) -- "PY4821" arrives as "uy4821" or "ty4821" -- or
# truncates it -- "py"/"py48". Every real corpus policy number is PY + 4 digits (see the real set below,
# read from the synthetic corpus, not hand-typed), so the digits alone already identify one policy
# uniquely today; this fallback only ever trusts that when it holds, never by assumption.
_REAL_POLICY_NUMBERS = frozenset({"PY4821", "PY1103", "PY6650", "PY2977", "PY3348", "PY9012"})


def test_resolve_policy_number_by_digits_matches_a_mis_heard_leading_letter() -> None:
    assert resolve_policy_number_by_digits("UY4821", _REAL_POLICY_NUMBERS) == "PY4821"
    assert resolve_policy_number_by_digits("TY4821", _REAL_POLICY_NUMBERS) == "PY4821"


def test_resolve_policy_number_by_digits_returns_none_on_too_few_digits() -> None:
    # "too few digits to be unambiguous" -- neither has 4 digits, so neither equals any real policy's
    # digit string exactly.
    assert resolve_policy_number_by_digits("PY", _REAL_POLICY_NUMBERS) is None
    assert resolve_policy_number_by_digits("PY48", _REAL_POLICY_NUMBERS) is None


def test_resolve_policy_number_by_digits_returns_none_when_ambiguous() -> None:
    # Synthetic collision, not a real corpus case (today's real set has no two policies sharing a digit
    # string) -- proves the safety property itself: more than one match must never guess.
    ambiguous = frozenset({"PY4821", "AB4821"})
    assert resolve_policy_number_by_digits("XY4821", ambiguous) is None


def test_resolve_policy_number_by_digits_returns_none_on_no_digits_at_all() -> None:
    assert resolve_policy_number_by_digits("not-a-policy-number", _REAL_POLICY_NUMBERS) is None


def test_normalize_policy_number_passes_through_an_exact_match() -> None:
    assert normalize_policy_number("py4821", _REAL_POLICY_NUMBERS) == "PY4821"


def test_normalize_policy_number_falls_back_to_digits_when_the_prefix_is_mis_heard() -> None:
    assert normalize_policy_number("uy4821", _REAL_POLICY_NUMBERS) == "PY4821"


def test_normalize_policy_number_returns_the_uppercased_original_when_unresolved() -> None:
    """Not a raise -- the fallback failing is a no-op, not a new error path. Callers keep whatever
    format/not-found handling they already had for a value that doesn't resolve; this only ever adds a
    NEW way to succeed, never a new way to fail."""
    assert normalize_policy_number("py9999", _REAL_POLICY_NUMBERS) == "PY9999"
    assert normalize_policy_number("not-a-policy-number", _REAL_POLICY_NUMBERS) == (
        "NOT-A-POLICY-NUMBER"
    )
