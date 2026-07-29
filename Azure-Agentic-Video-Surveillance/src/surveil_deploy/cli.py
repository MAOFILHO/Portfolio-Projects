from __future__ import annotations

from typing import Optional

import typer

from surveil_deploy.config import get_config
from surveil_deploy.console import (
    HealthRow,
    HealthStatus,
    console,
    log_error,
    log_success,
    log_warning,
    write_banner,
    write_health_row,
    write_key_value,
    write_section,
    write_summary_block,
)
from surveil_deploy.state import delete_state, load_state, save_state
from surveil_deploy.steps import (
    s00_preflight,
    s01_azure_login,
    s02_collect_secrets,
    s03_deploy_infra,
    s04_resolve_names,
    s05_build_backend,
    s06_deploy_ingestor,
    s07_deploy_function,
    s08_env_and_config,
    s09_deploy_frontend,
    s10_health_check,
    s11_validate_e2e,
    s12_teardown,
)

app = typer.Typer(add_completion=False, help="Zero-portal-click deployment CLI for Azure Real-Time Surveillance.")

PIPELINE = [
    s00_preflight,
    s01_azure_login,
    s02_collect_secrets,
    s03_deploy_infra,
    s04_resolve_names,
    s05_build_backend,
    s06_deploy_ingestor,
    s07_deploy_function,
    s08_env_and_config,
    s09_deploy_frontend,
    s10_health_check,
    s11_validate_e2e,
]


@app.command()
def deploy(
    fresh: bool = typer.Option(False, "--fresh", help="Ignore any previous deployment state and start over"),
    resource_group: Optional[str] = typer.Option(None, "-g", "--resource-group", help="Override AZURE_RESOURCE_GROUP"),
    location: Optional[str] = typer.Option(None, "-l", "--location", help="Override AZURE_LOCATION"),
) -> None:
    """Run the full deployment pipeline (resumable)."""
    config = get_config()
    if resource_group:
        config.azure_resource_group = resource_group
    if location:
        config.azure_location = location

    write_banner(
        "Azure Real-Time Surveillance — Deploy",
        f"env={config.azure_env_name}  region={config.azure_location}  rg={config.resource_group_name()}",
    )

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
            log_error("Deployment stopped. Fix the issue above and re-run `surveil-deploy deploy` to resume from this step.")
            raise typer.Exit(code=1) from exc
        state.mark_complete(step_module.STEP_NAME, outputs)
        save_state(state_file, state)

    write_banner("Deployment Complete", "Your surveillance system is live")
    outputs = state.resource_outputs
    write_section("Live URLs")
    if "FRONTEND_ORIGIN" in outputs:
        write_key_value("Dashboard", outputs["FRONTEND_ORIGIN"])
    if "API_BASE_URL" in outputs:
        write_key_value("Backend API", outputs["API_BASE_URL"])
    write_section("Next steps")
    console.print("  1. Open the dashboard URL above and grant camera permission.")
    console.print("  2. Start capture and confirm frames appear in the event feed.")
    console.print("  3. Run `surveil-deploy smoke-test --stage post` any time to re-validate.")
    console.print("  4. Run `surveil-deploy teardown` when done to avoid ongoing charges.\n")


@app.command()
def teardown(
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip the confirmation prompt"),
    purge: bool = typer.Option(False, "--purge", help="Also purge soft-deleted Cognitive Services accounts (irreversible)"),
) -> None:
    """Delete all Azure resources for this environment."""
    config = get_config()
    write_banner("Azure Real-Time Surveillance — Teardown", f"resource group: {config.resource_group_name()}")

    if not yes:
        confirmed = typer.confirm(f"Delete resource group '{config.resource_group_name()}' and all its resources?")
        if not confirmed:
            log_warning("Teardown cancelled")
            raise typer.Exit(code=0)

    state = load_state(config.state_file())
    s12_teardown.run(config, state, purge=purge)
    delete_state(config.state_file())
    if purge:
        log_success("Teardown complete (resources deleted, soft-deleted accounts purged). Local deployment state cleared.")
    else:
        log_success("Teardown initiated. Local deployment state cleared.")


@app.command()
def status() -> None:
    """Show which deployment steps have completed."""
    config = get_config()
    state = load_state(config.state_file())

    if not state.completed_steps:
        console.print("No deployment in progress. Run `surveil-deploy deploy` to start.")
        return

    write_banner("Deployment Status", f"env={config.azure_env_name}")
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
    stage: str = typer.Option(..., "--stage", help="'pre' (local prerequisites) or 'post' (live deployment validation)"),
) -> None:
    """Run pre- or post-deploy smoke checks."""
    config = get_config()

    if stage == "pre":
        from surveil_deploy.smoke import pre_deploy
        ok = pre_deploy.run(config)
    elif stage == "post":
        from surveil_deploy.smoke import post_deploy
        ok = post_deploy.run(config)
    else:
        log_error("`--stage` must be 'pre' or 'post'")
        raise typer.Exit(code=2)

    raise typer.Exit(code=0 if ok else 1)


if __name__ == "__main__":
    app()
