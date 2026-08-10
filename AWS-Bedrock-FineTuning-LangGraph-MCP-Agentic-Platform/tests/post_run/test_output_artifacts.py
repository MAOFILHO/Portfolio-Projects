import os

from bedrock_platform.aws.naming import data_bucket_name
from bedrock_platform.aws.s3_client import S3Client
from bedrock_platform.aws.session import get_session


def test_output_artifacts_are_nonempty(run_results: dict) -> None:
    suffix = os.environ["PROJECT_SUFFIX"]
    bucket = data_bucket_name(suffix, os.environ["AWS_REGION"])
    client = S3Client(bucket=bucket, session=get_session())

    artifacts = client.list_output_artifacts(run_results["_scenario_id"])
    assert len(artifacts) > 0
