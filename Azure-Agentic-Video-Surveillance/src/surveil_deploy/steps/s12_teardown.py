from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success, log_warning
from surveil_deploy.runner import run as run_command
from surveil_deploy.soft_delete import purge_soft_deleted_vision_accounts
from surveil_deploy.state import DeploymentState

STEP_NAME = "s12_teardown"
STEP_TITLE = "Tearing down all Azure resources"


def run(config: DeployConfig, state: DeploymentState, purge: bool = False) -> dict:
    log_step(12, 12, STEP_TITLE)

    resource_group = config.resource_group_name()
    log_info(f"Deleting resource group {resource_group} (this runs in the background; Azure takes several minutes)")

    exists = run_command(["az", "group", "exists", "--name", resource_group], stream=False, check=False)
    if exists.stdout.strip().lower() != "true":
        log_warning(f"Resource group {resource_group} does not exist — nothing to delete")
    else:
        run_command(["az", "group", "delete", "--name", resource_group, "--yes", "--no-wait"])
        log_success(f"Deletion of {resource_group} started (--no-wait; check with `az group exists --name {resource_group}`)")

    if purge:
        purge_soft_deleted_vision_accounts(config)

    return {}
