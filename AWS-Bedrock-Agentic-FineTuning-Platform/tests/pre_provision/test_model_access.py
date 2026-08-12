import boto3

BASE_MODEL_ID = "amazon.nova-2-lite-v1:0:256k"


def test_nova_2_lite_is_authorized() -> None:
    client = boto3.client("bedrock", region_name="us-east-1")
    response = client.get_foundation_model_availability(modelId=BASE_MODEL_ID)
    assert response["authorizationStatus"] == "AUTHORIZED"
    assert response["regionAvailability"] == "AVAILABLE"
