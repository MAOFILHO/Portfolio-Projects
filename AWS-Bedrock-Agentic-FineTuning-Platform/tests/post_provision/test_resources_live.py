import os

import boto3
import pytest


def test_bedrock_role_trust_policy_names_bedrock_service() -> None:
    suffix = os.environ.get("PROJECT_SUFFIX")
    if not suffix:
        pytest.skip("PROJECT_SUFFIX not set")

    client = boto3.client("iam")
    role_name = f"bedrock-platform-{suffix}-customization-role"
    response = client.get_role(RoleName=role_name)
    trust_policy = response["Role"]["AssumeRolePolicyDocument"]
    principals = [
        stmt["Principal"].get("Service")
        for stmt in trust_policy["Statement"]
        if "Principal" in stmt
    ]
    flat_principals = []
    for p in principals:
        if isinstance(p, list):
            flat_principals.extend(p)
        elif p:
            flat_principals.append(p)
    assert "bedrock.amazonaws.com" in flat_principals
