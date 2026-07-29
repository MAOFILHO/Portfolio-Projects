from __future__ import annotations

import time

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success, log_warning
from surveil_deploy.runner import run as run_command
from surveil_deploy.soft_delete import purge_soft_deleted_vision_accounts
from surveil_deploy.state import DeploymentState

STEP_NAME = "s12_teardown"
STEP_TITLE = "Tearing down all Azure resources"

# Cognitive Services accounts only show up in `az cognitiveservices account
# list-deleted` once Azure has actually finished deleting the resource group
# they lived in -- with `--no-wait`, that can take several minutes after the
# `az group delete` call returns. Bounds how long `--purge` blocks waiting
# for that before giving up and falling back to the async, best-effort path.
GROUP_DELETE_POLL_TIMEOUT_SECONDS = 900
GROUP_DELETE_POLL_INTERVAL_SECONDS = 15


def _resource_group_exists(resource_group: str) -> bool:
    result = run_command(["az", "group", "exists", "--name", resource_group], stream=False, check=False)
    return result.stdout.strip().lower() == "true"


def run(config: DeployConfig, state: DeploymentState, purge: bool = False) -> dict:
    log_step(12, 12, STEP_TITLE)

    resource_group = config.resource_group_name()
    log_info(f"Deleting resource group {resource_group} (this runs in the background; Azure takes several minutes)")

    if not _resource_group_exists(resource_group):
        log_warning(f"Resource group {resource_group} does not exist — nothing to delete")
    else:
        run_command(["az", "group", "delete", "--name", resource_group, "--yes", "--no-wait"])
        log_success(f"Deletion of {resource_group} started (--no-wait; check with `az group exists --name {resource_group}`)")

        if purge:
            # `--purge` is a promise to actually free up the account names for
            # a future redeploy, not just to fire the delete -- so unlike the
            # plain teardown path above, block here until the group is fully
            # gone rather than checking for soft-deleted accounts too early
            # and silently finding nothing (confirmed live: the check below,
            # run immediately after `--no-wait` returns, always reported
            # "nothing to purge" even though the accounts soft-deleted a
            # minute later once the group finish deleting).
            log_info(f"--purge requested: waiting for {resource_group} to finish deleting before checking for soft-deleted accounts")
            waited = 0
            while _resource_group_exists(resource_group):
                if waited >= GROUP_DELETE_POLL_TIMEOUT_SECONDS:
                    log_warning(
                        f"{resource_group} still deleting after {GROUP_DELETE_POLL_TIMEOUT_SECONDS}s — "
                        "giving up on the wait. Re-run `surveil-deploy teardown --purge` once it's gone "
                        f"(check with `az group exists --name {resource_group}`) to purge soft-deleted accounts."
                    )
                    return {}
                time.sleep(GROUP_DELETE_POLL_INTERVAL_SECONDS)
                waited += GROUP_DELETE_POLL_INTERVAL_SECONDS
            log_success(f"{resource_group} deletion confirmed complete")

    if purge:
        purge_soft_deleted_vision_accounts(config)

    return {}
