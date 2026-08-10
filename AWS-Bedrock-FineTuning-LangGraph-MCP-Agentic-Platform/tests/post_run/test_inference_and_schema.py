from bedrock_platform.config.scenario_loader import load_scenarios


def _scenario(scenario_id: str):
    for s in load_scenarios():
        if s.id == scenario_id:
            return s
    raise AssertionError(f"scenario {scenario_id!r} not found")


def test_tuned_inference_returns_nonempty_text(run_results: dict) -> None:
    assert len(run_results["results"]) > 0
    for entry in run_results["results"]:
        assert entry["tuned"]["text"].strip() != ""


def test_strict_json_scenarios_parse_or_produce_violation(run_results: dict) -> None:
    scenario = _scenario(run_results["_scenario_id"])
    if scenario.output_mode != "strict_json":
        return

    for entry in run_results["results"]:
        # Either the output parsed cleanly (schema_valid True) or a SchemaViolation
        # was captured (schema_valid False, verdict populated) — never neither.
        assert entry["schema_valid"] is not None
        assert entry["verdict"] is not None
