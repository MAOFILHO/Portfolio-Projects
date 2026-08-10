from bedrock_platform.aws.session import SUPPORTED_REGIONS, get_session
from bedrock_platform.config.settings import Settings


def test_resolved_region_matches_settings() -> None:
    session = get_session()
    assert session.region_name == Settings().aws_region


def test_configured_region_supports_customization() -> None:
    assert Settings().aws_region in SUPPORTED_REGIONS
