import boto3
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from bedrock_platform.api.deps import get_boto_session, get_enabled_scenario, get_settings
from bedrock_platform.aws.deployment_client import DeploymentClient
from bedrock_platform.aws.naming import deployment_name
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.settings import Settings

router = APIRouter()


class DeployRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custom_model_arn: str


class DeployResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deployment_arn: str


class DeploymentStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    failure_message: str | None = None


@router.post("/deploy/{scenario_id}", response_model=DeployResponse)
def create_deployment(
    request: DeployRequest,
    scenario: ScenarioConfig = Depends(get_enabled_scenario),
    settings: Settings = Depends(get_settings),
    session: boto3.Session = Depends(get_boto_session),
) -> DeployResponse:
    deployment_client = DeploymentClient(session=session)
    name = deployment_name(settings.project_suffix, scenario.id)

    # Reuse an Active deployment of the same model rather than creating a second one.
    # Custom Model on-Demand deployments are $0/hr idle, so a live one is worth keeping;
    # creating again under the same name fails outright, and creating under a new name
    # would orphan the old deployment, which then holds the model open against teardown.
    # Without this the UI wizard is unusable for anyone who has already run the pipeline.
    for existing in deployment_client.list_custom_model_deployments():
        if existing["modelArn"] == request.custom_model_arn and existing["status"] == "Active":
            return DeployResponse(deployment_arn=existing["customModelDeploymentArn"])

    response = deployment_client.create_custom_model_deployment(name, request.custom_model_arn)
    return DeployResponse(deployment_arn=response["customModelDeploymentArn"])


@router.get("/deploy/{scenario_id}/status", response_model=DeploymentStatusResponse)
def get_deployment_status(
    deployment_arn: str,
    session: boto3.Session = Depends(get_boto_session),
) -> DeploymentStatusResponse:
    deployment_client = DeploymentClient(session=session)
    deployment = deployment_client.get_custom_model_deployment(deployment_arn)
    return DeploymentStatusResponse(
        status=deployment["status"],
        failure_message=deployment.get("failureMessage"),
    )
