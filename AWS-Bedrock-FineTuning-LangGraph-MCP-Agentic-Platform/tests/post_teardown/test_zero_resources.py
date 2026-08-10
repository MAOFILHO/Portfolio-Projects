import importlib.util
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from bedrock_platform.aws.finetune_client import FinetuneClient
from bedrock_platform.aws.teardown import delete_all_custom_models

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERIFY_EMPTY_PATH = REPO_ROOT / "scripts" / "verify_empty.py"
BASE_MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-2-lite-v1:0:256k"

_spec = importlib.util.spec_from_file_location("verify_empty", VERIFY_EMPTY_PATH)
verify_empty = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_empty)


def test_zero_deployments_check_passes_when_list_is_empty() -> None:
    client = boto3.client("bedrock", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response("list_custom_model_deployments", {"modelDeploymentSummaries": []}, {})
    stubber.activate()
    assert verify_empty.check_zero_deployments(client) == []
    stubber.deactivate()


def test_zero_custom_models_check_flags_survivors() -> None:
    client = boto3.client("bedrock", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "list_custom_models",
        {
            "modelSummaries": [
                {
                    "modelArn": "arn:aws:bedrock:us-east-1:123:custom-model/x",
                    "modelName": "marco-demo01-pharma-ft",
                    "creationTime": "2026-01-01T00:00:00Z",
                    "baseModelArn": BASE_MODEL_ARN,
                    "baseModelName": "amazon.nova-2-lite-v1:0:256k",
                }
            ]
        },
        {},
    )
    stubber.activate()
    problems = verify_empty.check_zero_custom_models(client)
    assert len(problems) == 1
    assert "custom model" in problems[0]
    stubber.deactivate()


def test_bucket_absent_check_passes_on_404() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_client_error("head_bucket", service_error_code="404", http_status_code=404)
    stubber.activate()
    assert verify_empty.check_bucket_absent(client, "bedrock-platform-marco-demo01-data") == []
    stubber.deactivate()


def test_bucket_still_exists_is_flagged() -> None:
    client = boto3.client("s3", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response("head_bucket", {})
    stubber.activate()
    problems = verify_empty.check_bucket_absent(client, "bedrock-platform-marco-demo01-data")
    assert len(problems) == 1
    stubber.deactivate()


def test_iam_role_absent_check_passes_on_no_such_entity() -> None:
    client = boto3.client("iam", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_client_error("get_role", service_error_code="NoSuchEntity", http_status_code=404)
    stubber.activate()
    role_name = "bedrock-platform-marco-demo01-customization-role"
    assert verify_empty.check_iam_role_absent(client, role_name) == []
    stubber.deactivate()


def test_deleting_referenced_custom_model_raises_instead_of_hanging() -> None:
    """Ordering regression test: if a deployment still references a custom model,
    delete_custom_model must surface the conflict immediately rather than being
    swallowed into an infinite existence-poll loop."""
    client = boto3.client("bedrock", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "list_custom_models",
        {
            "modelSummaries": [
                {
                    "modelArn": "arn:aws:bedrock:us-east-1:123:custom-model/x",
                    "modelName": "marco-demo01-pharma-ft",
                    "creationTime": "2026-01-01T00:00:00Z",
                    "baseModelArn": BASE_MODEL_ARN,
                    "baseModelName": "amazon.nova-2-lite-v1:0:256k",
                }
            ]
        },
        {},
    )
    stubber.add_client_error(
        "delete_custom_model",
        service_error_code="ConflictException",
        service_message="Model is referenced by an active deployment.",
        http_status_code=409,
    )
    stubber.activate()

    finetune_client = FinetuneClient(project_suffix="marco-demo01", session=boto3.Session())
    finetune_client._bedrock = client

    with pytest.raises(ClientError) as exc_info:
        delete_all_custom_models(finetune_client)

    assert exc_info.value.response["Error"]["Code"] == "ConflictException"
    stubber.deactivate()
