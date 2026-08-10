import os

import boto3
import pytest

from bedrock_platform.aws.naming import data_bucket_name

BUCKET_NAME_ENV = "PROJECT_SUFFIX"


def _bucket_name() -> str:
    suffix = os.environ.get(BUCKET_NAME_ENV)
    if not suffix:
        pytest.skip(f"{BUCKET_NAME_ENV} not set")
    return data_bucket_name(suffix, _region())


def _region() -> str:
    region = os.environ.get("AWS_REGION")
    if not region:
        pytest.skip("AWS_REGION not set")
    return region


def test_bucket_exists() -> None:
    client = boto3.client("s3", region_name=_region())
    client.head_bucket(Bucket=_bucket_name())


def test_public_access_fully_blocked() -> None:
    client = boto3.client("s3", region_name=_region())
    response = client.get_public_access_block(Bucket=_bucket_name())
    config = response["PublicAccessBlockConfiguration"]
    assert config["BlockPublicAcls"] is True
    assert config["BlockPublicPolicy"] is True
    assert config["IgnorePublicAcls"] is True
    assert config["RestrictPublicBuckets"] is True
    print("bucket public access: BLOCKED")
