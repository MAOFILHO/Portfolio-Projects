FORBIDDEN_STRINGS = [
    "ProvisionedThroughput",
    "aws_bedrock_provisioned_model_throughput",
    "create_provisioned_model_throughput",
]


class ForbiddenResourceError(Exception):
    """Raised when a code path attempts to create Bedrock Provisioned Throughput.

    Provisioned Throughput bills hourly with no free tier: $60.50/hr/model, which is
    $130,680/month for three models. This project uses Custom Model on-Demand (CMoD)
    exclusively — token-billed, $0 when idle.
    """


def assert_not_provisioned_throughput(candidate: str) -> None:
    for forbidden in FORBIDDEN_STRINGS:
        if forbidden in candidate:
            raise ForbiddenResourceError(
                f"Forbidden string {forbidden!r} detected in {candidate!r}. "
                "Provisioned Throughput is never permitted in this project."
            )
