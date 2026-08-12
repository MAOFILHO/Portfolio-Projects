import boto3
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from bedrock_platform.api.deps import get_boto_session, get_enabled_scenario
from bedrock_platform.aws.inference_client import InferenceClient, InferenceResult
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.validation.schema_guard import validate_output
from bedrock_platform.validation.violation import SchemaViolation

router = APIRouter()


class InferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    deployment_arn: str


class InferCompareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: InferenceResult
    tuned: InferenceResult
    schema_valid: bool | None
    violation: SchemaViolation | None


@router.post("/infer/{scenario_id}", response_model=InferCompareResponse)
def compare_inference(
    request: InferRequest,
    scenario: ScenarioConfig = Depends(get_enabled_scenario),
    session: boto3.Session = Depends(get_boto_session),
) -> InferCompareResponse:
    inference_client = InferenceClient(session=session)
    base = inference_client.invoke_base_model(
        scenario.base_inference_model_id,
        scenario.system_prompt,
        request.prompt,
        scenario.max_output_tokens,
    )
    tuned = inference_client.invoke_tuned_model(
        request.deployment_arn,
        scenario.system_prompt,
        request.prompt,
        scenario.max_output_tokens,
    )

    verdict = validate_output(scenario, tuned.text) if scenario.output_schema_ref else None
    violation = verdict if isinstance(verdict, SchemaViolation) else None
    schema_valid = None if verdict is None else violation is None

    return InferCompareResponse(
        base=base, tuned=tuned, schema_valid=schema_valid, violation=violation
    )
