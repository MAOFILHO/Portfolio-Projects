from __future__ import annotations

from forecast_deploy.config import DeployConfig
from forecast_deploy.state import DeploymentState
from forecast_deploy.steps import s00_preflight


def run(config: DeployConfig) -> bool:
    try:
        s00_preflight.run(config, DeploymentState())
        return True
    except RuntimeError:
        return False
