"""Resource naming with collision handling.

Unlike Azure-Agentic-Video-Surveillance's Bicep (which derives every name
from `uniqueString(subscription, env, location)` -- deterministic, so a
redeploy always targets the exact same names), this project's names are
plain incrementing suffixes: `rg-forecasting-platform`, then `-2`, `-3`, ...
That's the behavior explicitly asked for: never fail/stop on a name
conflict, never touch a still-live prior deployment, just move to the next
suffix and carry on.

Only one resource in this stack has a real *soft-delete* concept: the Log
Analytics workspace (14-day soft delete, no purge API -- only "recover").
VM/Disk/NIC/PublicIP/NSG/VNet delete immediately, no lingering reservation,
so a name collision on those only happens if a prior deploy's resource
group is still live -- which the increment loop below already handles.

Before checking each candidate resource-group name for liveness, this
proactively tries to *recover* any soft-deleted Log Analytics workspace
that would otherwise block reusing that exact name -- so a normal
`deploy` after a normal `teardown` reuses the base name instead of
accumulating `-2`, `-3`, ... forever. If recovery doesn't succeed (e.g. the
resource group itself doesn't exist yet -- expected on a first deploy, or
still doesn't exist within Azure's soft-delete propagation window), that's
not fatal: this function still falls through to the liveness check, and if
the base name turns out to be free (RG doesn't exist), the deploy simply
proceeds -- if the Bicep deployment then hits a stale soft-delete conflict
Azure hasn't resolved yet, re-running `forecast-deploy deploy --fresh` will
re-attempt naming from scratch and increment past it.
"""

from __future__ import annotations

from dataclasses import dataclass

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import log_info, log_warning
from forecast_deploy.runner import CommandError, run as run_command, run_json

SOFT_DELETE_CHECK_TIMEOUT_SECONDS = 30
MAX_NAME_ATTEMPTS = 50


@dataclass
class ResolvedNames:
    resource_group: str
    name_prefix: str
    log_analytics_workspace: str


def resource_group_exists(resource_group: str) -> bool:
    result = run_command(["az", "group", "exists", "--name", resource_group], stream=False, check=False)
    return result.stdout.strip().lower() == "true"


def list_matching_resource_groups(config: DeployConfig) -> list[str]:
    """Every live resource group whose name starts with the configured base
    name -- covers every incremental suffix a prior deploy might have used.
    Used as `teardown`'s fallback target when there's no local state file to
    read the exact name from (e.g. a GitHub Actions run, which never has the
    deployment_state.json a local `deploy` would have written), and by
    smoke/teardown_verify.py's post-teardown check.
    """
    groups = run_json(["az", "group", "list", "-o", "json"], timeout=60)
    return [g["name"] for g in groups if g["name"].startswith(config.resource_group_base)]


def _try_recover_log_analytics_workspace(resource_group: str, workspace_name: str) -> None:
    try:
        deleted = run_json(
            [
                "az", "monitor", "log-analytics", "workspace", "list-deleted-workspaces",
                "--resource-group", resource_group, "-o", "json",
            ],
            timeout=SOFT_DELETE_CHECK_TIMEOUT_SECONDS,
        )
    except CommandError as exc:
        # Expected on a first deploy, or if the resource group from a prior
        # teardown hasn't finished disappearing yet -- not fatal, see the
        # module docstring for why the caller doesn't need this to succeed.
        log_info(f"Skipping Log Analytics soft-delete check for {resource_group}: {exc}")
        return

    match = next((w for w in deleted if w.get("name") == workspace_name), None)
    if not match:
        return

    log_info(f"Recovering soft-deleted Log Analytics workspace {workspace_name} to free it for redeploy")
    try:
        run_command(
            [
                "az", "monitor", "log-analytics", "workspace", "recover",
                "--resource-group", resource_group, "--workspace-name", workspace_name,
            ],
            timeout=SOFT_DELETE_CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - a slow/failed recovery shouldn't abort naming resolution
        log_warning(f"Recovery of {workspace_name} did not complete: {exc}")


def resolve_names(config: DeployConfig) -> ResolvedNames:
    """Find the first (resource_group, name_prefix) pair that isn't a live
    deployment, incrementing a numeric suffix on every collision instead of
    failing. Recorded into the deploy CLI's state file so `teardown` later
    targets the exact resource group this `deploy` actually used.
    """
    base_rg = config.resource_group_base
    base_prefix = config.name_prefix_base

    for attempt in range(MAX_NAME_ATTEMPTS):
        suffix = attempt + 1
        candidate_rg = base_rg if attempt == 0 else f"{base_rg}-{suffix}"
        candidate_prefix = base_prefix if attempt == 0 else f"{base_prefix}-{suffix}"
        candidate_law = f"law-{candidate_prefix}"

        _try_recover_log_analytics_workspace(candidate_rg, candidate_law)

        if not resource_group_exists(candidate_rg):
            return ResolvedNames(
                resource_group=candidate_rg,
                name_prefix=candidate_prefix,
                log_analytics_workspace=candidate_law,
            )

        log_info(f"{candidate_rg} is still live (a previous deploy that wasn't torn down) -- trying the next name instead of stopping")

    raise RuntimeError(
        f"{MAX_NAME_ATTEMPTS} consecutive resource-group name collisions -- giving up. "
        "Tear down old deployments (`forecast-deploy teardown`) or set resource_group_base "
        "in .env to something else."
    )
