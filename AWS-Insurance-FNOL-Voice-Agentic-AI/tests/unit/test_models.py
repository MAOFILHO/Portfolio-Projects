"""Stage 1 model tests. The strongest check here is validating the real Phase 3 synthetic corpus
against these schemas -- if the models don't match what's actually on disk, that's a real bug, not a
hypothetical one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fnol_voice_agent.models import (
    Claim,
    CheckClaimStatusSlots,
    FileAutoClaimSlots,
    Policyholder,
    TurnClassification,
    Vehicle,
)
from fnol_voice_agent.models.enums import CoverageQuestionType, Intent, LossType

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def test_all_synthetic_policyholders_validate() -> None:
    records = json.loads((DATA_DIR / "policyholders" / "policyholders.json").read_text())[
        "policyholders"
    ]
    assert len(records) == 6
    for record in records:
        Policyholder.model_validate(record)


def test_all_synthetic_vehicles_validate() -> None:
    records = json.loads((DATA_DIR / "vehicles" / "vehicles.json").read_text())["vehicles"]
    assert len(records) == 7
    for record in records:
        Vehicle.model_validate(record)


def test_all_synthetic_claims_validate() -> None:
    records = json.loads((DATA_DIR / "claims" / "claims.json").read_text())["claims"]
    assert len(records) == 8
    for record in records:
        Claim.model_validate(record)


def test_rental_worked_example_claim_matches_endorsements_md() -> None:
    records = json.loads((DATA_DIR / "claims" / "claims.json").read_text())["claims"]
    rental_claim = next(r for r in records if r["claim_number"] == "CLM-2608-00042-4")
    claim = Claim.model_validate(rental_claim)
    assert claim.rental is not None
    assert claim.rental.days_used == 12
    assert claim.rental.days_remaining == 8
    assert claim.rental.amount_remaining_cad == 400


def test_file_auto_claim_slots_requires_police_report_number_when_filed() -> None:
    base = dict(
        injuries_present=False,
        policy_number="PY4821",
        insured_vehicle_vin="9SYAB1239G1000101",
        loss_datetime="2026-07-27T08:15:00-04:00",
        loss_location="Highway 403 near Oakville, ON",
        loss_type=LossType.COLLISION,
        damage_description="Rear bumper damage",
        other_party_involved=False,
        police_report_filed=True,
        driver_name="Priya Nakamura",
    )
    with pytest.raises(ValidationError):
        FileAutoClaimSlots.model_validate(base)

    ok = FileAutoClaimSlots.model_validate({**base, "police_report_number": "2026-0727-014"})
    assert ok.relationship_to_insured == "Self"  # default


def test_check_claim_status_slots_requires_one_of_claim_or_policy_number() -> None:
    with pytest.raises(ValidationError):
        CheckClaimStatusSlots.model_validate({})
    CheckClaimStatusSlots.model_validate({"policy_number": "PY4821"})
    CheckClaimStatusSlots.model_validate({"claim_number": "CLM-2608-00042-4"})


def test_turn_classification_matches_prompt_registry_schema() -> None:
    tc = TurnClassification.model_validate(
        {
            "safety_flag": False,
            "intent": "CoverageQuestion",
            "intent_confidence": 0.92,
            "coverage_question_type": "election_fact_optional",
        }
    )
    assert tc.intent is Intent.COVERAGE_QUESTION
    assert tc.coverage_question_type is CoverageQuestionType.ELECTION_FACT_OPTIONAL


def test_turn_classification_defaults_coverage_question_type_to_not_applicable() -> None:
    tc = TurnClassification.model_validate(
        {"safety_flag": True, "intent": "InjuryEscalation", "intent_confidence": 1.0}
    )
    assert tc.coverage_question_type is CoverageQuestionType.NOT_APPLICABLE
