from functools import lru_cache

import boto3
from fastapi import HTTPException

from bedrock_platform.aws.session import get_session
from bedrock_platform.config.scenario_config import ScenarioConfig
from bedrock_platform.config.scenario_loader import load_scenarios
from bedrock_platform.config.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from .env at runtime


@lru_cache
def get_boto_session() -> boto3.Session:
    return get_session()


def get_enabled_scenario(scenario_id: str) -> ScenarioConfig:
    for scenario in load_scenarios():
        if scenario.id == scenario_id and scenario.enabled:
            return scenario
    raise HTTPException(status_code=404, detail=f"Unknown or disabled scenario: {scenario_id!r}")
