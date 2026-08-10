import boto3

from bedrock_platform.config.settings import Settings

# Bedrock model customization exists in exactly two Regions, and each supports a
# different set of base models for Custom Model on-Demand (Nova: us-east-1,
# Llama 3.3 70B: us-west-2). Must stay in sync with the validation block in
# infra/terraform/variables.tf.
SUPPORTED_REGIONS = ("us-east-1", "us-west-2")


def get_session(profile: str | None = None) -> boto3.Session:
    """Builds a session pinned to the configured Region.

    The Region comes from Settings (AWS_REGION in .env), never from the ambient
    AWS CLI config — a stale ~/.aws/config region would otherwise silently point
    every client at the wrong Region, where the custom model does not exist.
    """
    settings = Settings()  # type: ignore[call-arg]  # values come from .env at runtime
    region = settings.aws_region

    if region not in SUPPORTED_REGIONS:
        raise RuntimeError(
            f"AWS_REGION is {region!r}, which does not support Bedrock model "
            f"customization. Supported: {', '.join(SUPPORTED_REGIONS)}."
        )

    session = boto3.Session(
        profile_name=profile or settings.aws_profile,
        region_name=region,
    )
    resolved_region = session.region_name
    if resolved_region != region:
        raise RuntimeError(f"Resolved AWS region is {resolved_region!r}, expected {region!r}.")
    return session
