from bedrock_platform.aws.deployment_client import DeploymentClient
from bedrock_platform.aws.session import get_session


def test_deployment_is_active(run_results: dict) -> None:
    client = DeploymentClient(session=get_session())
    deployment = client.get_custom_model_deployment(run_results["deployment_arn"])
    assert deployment["status"] == "Active"
