#!/usr/bin/env python3
"""Asserts that nothing which accrues cost survives, after `scripts/teardown.py`.

This is the check for a **partial** teardown — the one that removes the billable
resources but keeps the free infrastructure (S3 bucket, IAM roles, budget, log group,
GitHub OIDC plan role) so CI keeps working and a re-run needs no `terraform apply`.

Not to be confused with `scripts/verify_empty.py`, which is the P0 release gate for a
**full** teardown and additionally requires the bucket, the IAM role and the Terraform
state to be gone. Running that one after a partial teardown fails by design.

What actually costs money in this project:

    custom models          $1.95 / model / month, until deleted   <- the real cost
    CMoD deployments       $0.00/hr idle, token-billed in use
    provisioned throughput $60.50/hr -- must never exist at all
    S3 objects             fractions of a cent, but should be empty

Exits non-zero if any of the above survives, so it can gate a script or a demo teardown.
"""

import sys
from typing import Any

from botocore.exceptions import ClientError

from bedrock_platform.aws.naming import data_bucket_name
from bedrock_platform.aws.session import get_session
from bedrock_platform.config.settings import Settings


def find_billable_resources(bedrock: Any, s3: Any, bucket: str, region: str) -> list[str]:
    """Returns one message per surviving billable resource; empty means nothing costs money.

    Split out from main() so the detection path can be unit-tested against stubbed
    responses. A checker whose failure branch has never executed is not evidence that it
    would catch anything.
    """
    problems: list[str] = []

    deployments = bedrock.list_custom_model_deployments().get("modelDeploymentSummaries", [])
    models = bedrock.list_custom_models().get("modelSummaries", [])
    throughputs = bedrock.list_provisioned_model_throughputs().get("provisionedModelSummaries", [])

    print(f"Region: {region}")
    print(f"  custom model deployments : {len(deployments)}")
    for deployment in deployments:
        name = deployment["customModelDeploymentName"]
        print(f"      SURVIVING  {name}  ({deployment['status']})")
        problems.append(f"deployment {name} still exists")

    print(f"  custom models            : {len(models)}   (${1.95 * len(models):.2f}/month)")
    for model in models:
        print(f"      SURVIVING  {model['modelName']}")
        problems.append(f"custom model {model['modelName']} still exists")

    print(f"  provisioned throughputs  : {len(throughputs)}")
    for throughput in throughputs:
        # This should be impossible: nothing in this project can create one, and a unit
        # test forbids the API call. If one exists, it was created outside the project.
        print(f"      SURVIVING  {throughput.get('provisionedModelName')}  -- $60.50/hr")
        problems.append(f"provisioned throughput {throughput.get('provisionedModelName')} exists")

    # The bucket itself is retained by a partial teardown; only its contents should be gone.
    try:
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=5)
        object_count = response.get("KeyCount", 0)
        print(f"  objects in {bucket}: {object_count}")
        if object_count:
            problems.append(f"{object_count}+ objects remain in {bucket}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("NoSuchBucket", "404"):
            print(f"  bucket {bucket}: absent (full teardown was run)")
        else:
            raise

    return problems


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]  # values come from .env at runtime
    session = get_session()
    region = settings.aws_region
    bucket = data_bucket_name(settings.project_suffix, region)

    problems = find_billable_resources(
        session.client("bedrock"), session.client("s3"), bucket, region
    )

    print()
    if problems:
        print(f"{len(problems)} BILLABLE RESOURCE(S) SURVIVING:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)

    print("ZERO BILLABLE RESOURCES — recurring cost is $0.00/month.")
    print("Infrastructure (S3 bucket, IAM roles, budget, log group) is retained by design;")
    print("run `make teardown` for a full destroy, then scripts/verify_empty.py.")


if __name__ == "__main__":
    main()
