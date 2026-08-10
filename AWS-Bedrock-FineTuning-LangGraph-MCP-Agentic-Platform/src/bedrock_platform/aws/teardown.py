import time
from collections.abc import Callable

from botocore.exceptions import ClientError

from bedrock_platform.aws.deployment_client import DeploymentClient
from bedrock_platform.aws.finetune_client import FinetuneClient
from bedrock_platform.aws.s3_client import S3Client

POLL_INTERVAL_SECONDS = 15
MAX_WAIT_SECONDS = 1800


class TeardownTimeoutError(Exception):
    """Raised when a resource doesn't disappear within the polling budget."""


def _wait_until_gone(check_exists: Callable[[], bool], resource_label: str) -> None:
    waited = 0
    while check_exists():
        if waited >= MAX_WAIT_SECONDS:
            raise TeardownTimeoutError(
                f"{resource_label} did not disappear within {MAX_WAIT_SECONDS}s."
            )
        time.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS


def delete_all_deployments(client: DeploymentClient) -> int:
    """Step 1: delete every CMoD deployment, waiting for each to actually disappear."""
    deployments = client.list_custom_model_deployments()
    for deployment in deployments:
        arn = deployment["modelDeploymentArn"]
        try:
            client.delete_custom_model_deployment(arn)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        def _still_exists(arn: str = arn) -> bool:
            try:
                client.get_custom_model_deployment(arn)
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ResourceNotFoundException":
                    return False
                raise

        _wait_until_gone(_still_exists, f"deployment {arn}")

    return len(deployments)


def delete_all_custom_models(client: FinetuneClient) -> int:
    """Step 2: delete every custom model, only after all deployments referencing it are gone."""
    models = client.list_custom_models()
    for model in models:
        arn = model["modelArn"]
        try:
            client.delete_custom_model(arn)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceNotFoundException":
                raise

        def _still_exists(arn: str = arn) -> bool:
            return any(m["modelArn"] == arn for m in client.list_custom_models())

        _wait_until_gone(_still_exists, f"custom model {arn}")

    return len(models)


def empty_data_bucket(client: S3Client) -> int:
    """Step 3: delete every object version and delete marker from the data bucket."""
    return client.empty_bucket()


def ordered_teardown(
    deployment_client: DeploymentClient,
    finetune_client: FinetuneClient,
    s3_client: S3Client,
) -> dict[str, int]:
    """Runs the mandatory teardown order: deployments -> custom models -> S3 objects.

    Reversing this order hangs the destroy: a deployment referencing a model blocks
    model deletion, and terraform destroy on a non-empty bucket fails.
    """
    deployments_deleted = delete_all_deployments(deployment_client)
    models_deleted = delete_all_custom_models(finetune_client)
    objects_deleted = empty_data_bucket(s3_client)

    return {
        "deployments_deleted": deployments_deleted,
        "models_deleted": models_deleted,
        "objects_deleted": objects_deleted,
    }
