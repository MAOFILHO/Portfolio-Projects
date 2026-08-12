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
    # "Hepatobiliary" is one of the 8 controlled-vocabulary terms. This fixture previously
    # used "Neurological", which is NOT in the vocabulary — it passed only because
    # event_category was typed as a bare str, so the test was asserting the wrong thing.
    raw = json.dumps(
        {"seriousness": "Serious", "event_category": "Hepatobiliary", "expedited_reporting": True}
    )
    result = validate_output(scenario, raw)
    assert not isinstance(result, SchemaViolation)
    assert result.seriousness == "Serious"


def test_pharma_out_of_vocabulary_category_is_caught_as_violation() -> None:
    """The distinction the strict schema exists to make: syntactically perfect JSON whose
    category the downstream enum would reject."""
    scenario = _scenario("pharma")
    raw = json.dumps(
        {"seriousness": "Serious", "event_category": "Neurological", "expedited_reporting": True}
    )
    result = validate_output(scenario, raw)
    assert isinstance(result, SchemaViolation)
    assert "event_category" in result.error_path


def test_pharma_category_is_case_sensitive() -> None:
    """A near-miss on casing is still a parse failure downstream — the base model produced
    exactly this ('hepatobiliary') and the loose schema called it valid."""
    scenario = _scenario("pharma")
    raw = json.dumps(
        {"seriousness": "Serious", "event_category": "hepatobiliary", "expedited_reporting": True}
    )
    result = validate_output(scenario, raw)
    assert isinstance(result, SchemaViolation)


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
