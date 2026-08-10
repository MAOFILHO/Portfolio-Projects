from bedrock_platform.aws.session import get_session

# "Custom models with a creating status per account" is the live quota AWS uses to gate
# in-progress custom model deployments (verified live == 2 on this account).
QUOTA_CODE_IN_PROGRESS_DEPLOYMENTS = "L-C02E1E99"
EXPECTED_MIN_QUOTA = 2


def test_in_progress_deployment_quota_at_least_two() -> None:
    # Bedrock quotas are per-Region; querying us-east-1 would report a limit that does
    # not govern jobs running in the configured Region.
    client = get_session().client("service-quotas")
    response = client.get_service_quota(
        ServiceCode="bedrock", QuotaCode=QUOTA_CODE_IN_PROGRESS_DEPLOYMENTS
    )
    assert response["Quota"]["Value"] >= EXPECTED_MIN_QUOTA
