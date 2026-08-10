from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from bedrock_platform.api.deps import get_enabled_scenario
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.scenario_loader import load_scenarios

router = APIRouter()


class ScenarioSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str
    tagline: str
    industry: str


class ScenarioDetail(ScenarioSummary):
    system_prompt: str
    output_mode: str
    sample_prompts: list[str]
    epochs: int
    base_model_id: str


@router.get("/scenarios", response_model=list[ScenarioSummary])
def list_enabled_scenarios() -> list[ScenarioSummary]:
    """Only enabled scenarios are returned — the frontend nav must never hardcode
    the list, and flipping a YAML flag is the only way to add or remove an entry."""
    return [
        ScenarioSummary(
            id=s.id, display_name=s.display_name, tagline=s.tagline, industry=s.industry
        )
        for s in load_scenarios()
        if s.enabled
    ]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
def get_scenario_detail(scenario: ScenarioConfig = Depends(get_enabled_scenario)) -> ScenarioDetail:
    return ScenarioDetail(
        id=scenario.id,
        display_name=scenario.display_name,
        tagline=scenario.tagline,
        industry=scenario.industry,
        system_prompt=scenario.system_prompt,
        output_mode=scenario.output_mode,
        sample_prompts=scenario.sample_prompts,
        epochs=scenario.epochs,
        base_model_id=scenario.base_model_id,
    )
