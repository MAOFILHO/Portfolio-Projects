#!/usr/bin/env python3
"""Asserts the account and terraform state are truly empty after teardown.

Checks: zero custom model deployments, zero custom models, data bucket absent,
IAM bedrock role absent, `terraform state list` empty. Exits non-zero on any
surviving resource.
"""

import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from bedrock_platform.aws.naming import data_bucket_name
from bedrock_platform.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform"


def check_zero_deployments(bedrock) -> list[str]:
    problems = []
    deployments = []
    paginator = bedrock.get_paginator("list_custom_model_deployments")
    for page in paginator.paginate():
        deployments.extend(page.get("modelDeploymentSummaries", []))
    if deployments:
        problems.append(f"{len(deployments)} custom model deployment(s) still exist")
    return problems


def check_zero_custom_models(bedrock) -> list[str]:
    problems = []
    models = []
    paginator = bedrock.get_paginator("list_custom_models")
    for page in paginator.paginate():
        models.extend(page.get("modelSummaries", []))
    if models:
        problems.append(f"{len(models)} custom model(s) still exist")
    return problems


def check_bucket_absent(s3, bucket_name: str) -> list[str]:
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            return []
        raise
    return [f"data bucket {bucket_name!r} still exists"]


def check_iam_role_absent(iam, role_name: str) -> list[str]:
    try:
        iam.get_role(RoleName=role_name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchEntity":
            return []
        raise
    return [f"IAM role {role_name!r} still exists"]


def check_terraform_state_empty() -> list[str]:
    result = subprocess.run(
        ["terraform", "state", "list"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return [f"`terraform state list` failed: {result.stderr.strip()}"]
    remaining = [line for line in result.stdout.splitlines() if line.strip()]
    if remaining:
        return [f"terraform state is non-empty: {remaining}"]
    return []


def main() -> None:
    settings = Settings()
    session = boto3.Session(region_name=settings.aws_region)
    bedrock = session.client("bedrock")
    s3 = session.client("s3")
    iam = session.client("iam")

    # Region-suffixed via naming.data_bucket_name. Building the name inline here made the
    # check probe a bucket that never existed, so head_bucket returned 404 and the release
    # gate passed while the real bucket was still present.
    bucket_name = data_bucket_name(settings.project_suffix, settings.aws_region)
    role_name = f"bedrock-platform-{settings.project_suffix}-customization-role"

    problems: list[str] = []
    problems += check_zero_deployments(bedrock)
    problems += check_zero_custom_models(bedrock)
    problems += check_bucket_absent(s3, bucket_name)
    problems += check_iam_role_absent(iam, role_name)
    problems += check_terraform_state_empty()

    if problems:
        print("SURVIVING RESOURCES FOUND ❌")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    print("ZERO SURVIVING RESOURCES ✅")


if __name__ == "__main__":
    main()
