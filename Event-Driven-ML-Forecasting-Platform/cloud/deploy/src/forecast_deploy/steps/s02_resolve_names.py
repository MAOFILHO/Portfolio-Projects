from __future__ import annotations

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import log_step, log_success, write_key_value
from forecast_deploy.naming import resolve_names
from forecast_deploy.state import DeploymentState

STEP_NAME = "s02_resolve_names"
STEP_TITLE = "Resolving resource names — handling collisions with prior deploys"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(2, 5, STEP_TITLE)

    names = resolve_names(config)
    log_success(f"Resolved resource group: {names.resource_group}")
    write_key_value("Resource group", names.resource_group)
    write_key_value("Name prefix", names.name_prefix)
    write_key_value("Log Analytics workspace", names.log_analytics_workspace)

    return {
        "RESOURCE_GROUP": names.resource_group,
        "NAME_PREFIX": names.name_prefix,
        "LOG_ANALYTICS_WORKSPACE": names.log_analytics_workspace,
    }
