#!/usr/bin/env python3
"""Ordered AWS-level teardown: deployments -> custom models -> S3 objects.

Run before `terraform destroy` (the Makefile `teardown` target does both, in
this order). Safe to run against an account with nothing live in it.
"""

from bedrock_platform.aws.deployment_client import DeploymentClient
from bedrock_platform.aws.finetune_client import FinetuneClient
from bedrock_platform.aws.naming import data_bucket_name
from bedrock_platform.aws.s3_client import S3Client
from bedrock_platform.aws.session import get_session
from bedrock_platform.aws.teardown import ordered_teardown
from bedrock_platform.config.settings import Settings


def main() -> None:
    settings = Settings()
    session = get_session()

    deployment_client = DeploymentClient(session=session)
    finetune_client = FinetuneClient(project_suffix=settings.project_suffix, session=session)
    # Must go through naming.data_bucket_name — the bucket name is Region-suffixed, and
    # hardcoding the unsuffixed form here silently pointed teardown at a bucket that does
    # not exist, reporting a clean teardown while the real bucket kept its objects.
    data_bucket = data_bucket_name(settings.project_suffix, settings.aws_region)
    s3_client = S3Client(bucket=data_bucket, session=session)
    print(f"Data bucket: {data_bucket}")

    print(f"Tearing down AWS resources for project_suffix={settings.project_suffix!r}...")
    print("Step 1/3: deleting custom model deployments...")
    print("Step 2/3: deleting custom models...")
    print("Step 3/3: emptying data bucket (all versions + delete markers)...")

    results = ordered_teardown(deployment_client, finetune_client, s3_client)

    print()
    print(f"Deployments deleted: {results['deployments_deleted']}")
    print(f"Custom models deleted: {results['models_deleted']}")
    print(f"S3 objects/versions deleted: {results['objects_deleted']}")
    print()
    print("AWS-level teardown complete. Proceeding to `terraform destroy`.")


if __name__ == "__main__":
    main()
