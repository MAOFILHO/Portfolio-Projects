import os

import boto3
import pytest

from bedrock_platform.aws.session import get_session

# The state bucket and lock table are Terraform *backend* resources, not workload
# resources. They live wherever the backend is configured, independent of the Region the
# platform runs in. Must stay in sync with the hardcoded region in
# infra/terraform/backend.tf.
TERRAFORM_BACKEND_REGION = "us-east-1"


def _suffix() -> str:
    suffix = os.environ.get("PROJECT_SUFFIX")
    if not suffix:
        pytest.skip("PROJECT_SUFFIX not set")
    return suffix


def test_dynamodb_lock_table_is_pay_per_request() -> None:
    client = boto3.client("dynamodb", region_name=TERRAFORM_BACKEND_REGION)
    response = client.describe_table(TableName=f"bedrock-platform-{_suffix()}-tflock")
    billing_mode = response["Table"].get("BillingModeSummary", {}).get("BillingMode")
    assert billing_mode == "PAY_PER_REQUEST"
    print("dynamodb billing mode: PAY_PER_REQUEST")


def test_log_group_retention_is_seven_days() -> None:
    # Unlike the lock table, the log group is a workload resource created by the
    # observability module under `provider "aws" { region = var.aws_region }`, so it must
    # exist in the configured Region.
    client = get_session().client("logs")
    response = client.describe_log_groups(logGroupNamePrefix=f"/bedrock-platform/{_suffix()}")
    groups = response["logGroups"]
    assert groups, (
        "log group not found in the configured Region — see docs/INCIDENT-LOG.md; "
        "the observability module has not been re-applied since the Region change"
    )
    assert groups[0]["retentionInDays"] == 7
