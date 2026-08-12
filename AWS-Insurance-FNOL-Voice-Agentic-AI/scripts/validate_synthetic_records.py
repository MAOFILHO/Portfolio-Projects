#!/usr/bin/env python3
"""Validate data/synthetic/{policyholders,vehicles,claims}.json for internal consistency.

Checks, each tied to a specific Phase 3 spec document:
  1. Every claim number's Luhn check digit is correct, per docs/phase3/DATA-CONTRACTS.md §1.
  2. Every VIN's check digit is a *deliberately* incorrect NHTSA check digit, per
     docs/phase3/DATA-CONTRACTS.md §3 -- fails loudly if one is accidentally valid.
  3. Referential integrity across the three files (policyholder <-> vehicle <-> claim).
  4. Every claim's total-loss flag and settlement amount match
     data/synthetic/policy/coverage-logic.md §§1-2's formulas exactly.

Exit code 0 and a summary line on success; a non-zero exit code and an itemized list on failure.
Run standalone: `python3 scripts/validate_synthetic_records.py`. No AWS dependency, no network access --
pure local computation, safe to run in CI (Phase 10) without any billable resource.

Luhn/VIN check-digit logic lives in `fnol_voice_agent.validation.identifiers` (Phase 5) -- imported here
rather than duplicated, so there is exactly one implementation of each algorithm.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fnol_voice_agent.validation.identifiers import (  # noqa: E402
    luhn_check_digit,
    vin_correct_check_digit,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"


def main() -> int:
    policyholders = json.loads((DATA_DIR / "policyholders" / "policyholders.json").read_text())[
        "policyholders"
    ]
    vehicles = json.loads((DATA_DIR / "vehicles" / "vehicles.json").read_text())["vehicles"]
    claims = json.loads((DATA_DIR / "claims" / "claims.json").read_text())["claims"]

    errors: list[str] = []

    claim_re = re.compile(r"^CLM-(\d{2})(\d{2})-(\d{5})-(\d)$")
    for c in claims:
        m = claim_re.match(c["claim_number"])
        if not m:
            errors.append(f"BAD FORMAT: {c['claim_number']}")
            continue
        yy, mm, seq, check = m.groups()
        expected = luhn_check_digit(yy + mm + seq)
        if str(expected) != check:
            errors.append(f"BAD CHECK DIGIT: {c['claim_number']} expected {expected}")

    for v in vehicles:
        vin = v["vin"]
        if len(vin) != 17:
            errors.append(f"VIN wrong length: {vin}")
            continue
        correct = vin_correct_check_digit(vin)
        if vin[8] == correct:
            errors.append(
                f"VIN {vin}: check digit is ACCIDENTALLY VALID ({vin[8]}) -- must be deliberately wrong"
            )

    veh_by_vin = {v["vin"]: v for v in vehicles}
    ph_by_policy = {p["policy_number"]: p for p in policyholders}

    for p in policyholders:
        for vin in p["vehicles"]:
            if vin not in veh_by_vin:
                errors.append(f"Policyholder {p['policy_number']} references missing VIN {vin}")
            elif veh_by_vin[vin]["policy_number"] != p["policy_number"]:
                errors.append(f"VIN {vin}: policy_number mismatch with its owning policyholder")

    for c in claims:
        if c["policy_number"] not in ph_by_policy:
            errors.append(
                f"Claim {c['claim_number']} references missing policy {c['policy_number']}"
            )
        veh = veh_by_vin.get(c["vin"])
        if veh is None:
            errors.append(f"Claim {c['claim_number']} references missing VIN {c['vin']}")
            continue
        if veh["policy_number"] != c["policy_number"]:
            errors.append(f"Claim {c['claim_number']}: VIN/policy mismatch")
        if veh["actual_cash_value_cad"] != c["actual_cash_value_cad"]:
            errors.append(f"Claim {c['claim_number']}: ACV mismatch with vehicle record")

        # data/synthetic/policy/coverage-logic.md §§1-2
        repair, acv, ded = (
            c["repair_estimate_cad"],
            c["actual_cash_value_cad"],
            c["deductible_applied_cad"],
        )
        tow = c.get("towing_allowance_cad") or 0
        is_total_loss = repair >= 0.80 * acv
        if is_total_loss != c["is_total_loss"]:
            errors.append(
                f"Claim {c['claim_number']}: total-loss flag mismatch (repair/acv={repair / acv:.3f})"
            )
        expected_settlement = (acv - ded) if c["is_total_loss"] else (min(repair, acv) - ded + tow)
        actual = (
            c["settlement_amount_cad"]
            if c["settlement_amount_cad"] is not None
            else c["estimated_settlement_cad"]
        )
        if actual != expected_settlement:
            errors.append(
                f"Claim {c['claim_number']}: settlement mismatch, expected {expected_settlement}, got {actual}"
            )

    if errors:
        print(f"{len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f" - {e}", file=sys.stderr)
        return 1

    print(
        f"All checks passed: {len(claims)} claims, {len(vehicles)} vehicles, {len(policyholders)} policyholders"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
