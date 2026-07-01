"""Step 13: Full teardown — delete resource group and Entra app registrations."""

from __future__ import annotations

import json
import time

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_az


SPA_APP_DISPLAY_NAME = "cdss-frontend-spa"
API_APP_DISPLAY_NAME = "cdss-api"

RG_DELETE_POLL_INTERVAL_SECONDS = 10
RG_DELETE_TIMEOUT_SECONDS = 30
PURGE_CALL_TIMEOUT_SECONDS = 30


def _wait_for_rg_deletion(rg: str) -> bool:
    """Poll until the resource group is gone or the timeout elapses.

    Bounded so teardown always finishes and returns control to the caller --
    never blocks indefinitely, even if the RG deletion itself stalls in Azure.
    """
    elapsed = 0
    while elapsed < RG_DELETE_TIMEOUT_SECONDS:
        result = run_az(["group", "exists", "--name", rg], parse_json=False)
        if result.stdout.strip().lower() == "false":
            return True
        print_substep(
            f"Resource group '{rg}' still deleting ({elapsed}s / {RG_DELETE_TIMEOUT_SECONDS}s)...",
            "info",
        )
        time.sleep(RG_DELETE_POLL_INTERVAL_SECONDS)
        elapsed += RG_DELETE_POLL_INTERVAL_SECONDS
    return False


def _find_deleted_key_vaults(rg: str) -> list[dict]:
    """Return soft-deleted Key Vaults whose original resource group matches rg.

    Queried live from Azure rather than local state, since deployment state
    (deployed_resources) is cleared after the first teardown run and would
    be unavailable on a re-run of --purge.
    """
    result = run_az(["keyvault", "list-deleted"])
    if not result.success or not result.stdout:
        return []
    try:
        vaults = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return []
    rg_marker = f"/resourcegroups/{rg.lower()}/"
    matches = []
    for vault in vaults:
        vault_id = str(vault.get("properties", {}).get("vaultId", "")).lower()
        if rg_marker in vault_id:
            matches.append({
                "name": vault.get("name", ""),
                "location": vault.get("properties", {}).get("location", ""),
            })
    return matches


def _find_deleted_cognitive_accounts(rg: str) -> list[dict]:
    """Return soft-deleted Cognitive Services accounts whose original RG matches rg."""
    result = run_az(["cognitiveservices", "account", "list-deleted"])
    if not result.success or not result.stdout:
        return []
    try:
        accounts = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return []
    rg_marker = f"/resourcegroups/{rg.lower()}/"
    matches = []
    for account in accounts:
        account_id = str(account.get("id", "")).lower()
        if rg_marker in account_id:
            matches.append({
                "name": account.get("name", ""),
                "location": account.get("location", ""),
            })
    return matches


def _purge_soft_deleted_resources(rg: str) -> None:
    """Permanently purge soft-deleted Key Vault and Cognitive Services resources.

    Irreversible: this removes the recovery window (90 days for Key Vault,
    48h for Cognitive Services). Only called when --purge is explicitly passed.
    Discovers resource names live from Azure so it works even on a re-run
    after local deployment state has been cleared.
    """
    print_substep("Waiting for resource group deletion to complete before purging...", "info")
    if not _wait_for_rg_deletion(rg):
        print_substep(
            f"Resource group '{rg}' still deleting after {RG_DELETE_TIMEOUT_SECONDS}s; "
            "skipping purge. Re-run 'cdss-deploy teardown --purge' once deletion finishes.",
            "warn",
        )
        return

    vaults = _find_deleted_key_vaults(rg)
    if not vaults:
        print_substep(f"No soft-deleted Key Vaults found for resource group '{rg}'", "info")
    for vault in vaults:
        name, location = vault["name"], vault["location"]
        if not name or not location:
            continue
        print_substep(f"Purging soft-deleted Key Vault: {name}...", "info")
        result = run_az(
            ["keyvault", "purge", "--name", name, "--location", location],
            timeout=PURGE_CALL_TIMEOUT_SECONDS,
        )
        if result.success:
            print_substep(f"Purged Key Vault: {name}", "ok")
        elif result.returncode == 124:
            print_substep(
                f"Key Vault purge for '{name}' did not finish within "
                f"{PURGE_CALL_TIMEOUT_SECONDS}s; moving on. It may still complete in the "
                "background -- re-run 'cdss-deploy teardown --purge' later to confirm.",
                "warn",
            )
        else:
            print_substep(f"Key Vault purge warning: {result.stderr[-200:]}", "warn")

    accounts = _find_deleted_cognitive_accounts(rg)
    if not accounts:
        print_substep(f"No soft-deleted Cognitive Services accounts found for resource group '{rg}'", "info")
    for account in accounts:
        name, location = account["name"], account["location"]
        if not name or not location:
            continue
        print_substep(f"Purging soft-deleted Cognitive Services account: {name}...", "info")
        result = run_az(
            [
                "cognitiveservices", "account", "purge",
                "--name", name,
                "--location", location,
                "--resource-group", rg,
            ],
            timeout=PURGE_CALL_TIMEOUT_SECONDS,
        )
        if result.success:
            print_substep(f"Purged Cognitive Services account: {name}", "ok")
        elif result.returncode == 124:
            print_substep(
                f"Cognitive Services purge for '{name}' did not finish within "
                f"{PURGE_CALL_TIMEOUT_SECONDS}s; moving on. It may still complete in the "
                "background -- re-run 'cdss-deploy teardown --purge' later to confirm.",
                "warn",
            )
        else:
            print_substep(f"Cognitive Services purge warning: {result.stderr[-200:]}", "warn")


def run(ctx: dict) -> dict:
    rg = ctx.get("resource_group", "")
    state = ctx.get("state")
    purge = ctx.get("purge", False)

    if not rg and state:
        rg = state.resource_group

    if not rg:
        return {"success": False, "error": "No resource group to delete"}

    # Delete resource group
    print_substep(f"Deleting resource group: {rg}...", "info")
    result = run_az(["group", "delete", "--name", rg, "--yes", "--no-wait"])
    if result.success:
        print_substep(f"Resource group '{rg}' deletion initiated (async)", "ok")
    else:
        print_substep(f"RG deletion warning: {result.stderr[-200:]}", "warn")

    # Clean up Entra app registrations
    for display_name in [SPA_APP_DISPLAY_NAME, API_APP_DISPLAY_NAME]:
        result = run_az([
            "ad", "app", "list", "--display-name", display_name,
            "--query", "[0].appId", "-o", "tsv",
        ])
        app_id = result.stdout.strip() if result.success else ""
        if app_id:
            print_substep(f"Deleting Entra app: {display_name} ({app_id})...", "info")
            del_result = run_az(["ad", "app", "delete", "--id", app_id])
            if del_result.success:
                print_substep(f"Deleted: {display_name}", "ok")
            else:
                print_substep(f"Could not delete {display_name}: {del_result.stderr[-100:]}", "warn")
        else:
            print_substep(f"Entra app '{display_name}' not found, skipping", "info")

    # Purge soft-deleted resources
    if purge:
        _purge_soft_deleted_resources(rg)
    else:
        print_substep("Note: Cognitive Services may remain in soft-deleted state for 48h", "info")
        print_substep("Key Vault may remain in soft-deleted state for 90 days", "info")
        print_substep("To purge immediately, re-run with: cdss-deploy teardown --purge", "info")

    return {"success": True}
