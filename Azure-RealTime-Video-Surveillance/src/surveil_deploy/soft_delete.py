"""Handles soft-deleted resources left over from a prior teardown/deploy.

Resource names in this project are deterministic per (subscription,
environment name, location) via Bicep's `uniqueString(...)`, so a prior
teardown followed by a redeploy always collides on the exact same name if
Azure is still holding a soft-deleted record under it. Two resource types in
this project's infra soft-delete on removal:

- Cognitive Services (Vision) accounts: soft-deleted for 48h, no purge
  protection here (unlike Key Vault) -- a same-named redeploy fails against
  the soft-deleted record until it's explicitly purged.
- Log Analytics workspaces: soft-deleted for 14 days -- there is no "purge"
  API for these, only "recover" (which brings the workspace itself back, so
  the Bicep deploy proceeds as an update to the recovered resource instead
  of a fresh create).

Both are checked and resolved automatically before every deploy, not just
during teardown.
"""

from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_warning
from surveil_deploy.runner import run as run_command, run_json

PURGE_CALL_TIMEOUT_SECONDS = 30


def purge_soft_deleted_vision_accounts(config: DeployConfig) -> None:
    log_info("Checking for soft-deleted Cognitive Services accounts from a prior deploy/teardown")
    deleted_accounts = run_json(
        ["az", "cognitiveservices", "account", "list-deleted", "-o", "json"],
        timeout=PURGE_CALL_TIMEOUT_SECONDS,
    )

    resource_group = config.resource_group_name()
    matches = [
        a for a in deleted_accounts
        if f"/resourceGroups/{resource_group}/".lower() in a.get("id", "").lower()
    ]

    if not matches:
        log_info("No soft-deleted Cognitive Services accounts found -- nothing to purge")
        return

    for account in matches:
        name = account["name"]
        location = account["location"]
        log_info(f"Purging soft-deleted Cognitive Services account: {name} ({location}) to free its name for redeploy")
        try:
            run_command(
                ["az", "cognitiveservices", "account", "purge", "--name", name,
                 "--location", location, "--resource-group", resource_group],
                timeout=PURGE_CALL_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001 - a slow/failed purge shouldn't abort the deploy
            log_warning(f"Purge of {name} did not complete within {PURGE_CALL_TIMEOUT_SECONDS}s: {exc}")


def recover_soft_deleted_log_analytics_workspaces(config: DeployConfig) -> None:
    log_info("Checking for soft-deleted Log Analytics workspaces from a prior deploy/teardown")
    resource_group = config.resource_group_name()
    try:
        deleted_workspaces = run_json(
            ["az", "monitor", "log-analytics", "workspace", "list-deleted-workspaces",
             "--resource-group", resource_group, "-o", "json"],
            timeout=PURGE_CALL_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - resource group may not exist yet on a first deploy
        log_info(f"Skipping Log Analytics soft-delete check: {exc}")
        return

    if not deleted_workspaces:
        log_info("No soft-deleted Log Analytics workspaces found -- nothing to recover")
        return

    for workspace in deleted_workspaces:
        name = workspace["name"]
        log_info(f"Recovering soft-deleted Log Analytics workspace: {name} to free it for redeploy")
        try:
            run_command(
                ["az", "monitor", "log-analytics", "workspace", "recover",
                 "--resource-group", resource_group, "--workspace-name", name],
                timeout=PURGE_CALL_TIMEOUT_SECONDS,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001 - a slow/failed recovery shouldn't abort the deploy
            log_warning(f"Recovery of {name} did not complete within {PURGE_CALL_TIMEOUT_SECONDS}s: {exc}")
