import importlib
import json

from pydantic import BaseModel, ValidationError

from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.validation.violation import SchemaViolation


def _load_output_model(output_schema_ref: str) -> type[BaseModel]:
    module_path, class_name = output_schema_ref.rsplit(".", 1)
    module = importlib.import_module(module_path)
    model_cls: type[BaseModel] = getattr(module, class_name)
    return model_cls


def validate_output(scenario: ScenarioConfig, raw_text: str) -> BaseModel | SchemaViolation:
    """Parses raw model output against the scenario's Pydantic output model.

    Never raises — a mismatch is returned as a SchemaViolation for the caller (the API
    request path, the pipeline script) to surface as a demonstrated feature.
    """
    if scenario.output_schema_ref is None:
        return SchemaViolation(
            raw_text=raw_text,
            error_path="<no output_schema_ref configured>",
            expected_schema=f"{scenario.id} has no strict output schema",
        )

    model_cls = _load_output_model(scenario.output_schema_ref)

    if scenario.output_mode == "strict_json":
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            return SchemaViolation(
                raw_text=raw_text,
                error_path=f"json.loads: {exc}",
                expected_schema=json.dumps(model_cls.model_json_schema()),
            )
    else:
        payload = {"text": raw_text}

    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        error_path = ".".join(str(p) for p in first_error["loc"]) or "<root>"
        return SchemaViolation(
            raw_text=raw_text,
            error_path=f"{error_path}: {first_error['msg']}",
            expected_schema=json.dumps(model_cls.model_json_schema()),
        )
