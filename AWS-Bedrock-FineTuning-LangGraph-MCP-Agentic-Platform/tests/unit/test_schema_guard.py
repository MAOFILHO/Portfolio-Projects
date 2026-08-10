import json

from bedrock_platform.config.scenario_loader import load_scenarios
from bedrock_platform.validation.schema_guard import validate_output
from bedrock_platform.validation.violation import SchemaViolation


def _scenario(scenario_id: str):
    for s in load_scenarios():
        if s.id == scenario_id:
            return s
    raise AssertionError(f"scenario {scenario_id!r} not found")


def test_pharma_valid_json_parses_cleanly() -> None:
    scenario = _scenario("pharma")
    raw = json.dumps(
        {"seriousness": "Serious", "event_category": "Neurological", "expedited_reporting": True}
    )
    result = validate_output(scenario, raw)
    assert not isinstance(result, SchemaViolation)
    assert result.seriousness == "Serious"


def test_pharma_malformed_json_is_caught_as_violation() -> None:
    scenario = _scenario("pharma")
    result = validate_output(scenario, "not json at all")
    assert isinstance(result, SchemaViolation)
    assert "json.loads" in result.error_path


def test_pharma_contradiction_is_caught_as_violation() -> None:
    scenario = _scenario("pharma")
    raw = json.dumps(
        {"seriousness": "Non-serious", "event_category": "Rash", "expedited_reporting": True}
    )
    result = validate_output(scenario, raw)
    assert isinstance(result, SchemaViolation)


def test_banking_prose_scenario_has_no_strict_schema_configured() -> None:
    scenario = _scenario("banking")
    assert scenario.output_schema_ref is None
    result = validate_output(scenario, "Transfers may take 1-3 business days.")
    assert isinstance(result, SchemaViolation)
    assert "no output_schema_ref configured" in result.error_path
