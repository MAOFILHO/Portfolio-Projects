"""Confirms teardown actually left nothing billable behind -- the gap this
project's tooling fixes versus Azure-Agentic-Video-Surveillance's
`surveil-deploy teardown`, which has no equivalent post-teardown check.

Deliberately doesn't rely on the deploy CLI's own state file (which
`teardown` clears at the end) so this also works as a standalone command run
independently, any time later: it enumerates resource groups by name
*pattern* (anything starting with the configured base name, covering every
incremental suffix a prior deploy might have used) rather than trusting a
single remembered name.
"""

from __future__ import annotations

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import HealthRow, HealthStatus, log_info, write_health_row, write_summary_block
from forecast_deploy.naming import list_matching_resource_groups
from forecast_deploy.runner import run_json

PROJECT_TAG = "project=forecasting-platform"


def run(config: DeployConfig) -> bool:
    rows: list[HealthRow] = []

    matching_groups = list_matching_resource_groups(config)
    if matching_groups:
        rows.append(HealthRow(
            "No leftover resource groups",
            HealthStatus.FAIL,
            f"still exist: {', '.join(matching_groups)}",
        ))
    else:
        rows.append(HealthRow("No leftover resource groups", HealthStatus.PASS, f"none matching '{config.resource_group_base}*'"))

    # Filtered client-side, not via `az resource list --tag ...`: that flag
    # combination errors out ("cannot use '--tag' with '--location'") on any
    # machine with a default location configured via `az configure`
    # (observed firsthand) -- not an Azure API limitation, just an az CLI
    # arg-validation quirk, and not worth mutating the operator's global az
    # CLI defaults to work around from inside this tool.
    all_resources = run_json(["az", "resource", "list", "-o", "json"], timeout=60)
    # `.get("tags", {})` alone isn't enough: many resources have an
    # explicit "tags": null rather than omitting the key entirely, so the
    # default only kicks in for a *missing* key, not a present-but-null one.
    tagged = [r for r in all_resources if (r.get("tags") or {}).get("project") == "forecasting-platform"]
    if tagged:
        names = ", ".join(r["name"] for r in tagged)
        rows.append(HealthRow(
            "No live tagged resources",
            HealthStatus.FAIL,
            f"{len(tagged)} still exist at subscription scope: {names}",
        ))
    else:
        rows.append(HealthRow("No live tagged resources", HealthStatus.PASS, "subscription-wide tag query returned nothing"))

    for row in rows:
        write_health_row(row)

    ok = write_summary_block(rows, title="Teardown verification")

    # Informational, not fatal: a soft-deleted Log Analytics workspace from
    # this teardown may still be listed for up to 14 days -- Azure doesn't
    # bill soft-deleted resources, and naming.py's resolve_names() already
    # self-heals this on the *next* deploy by recovering it, so this is
    # nothing to act on, just worth knowing about.
    if not matching_groups:
        try:
            base_rg = config.resource_group_base
            deleted_workspaces = run_json(
                ["az", "monitor", "log-analytics", "workspace", "list-deleted-workspaces", "--resource-group", base_rg, "-o", "json"],
                timeout=30,
            )
            if deleted_workspaces:
                log_info(
                    f"Note: {len(deleted_workspaces)} soft-deleted Log Analytics workspace(s) under '{base_rg}' "
                    "are still pending Azure's 14-day retention window -- not billed, and the next `deploy` "
                    "recovers them automatically, nothing to clean up manually."
                )
        except Exception:  # noqa: BLE001 - purely informational, never fail the check over this
            pass

    return ok
