import pytest
from pydantic import ValidationError

from bedrock_platform.models.outputs.patient_triage import PatientTriageOutput
from bedrock_platform.models.outputs.pharma import PharmaTriageOutput
from bedrock_platform.models.outputs.support_triage import SupportTriageOutput

STRICT_JSON_MODELS = [PharmaTriageOutput, SupportTriageOutput, PatientTriageOutput]

VALID_PAYLOADS = {
    PharmaTriageOutput: {
        "seriousness": "Serious",
        "event_category": "Cardiac",
        "expedited_reporting": True,
    },
    SupportTriageOutput: {"category": "Billing", "priority": "P2", "team": "Finance-Ops"},
    PatientTriageOutput: {
        "department": "Cardiology",
        "urgency": "Emergency",
        "action": "Advise the patient to call emergency services (911) immediately.",
    },
}


@pytest.mark.parametrize("model", STRICT_JSON_MODELS)
def test_valid_payload_parses(model: type) -> None:
    model.model_validate(VALID_PAYLOADS[model])


@pytest.mark.parametrize("model", STRICT_JSON_MODELS)
def test_rejects_extra_key(model: type) -> None:
    payload = {**VALID_PAYLOADS[model], "unexpected_field": "x"}
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_pharma_rejects_wrong_enum_value() -> None:
    payload = {**VALID_PAYLOADS[PharmaTriageOutput], "seriousness": "Very-Serious"}
    with pytest.raises(ValidationError):
        PharmaTriageOutput.model_validate(payload)


def test_support_triage_rejects_wrong_enum_value() -> None:
    payload = {**VALID_PAYLOADS[SupportTriageOutput], "priority": "P0"}
    with pytest.raises(ValidationError):
        SupportTriageOutput.model_validate(payload)


def test_patient_triage_rejects_wrong_enum_value() -> None:
    payload = {**VALID_PAYLOADS[PatientTriageOutput], "urgency": "Critical"}
    with pytest.raises(ValidationError):
        PatientTriageOutput.model_validate(payload)


def test_pharma_expedited_seriousness_contradiction() -> None:
    payload = {
        "seriousness": "Non-serious",
        "event_category": "Cardiac",
        "expedited_reporting": True,
    }
    with pytest.raises(ValidationError):
        PharmaTriageOutput.model_validate(payload)


def test_patient_triage_emergency_requires_emergency_action() -> None:
    payload = {
        "department": "Cardiology",
        "urgency": "Emergency",
        "action": "Schedule a routine follow-up appointment.",
    }
    with pytest.raises(ValidationError):
        PatientTriageOutput.model_validate(payload)
