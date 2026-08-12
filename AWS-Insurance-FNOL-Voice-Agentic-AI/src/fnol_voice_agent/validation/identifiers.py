"""Identifier check-digit and format logic, per `docs/phase3/DATA-CONTRACTS.md`.

This is the canonical implementation -- `scripts/validate_synthetic_records.py` (Phase 3) imports the Luhn
and VIN functions from here rather than keeping its own copy, so there is exactly one implementation of each
algorithm, not two that could silently drift.
"""

from __future__ import annotations

import re

POLICY_NUMBER_RE = re.compile(r"^PY\d{4}$")
CLAIM_NUMBER_RE = re.compile(r"^CLM-(\d{2})(\d{2})-(\d{5})-(\d)$")
PLATE_RE = re.compile(r"^[A-Z]{3}-\d{4}$")
DRIVERS_LICENCE_RE = re.compile(r"^[A-Z]\d{8}$")
POLICE_REPORT_RE = re.compile(r"^\d{4}-\d{4}-\d{3}$")

_VIN_TRANSLITERATION = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
    "J": 1,
    "K": 2,
    "L": 3,
    "M": 4,
    "N": 5,
    "P": 7,
    "R": 9,
    "S": 2,
    "T": 3,
    "U": 4,
    "V": 5,
    "W": 6,
    "X": 7,
    "Y": 8,
    "Z": 9,
}
_VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def luhn_check_digit(payload_digits: str) -> int:
    """Standard Luhn (mod 10) check digit over an all-digit payload, per DATA-CONTRACTS.md §1's
    procedure: double every digit at an odd position counting from the right, sum, check digit is
    (10 - sum mod 10) mod 10."""
    if not payload_digits.isdigit():
        raise ValueError(f"payload must be digits only, got {payload_digits!r}")
    digits = [int(d) for d in payload_digits]
    n = len(digits)
    total = 0
    for i, d in enumerate(digits):
        pos_from_right = n - i
        if pos_from_right % 2 == 1:
            doubled = d * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += d
    return (10 - (total % 10)) % 10


def compute_claim_number(year_2digit: int, month_2digit: int, sequence: int) -> str:
    """Builds a full CLM-YYMM-NNNNN-C claim number, computing the Luhn check digit."""
    payload = f"{year_2digit:02d}{month_2digit:02d}{sequence:05d}"
    check = luhn_check_digit(payload)
    return f"CLM-{payload[:4]}-{payload[4:]}-{check}"


def verify_claim_number(claim_number: str) -> bool:
    """Format AND check-digit validation -- a caller reading a claim number back that fails this should
    trigger DATA-CONTRACTS.md's re-prompt-once-then-fallback recovery path, not a blind accept."""
    match = CLAIM_NUMBER_RE.match(claim_number)
    if not match:
        return False
    yy, mm, seq, check = match.groups()
    return luhn_check_digit(yy + mm + seq) == int(check)


def _vin_char_value(c: str) -> int:
    return int(c) if c.isdigit() else _VIN_TRANSLITERATION[c]


def vin_correct_check_digit(vin: str) -> str:
    """Computes the NHTSA weighted-sum-mod-11 check digit that *would* be correct for this VIN's other 16
    positions (position 9's actual character is ignored, per the standard algorithm)."""
    if len(vin) != 17:
        raise ValueError(f"VIN must be 17 characters, got {len(vin)}: {vin!r}")
    placeholder = vin[:8] + "0" + vin[9:]
    total = sum(_vin_char_value(c) * _VIN_WEIGHTS[i] for i, c in enumerate(placeholder))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def vin_is_deliberately_invalid(vin: str) -> bool:
    """True only if this VIN's check digit is genuinely wrong -- per CLAUDE.md's do-not-propagate rule
    (never a structurally-valid VIN), every synthetic VIN this project generates must satisfy this.
    """
    return vin[8] != vin_correct_check_digit(vin)


def validate_policy_number(value: str) -> bool:
    return bool(POLICY_NUMBER_RE.match(value))


def validate_plate(value: str) -> bool:
    return bool(PLATE_RE.match(value))


def validate_drivers_licence(value: str) -> bool:
    return bool(DRIVERS_LICENCE_RE.match(value))


def validate_police_report_number(value: str) -> bool:
    return bool(POLICE_REPORT_RE.match(value))
