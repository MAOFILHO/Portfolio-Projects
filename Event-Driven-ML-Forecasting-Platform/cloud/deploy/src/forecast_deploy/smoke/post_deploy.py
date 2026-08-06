from __future__ import annotations

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import log_error
from forecast_deploy.state import load_state
from forecast_deploy.steps import s05_smoke_post


def run(config: DeployConfig) -> bool:
    state = load_state(config.state_file())
    if "DASHBOARD_URL" not in state.resource_outputs:
        log_error("No deployment found. Run `forecast-deploy deploy` first.")
        return False
    try:
        s05_smoke_post.run(config, state)
        return True
    except RuntimeError:
        return False
