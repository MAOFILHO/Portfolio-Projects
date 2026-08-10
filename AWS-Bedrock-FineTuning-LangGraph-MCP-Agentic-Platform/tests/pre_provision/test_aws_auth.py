import boto3


def test_sts_get_caller_identity_succeeds() -> None:
    client = boto3.client("sts", region_name="us-east-1")
    identity = client.get_caller_identity()
    assert "Account" in identity
    assert "Arn" in identity
