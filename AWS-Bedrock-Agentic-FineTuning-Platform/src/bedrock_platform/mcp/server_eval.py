"""MCP tool for scoring model output. Read-only, pure Python, no AWS calls.

Scoring is deliberately split by what the scenario actually promises:

- **strict_json** scenarios are scored on schema validity through the scenario's Pydantic
  model. A caught violation is a successful demo outcome, not an error.
- **prose / numbered_steps / short_copy** scenarios have no parseable schema, so they are
  scored on rule compliance against literal contract strings drawn from the scenario's own
  system prompt.

Measuring a prose scenario by schema validity would report 100% for every model and
distinguish nothing — the finding recorded in docs/RESULTS.md.
"""

import re

from pydantic import BaseModel, ConfigDict

from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.scenario_loader import load_scenarios
from bedrock_platform.validation.schema_guard import validate_output
from bedrock_platform.validation.violation import SchemaViolation

EVAL_TOOLS: tuple[str, ...] = ("score_output",)

MIN_NUMBERED_STEPS = 2


class ScoreOutputInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    raw_text: str
    # Literal strings the answer must contain, from the scenario's contract. Supplied by
    # the caller rather than inferred, so the metric is stated up front and auditable.
    required_phrases: list[str] = []
    forbidden_phrases: list[str] = []


class ScoreOutputResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    output_mode: str
    schema_valid: bool | None
    violation_path: str | None
    numbered_step_count: int
    required_phrases_present: bool
    forbidden_phrases_absent: bool
    compliant: bool


def _scenario(scenario_id: str) -> ScenarioConfig:
    for scenario in load_scenarios():
        if scenario.id == scenario_id:
            return scenario
    raise ValueError(f"unknown scenario id {scenario_id!r}")


def _numbered_steps(text: str) -> int:
    return len(re.findall(r"(?m)^\s*\d+[.)]\s", text))


def score_output(payload: ScoreOutputInput) -> ScoreOutputResult:
    scenario = _scenario(payload.scenario_id)
    text = payload.raw_text

    schema_valid: bool | None = None
    violation_path: str | None = None
    if scenario.output_schema_ref is not None:
        verdict = validate_output(scenario, text)
        if isinstance(verdict, SchemaViolation):
            schema_valid = False
            violation_path = verdict.error_path
        else:
            schema_valid = True

    required_ok = all(phrase in text for phrase in payload.required_phrases)
    forbidden_ok = all(phrase not in text for phrase in payload.forbidden_phrases)
    steps = _numbered_steps(text)

    if scenario.output_mode == "strict_json":
        compliant = bool(schema_valid) and required_ok and forbidden_ok
    elif scenario.output_mode == "numbered_steps":
        compliant = steps >= MIN_NUMBERED_STEPS and required_ok and forbidden_ok
    else:
        compliant = required_ok and forbidden_ok

    return ScoreOutputResult(
        scenario_id=scenario.id,
        output_mode=scenario.output_mode,
        schema_valid=schema_valid,
        violation_path=violation_path,
        numbered_step_count=steps,
        required_phrases_present=required_ok,
        forbidden_phrases_absent=forbidden_ok,
        compliant=compliant,
    )
