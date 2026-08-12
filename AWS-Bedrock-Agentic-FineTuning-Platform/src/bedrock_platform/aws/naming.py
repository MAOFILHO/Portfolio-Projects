"""Deterministic resource names shared between the CLI pipeline and the API.

Idempotency comes from these stable names, never from runtime rename-on-collision logic.
"""

import boto3


def data_bucket_name(project_suffix: str, aws_region: str) -> str:
    """Region is part of the name because S3 bucket names are globally unique while
    buckets are regional, and Bedrock requires the training bucket to be in the same
    Region as the customization job. The supported Region differs per base model
    (Nova: us-east-1, Llama 3.3: us-west-2), so the project must be able to hold one
    bucket per Region rather than deleting and re-creating a single shared name.

    Must stay in sync with infra/terraform/modules/s3_data/main.tf.
    """
    return f"bedrock-platform-{project_suffix}-data-{aws_region}"


def deployment_name(project_suffix: str, scenario_id: str) -> str:
    return f"{project_suffix}-{scenario_id}-deploy"


def bedrock_role_arn(session: boto3.Session, project_suffix: str) -> str:
    account_id = session.client("sts").get_caller_identity()["Account"]
    return f"arn:aws:iam::{account_id}:role/bedrock-platform-{project_suffix}-customization-role"
