import json

import boto3
import pytest
from botocore.stub import Stubber

from bedrock_platform.aws.cost_estimator import (
    PriceUnavailableError,
    UnknownModelPricingError,
    _usage_types,
    estimate_cost,
)

BASE_MODEL = "amazon.nova-2-lite-v1:0:256k"
USAGE_TYPES = _usage_types(BASE_MODEL)

PRICES = {
    USAGE_TYPES["training"]: "0.00378",
    USAGE_TYPES["storage"]: "1.95",
    USAGE_TYPES["input"]: "0.0003",
    USAGE_TYPES["output"]: "0.0025",
}


def _price_list_entry(usage_type: str, price: str) -> str:
    return json.dumps(
        {
            "product": {"attributes": {"usagetype": usage_type}},
            "terms": {
                "OnDemand": {
                    "term1": {
                        "priceDimensions": {"dim1": {"pricePerUnit": {"USD": price}}},
                    }
                }
            },
        }
    )


@pytest.fixture
def pricing_client_stub():
    client = boto3.client("pricing", region_name="us-east-1")
    stubber = Stubber(client)
    for key in ["training", "storage", "input", "output"]:
        usage_type = USAGE_TYPES[key]
        stubber.add_response(
            "get_products",
            {
                "PriceList": [_price_list_entry(usage_type, PRICES[usage_type])],
                "FormatVersion": "aws_v1",
            },
            {
                "ServiceCode": "AmazonBedrock",
                "Filters": [{"Type": "TERM_MATCH", "Field": "usagetype", "Value": usage_type}],
            },
        )
    stubber.activate()
    yield client
    stubber.deactivate()


def test_estimate_cost_computes_expected_totals(pricing_client_stub) -> None:
    estimate = estimate_cost(
        scenario_id="pharma",
        base_model_id=BASE_MODEL,
        training_tokens=26_660 * 2,
        input_tokens=1000,
        output_tokens=1000,
        pricing_client=pricing_client_stub,
    )
    assert estimate.base_model_id == BASE_MODEL
    assert estimate.training_price_per_1k_usd == pytest.approx(0.00378)
    assert estimate.storage_price_per_model_month_usd == pytest.approx(1.95)
    assert estimate.training_cost_usd == pytest.approx((26_660 * 2 / 1000) * 0.00378, rel=1e-3)
    assert estimate.total_recurring_cost_usd_per_month == pytest.approx(1.95)


def test_price_unavailable_raises_on_empty_price_list() -> None:
    client = boto3.client("pricing", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "get_products",
        {"PriceList": [], "FormatVersion": "aws_v1"},
        {
            "ServiceCode": "AmazonBedrock",
            "Filters": [
                {"Type": "TERM_MATCH", "Field": "usagetype", "Value": USAGE_TYPES["training"]}
            ],
        },
    )
    stubber.activate()

    with pytest.raises(PriceUnavailableError):
        estimate_cost(
            scenario_id="pharma",
            base_model_id=BASE_MODEL,
            training_tokens=1000,
            input_tokens=100,
            output_tokens=100,
            pricing_client=client,
        )
    stubber.deactivate()


def test_usage_types_differ_per_base_model() -> None:
    """The bug this guards: usage types were hardcoded to Nova 2 Lite, so switching
    base_model_id silently priced the wrong model — Nova Micro is 3.8x cheaper to
    train, so the cost gate would have overstated it by ~4x."""
    nova_2_lite = _usage_types("amazon.nova-2-lite-v1:0:256k")
    nova_micro = _usage_types("amazon.nova-micro-v1:0:128k")
    llama = _usage_types("meta.llama3-3-70b-instruct-v1:0:128k")

    assert nova_2_lite["training"] == "USE1-Nova2.0Lite-Customization-Training"
    assert nova_micro["training"] == "USE1-NovaMicro-Customization-Training"
    # Llama customization is us-west-2 only, so the region prefix changes too.
    assert llama["training"] == "USW2-Llama3-3-70B-Customization-Training"


def test_unknown_base_model_fails_loudly() -> None:
    """A cost gate quoting a figure derived from the wrong model is worse than one
    that refuses to quote — same philosophy as PriceUnavailableError."""
    with pytest.raises(UnknownModelPricingError, match="No Price List usagetype family"):
        _usage_types("anthropic.claude-3-haiku-20240307-v1:0:200k")
