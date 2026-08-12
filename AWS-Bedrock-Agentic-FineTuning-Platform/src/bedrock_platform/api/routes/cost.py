from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from bedrock_platform.aws.cost_estimator import PriceUnavailableError, estimate_scenario_cost
from bedrock_platform.config.scenario_loader import enabled_scenarios

router = APIRouter()


class ScenarioCost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    one_time_cost_usd: float
    recurring_cost_usd_per_month: float


class CostSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenarios: list[ScenarioCost]
    total_one_time_usd: float
    total_recurring_usd_per_month: float
    price_source_unavailable: bool


@router.get("/cost/summary", response_model=CostSummaryResponse)
def get_cost_summary() -> CostSummaryResponse:
    """Live per-scenario cost, same heuristic and live AWS prices as
    scripts/print_cost_estimate.py — never a hardcoded or guessed figure."""
    scenarios = []
    try:
        for scenario in enabled_scenarios():
            estimate = estimate_scenario_cost(scenario)
            scenarios.append(
                ScenarioCost(
                    scenario_id=scenario.id,
                    one_time_cost_usd=estimate.total_one_time_cost_usd,
                    recurring_cost_usd_per_month=estimate.total_recurring_cost_usd_per_month,
                )
            )
    except PriceUnavailableError:
        return CostSummaryResponse(
            scenarios=[],
            total_one_time_usd=0.0,
            total_recurring_usd_per_month=0.0,
            price_source_unavailable=True,
        )

    return CostSummaryResponse(
        scenarios=scenarios,
        total_one_time_usd=round(sum(s.one_time_cost_usd for s in scenarios), 6),
        total_recurring_usd_per_month=round(
            sum(s.recurring_cost_usd_per_month for s in scenarios), 6
        ),
        price_source_unavailable=False,
    )
