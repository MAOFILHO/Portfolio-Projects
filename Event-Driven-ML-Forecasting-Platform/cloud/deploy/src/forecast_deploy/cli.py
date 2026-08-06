from __future__ import annotations

from typing import Optional

import typer

from forecast_deploy.config import get_config
from forecast_deploy.console import (
    HealthRow,
    HealthStatus,
    console,
    log_error,
    log_info,
    log_success,
    log_warning,
    write_banner,
    write_health_row,
    write_key_value,
    write_section,
    write_summary_block,
)
from forecast_deploy.naming import list_matching_resource_groups, resource_group_exists
from forecast_deploy.runner import run as run_command
from forecast_deploy.state import delete_state, load_state, save_state
from forecast_deploy.steps import (
    s00_preflight,
    s01_azure_login,
    s02_resolve_names,
    s03_deploy_infra,
    s04_bootstrap_stack,
    s05_smoke_post,
)

app = typer.Typer(add_completion=False, help="Deploy Event-Driven-ML-Forecasting-Platform to a single Azure VM.")

PIPELINE = [
    s00_preflight,
    s01_azure_login,
    s02_resolve_names,
    s03_deploy_infra,
    s04_bootstrap_stack,
    s05_smoke_post,
]


@app.command()
def deploy(
    fresh: bool = typer.Option(False, "--fresh", help="Ignore any previous deployment state and start over"),
    location: Optional[str] = typer.Option(None, "-l", "--location", help="Override the Azure region"),
) -> None:
    """Run the full deployment pipeline (resumable)."""
    config = get_config()
    if location:
        config.azure_location = location

    write_banner("Event-Driven-ML-Forecasting-Platform — Deploy", f"region={config.azure_location}")

    state_file = config.state_file()
    if fresh:
        delete_state(state_file)
    state = load_state(state_file)

    for step_module in PIPELINE:
        if state.is_complete(step_module.STEP_NAME):
            console.print(f"\n  [dim]{step_module.STEP_TITLE} — already complete, skipping[/dim]")
            continue
        try:
            outputs = step_module.run(config, state)
        except Exception as exc:
            log_error(f"{step_module.STEP_NAME} failed: {exc}")
            save_state(state_file, state)
            log_error("Deployment stopped. Fix the issue above and re-run `forecast-deploy deploy` to resume from this step.")
            raise typer.Exit(code=1) from exc
        state.mark_complete(step_module.STEP_NAME, outputs)
        save_state(state_file, state)

    write_banner("Deployment Complete")
    outputs = state.resource_outputs
    write_section("Live URLs")
    write_key_value("Dashboard", outputs.get("DASHBOARD_URL", "?"))
    write_key_value("Airflow", outputs.get("AIRFLOW_URL", "?"))
    write_section("Airflow admin credentials (generated fresh for this deploy)")
    write_key_value("Username", outputs.get("AIRFLOW_ADMIN_USER", "admin"))
    write_key_value("Password", outputs.get("AIRFLOW_ADMIN_PASSWORD", "?"))
    write_section("Next steps")
    console.print("  1. Open the dashboard URL above and, separately, the Airflow URL to trigger a DAG run.")
    console.print("  2. Take your screenshots.")
    console.print("  3. Run `forecast-deploy smoke-test --stage post` any time to re-validate the live URLs.")
    console.print("  4. Run `forecast-deploy teardown -y` when done — this is billed per-second, so don't leave it running.\n")


@app.command()
def teardown(
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirmation prompt"),
) -> None:
    """Delete the resource group this deploy created, waiting for full completion."""
    config = get_config()
    state = load_state(config.state_file())
    known_rg = state.resource_outputs.get("RESOURCE_GROUP")

    # Prefer the exact name this local state file recorded (fast, no
    # listing call needed). Without one -- e.g. a GitHub Actions run, which
    # never has a prior `deploy`'s deployment_state.json -- fall back to
    # every resource group matching the base name pattern, so a deploy that
    # landed on an incremented suffix (because the base name collided with
    # a still-live prior run) isn't silently missed and left running.
    targets = [known_rg] if known_rg else list_matching_resource_groups(config)

    write_banner("Teardown", f"target(s): {', '.join(targets) if targets else '(none found)'}")

    if not targets:
        log_warning(f"No resource group matching '{config.resource_group_base}*' found — nothing to delete")
        delete_state(config.state_file())
        return

    if not yes:
        confirmed = typer.confirm(f"Delete resource group(s) {', '.join(targets)} and all their resources?")
        if not confirmed:
            log_warning("Teardown cancelled")
            raise typer.Exit(code=0)

    for resource_group in targets:
        if not resource_group_exists(resource_group):
            log_warning(f"{resource_group} does not exist — nothing to delete")
            continue
        log_info(f"Deleting {resource_group} (waiting for full completion, not fire-and-forget)")
        # Deliberately omitting --no-wait: the user wants confirmation the
        # deletion actually finished, not just that it was requested.
        run_command(["az", "group", "delete", "--name", resource_group, "--yes"], timeout=1800)
        log_success(f"{resource_group} deleted")

    delete_state(config.state_file())
    log_success("Local deployment state cleared. Run `forecast-deploy smoke-test --stage teardown` to confirm nothing is left behind.")


@app.command()
def status() -> None:
    """Show which deployment steps have completed."""
    config = get_config()
    state = load_state(config.state_file())

    if not state.completed_steps:
        console.print("No deployment in progress. Run `forecast-deploy deploy` to start.")
        return

    write_banner("Deployment Status")
    rows = []
    for step_module in PIPELINE:
        completed = state.is_complete(step_module.STEP_NAME)
        rows.append(HealthRow(
            step_module.STEP_TITLE,
            HealthStatus.PASS if completed else HealthStatus.PENDING,
            state.completed_steps[step_module.STEP_NAME].completed_at if completed else "not yet run",
        ))
    for row in rows:
        write_health_row(row)
    write_summary_block(rows, title="Pipeline Progress")


@app.command(name="smoke-test")
def smoke_test(
    stage: str = typer.Option(..., "--stage", help="'pre' (local prerequisites), 'post' (live deployment), or 'teardown' (confirms nothing billable is left)"),
) -> None:
    """Run pre-deploy, post-deploy, or post-teardown smoke checks."""
    config = get_config()

    if stage == "pre":
        from forecast_deploy.smoke import pre_deploy
        ok = pre_deploy.run(config)
    elif stage == "post":
        from forecast_deploy.smoke import post_deploy
        ok = post_deploy.run(config)
    elif stage == "teardown":
        from forecast_deploy.smoke import teardown_verify
        ok = teardown_verify.run(config)
    else:
        log_error("`--stage` must be 'pre', 'post', or 'teardown'")
        raise typer.Exit(code=2)

    raise typer.Exit(code=0 if ok else 1)


if __name__ == "__main__":
    app()
