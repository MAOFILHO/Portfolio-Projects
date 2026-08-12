import json
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict

from bedrock_platform.config.scenario_config import ScenarioConfig

PRICING_API_REGION = "us-east-1"
SERVICE_CODE = "AmazonBedrock"

CHARS_PER_TOKEN = 4
ASSUMED_DEMO_CALLS_PER_MODEL = 10
ASSUMED_OUTPUT_TOKENS_PER_CALL = 150

# Price List API usagetype families, keyed by the customization base model ID.
# Explicit rather than derived from the model ID: the spellings follow no predictable
# rule ("Nova2.0Lite" vs "NovaMicro" vs "Llama3-3-70B"), and a wrong guess would price
# the wrong model silently. Region prefix matters too — Nova customization is us-east-1
# (USE1) only, Llama customization is us-west-2 (USW2) only.
USAGE_TYPE_FAMILIES: dict[str, tuple[str, str]] = {
    "amazon.nova-2-lite-v1:0:256k": ("USE1", "Nova2.0Lite"),
    "amazon.nova-micro-v1:0:128k": ("USE1", "NovaMicro"),
    "amazon.nova-lite-v1:0:300k": ("USE1", "NovaLite"),
    "amazon.nova-pro-v1:0:300k": ("USE1", "NovaPro"),
    "meta.llama3-3-70b-instruct-v1:0:128k": ("USW2", "Llama3-3-70B"),
}


class PriceUnavailableError(Exception):
    """Raised when the live AWS Price List API is unreachable or returns no match.

    Never caught to fall back on a guessed price — the cost estimator must fail loudly
    rather than silently understate cost.
    """


class UnknownModelPricingError(Exception):
    """Raised when a scenario's base_model_id has no known Price List usagetype family.

    Deliberately fatal for the same reason as PriceUnavailableError: quoting a cost
    gate figure derived from the wrong model is worse than refusing to quote one.
    """


def _usage_types(base_model_id: str) -> dict[str, str]:
    try:
        region, family = USAGE_TYPE_FAMILIES[base_model_id]
    except KeyError:
        raise UnknownModelPricingError(
            f"No Price List usagetype family known for base_model_id={base_model_id!r}. "
            f"Add it to USAGE_TYPE_FAMILIES (known: {sorted(USAGE_TYPE_FAMILIES)})."
        ) from None
    return {
        "training": f"{region}-{family}-Customization-Training",
        "storage": f"{region}-{family}-Customization-Storage",
        "input": f"{region}-{family}-input-tokens-custom-model",
        "output": f"{region}-{family}-output-tokens-custom-model",
    }


class CostEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    base_model_id: str
    training_tokens: int
    training_price_per_1k_usd: float
    training_cost_usd: float
    storage_price_per_model_month_usd: float
    storage_cost_usd_per_month: float
    input_tokens: int
    input_price_per_1k_usd: float
    input_cost_usd: float
    output_tokens: int
    output_price_per_1k_usd: float
    output_cost_usd: float
    total_one_time_cost_usd: float
    total_recurring_cost_usd_per_month: float


def _get_price_per_unit(pricing_client: Any, usage_type: str) -> float:
    try:
        response = pricing_client.get_products(
            ServiceCode=SERVICE_CODE,
            Filters=[{"Type": "TERM_MATCH", "Field": "usagetype", "Value": usage_type}],
        )
    except (BotoCoreError, ClientError) as exc:
        raise PriceUnavailableError(
            f"AWS Price List API call failed for usagetype={usage_type!r}: {exc}"
        ) from exc

    price_list = response.get("PriceList", [])
    if not price_list:
        raise PriceUnavailableError(
            f"No price found for usagetype={usage_type!r} in {SERVICE_CODE}/{PRICING_API_REGION}."
        )

    product = json.loads(price_list[0])
    on_demand_terms = product["terms"]["OnDemand"]
    first_term = next(iter(on_demand_terms.values()))
    first_dimension = next(iter(first_term["priceDimensions"].values()))
    return float(first_dimension["pricePerUnit"]["USD"])


def estimate_cost(
    scenario_id: str,
    base_model_id: str,
    training_tokens: int,
    input_tokens: int,
    output_tokens: int,
    pricing_client: Any = None,
) -> CostEstimate:
    client = pricing_client or boto3.client("pricing", region_name=PRICING_API_REGION)
    usage_types = _usage_types(base_model_id)

    training_price = _get_price_per_unit(client, usage_types["training"])
    storage_price = _get_price_per_unit(client, usage_types["storage"])
    input_price = _get_price_per_unit(client, usage_types["input"])
    output_price = _get_price_per_unit(client, usage_types["output"])

    training_cost = (training_tokens / 1000) * training_price
    input_cost = (input_tokens / 1000) * input_price
    output_cost = (output_tokens / 1000) * output_price

    return CostEstimate(
        scenario_id=scenario_id,
        base_model_id=base_model_id,
        training_tokens=training_tokens,
        training_price_per_1k_usd=training_price,
        training_cost_usd=round(training_cost, 6),
        storage_price_per_model_month_usd=storage_price,
        storage_cost_usd_per_month=storage_price,
        input_tokens=input_tokens,
        input_price_per_1k_usd=input_price,
        input_cost_usd=round(input_cost, 6),
        output_tokens=output_tokens,
        output_price_per_1k_usd=output_price,
        output_cost_usd=round(output_cost, 6),
        total_one_time_cost_usd=round(training_cost + input_cost + output_cost, 6),
        total_recurring_cost_usd_per_month=round(storage_price, 6),
    )


def _dataset_char_count(dataset_path: Path) -> int:
    total = 0
    with dataset_path.open() as f:
        for line in f:
            record = json.loads(line)
            total += len(record["system"][0]["text"])
            for message in record["messages"]:
                total += len(message["content"][0]["text"])
    return total


def estimate_scenario_cost(scenario: ScenarioConfig) -> CostEstimate:
    """Heuristic cost estimate for one scenario, shared by the CLI cost printer and
    the API's /cost/summary route. Uses a 4-chars-per-token heuristic and an assumed
    demo call volume — the underlying per-unit prices are always live from AWS."""
    dataset_chars = _dataset_char_count(scenario.dataset_path)
    dataset_tokens = dataset_chars // CHARS_PER_TOKEN

    sample_prompt_tokens = sum(len(p) // CHARS_PER_TOKEN for p in scenario.sample_prompts)
    input_tokens = sample_prompt_tokens * ASSUMED_DEMO_CALLS_PER_MODEL
    output_tokens = ASSUMED_OUTPUT_TOKENS_PER_CALL * ASSUMED_DEMO_CALLS_PER_MODEL

    return estimate_cost(
        scenario_id=scenario.id,
        base_model_id=scenario.base_model_id,
        training_tokens=dataset_tokens * scenario.epochs,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
