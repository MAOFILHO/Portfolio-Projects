"""Typer CLI entrypoint for Azure CDSS Pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.prompt import Confirm

from cdss_deploy.config import DeployConfig
from cdss_deploy.console import (
    StepTimer,
    console,
    print_banner,
    print_deployment_summary,
    print_status_table,
    print_step_done,
    print_step_fail,
    print_step_skip,
    print_step_start,
    print_substep,
)
from cdss_deploy.state import DeploymentState

app = typer.Typer(
    name="cdss-deploy",
    help="Automated zero-portal-click deployment of CDSS on Azure.",
    no_args_is_help=True,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / "deployment_state.json"

DEPLOY_STEPS = [
    ("s00_preflight", "Check prerequisites"),
    ("s01_azure_login", "Azure login and subscription"),
    ("s02_collect_secrets", "Collect API keys and secrets"),
    ("s03_deploy_infra", "Deploy Azure infrastructure (Bicep)"),
    ("s04_resolve_names", "Resolve deployed resource names"),
    ("s05_health_check", "Validate backend health"),
    ("s06_env_and_seed", "Generate env files and seed data"),
    ("s07_entra_auth", "Configure Entra ID authentication"),
    ("s08_pubmed_config", "Configure PubMed in production runtime"),
    ("s09_frontend_env", "Create frontend environment file"),
    ("s10_deploy_frontend", "Build and deploy React frontend"),
    ("s11_cors_and_redirect", "Configure CORS and redirect URIs"),
    ("s12_validate_e2e", "End-to-end validation"),
]


def _ensure_available_resource_group(base_name: str) -> str:
    """Check if the resource group exists or is being deleted; auto-increment if needed."""
    import json
    import re
    import subprocess

    match = re.match(r"^(.*?)(\d+)?$", base_name)
    prefix = match.group(1) if match else base_name
    suffix = int(match.group(2)) if match and match.group(2) else 0
    name = base_name

    for _ in range(20):
        try:
            result = subprocess.run(
                ["az", "group", "show", "--name", name, "-o", "json"],
                capture_output=True, text=True, timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return name

        if result.returncode != 0:
            return name

        rg_info = json.loads(result.stdout)
        state = rg_info.get("properties", {}).get("provisioningState", "")
        if state != "Deleting":
            return name
        console.print(
            f"[yellow]Resource group '{name}' is being deleted. "
            f"Trying next available name...[/yellow]"
        )
        suffix += 1
        name = f"{prefix}{suffix}"

    console.print(f"[green]Auto-selected resource group: {name}[/green]")
    return name


def _load_step_module(step_name: str):
    import importlib

    module = importlib.import_module(f"cdss_deploy.steps.{step_name}")
    return module


def _build_context(config: DeployConfig, state: DeploymentState) -> dict:
    source_dir = config.resolve_source_dir(PROJECT_ROOT)
    return {
        "config": config,
        "state": state,
        "project_root": PROJECT_ROOT,
        "source_dir": source_dir,
    }


@app.command()
def deploy(
    source_dir: Optional[str] = typer.Option(
        None, "--source-dir", "-s", help="Path to cdss-agentic-rag source directory"
    ),
    resource_group: Optional[str] = typer.Option(
        None, "--resource-group", "-g", help="Azure resource group name"
    ),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Azure region"),
    subscription: Optional[str] = typer.Option(
        None, "--subscription", help="Azure subscription ID"
    ),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment: dev|staging|prod"),
    resume: bool = typer.Option(True, "--resume/--fresh", help="Resume from last checkpoint"),
) -> None:
    """Deploy the full CDSS stack to Azure (zero portal clicks)."""
    print_banner()

    env_overrides = {}
    if source_dir:
        env_overrides["CDSS_SOURCE_DIR"] = source_dir
    if resource_group:
        env_overrides["AZURE_RESOURCE_GROUP"] = resource_group
    if location:
        env_overrides["AZURE_LOCATION"] = location
    if subscription:
        env_overrides["AZURE_SUBSCRIPTION_ID"] = subscription
    if environment:
        env_overrides["AZURE_ENVIRONMENT"] = environment

    import os
    for k, v in env_overrides.items():
        os.environ[k] = v

    try:
        config = DeployConfig()
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        console.print("[dim]Copy .env.example to .env and fill in required values.[/dim]")
        raise typer.Exit(1)

    if not resume:
        rg_name = _ensure_available_resource_group(config.azure_resource_group)
        if rg_name != config.azure_resource_group:
            os.environ["AZURE_RESOURCE_GROUP"] = rg_name
            config = DeployConfig()

    state = DeploymentState.load(STATE_FILE)
    if not resume:
        state.reset()

    state.resource_group = config.azure_resource_group
    state.location = config.azure_location
    state.subscription_id = config.azure_subscription_id
    state.save()

    source_dir_path = config.resolve_source_dir(PROJECT_ROOT)
    if not source_dir_path.exists():
        console.print(f"[red]Source directory not found: {source_dir_path}[/red]")
        console.print("[dim]Set CDSS_SOURCE_DIR or use --source-dir flag.[/dim]")
        raise typer.Exit(1)

    print_substep(f"Source: {source_dir_path}")
    print_substep(f"Resource Group: {config.azure_resource_group}")
    print_substep(f"Location: {config.azure_location}")
    print_substep(f"Environment: {config.azure_environment}")
    console.print()

    ctx = _build_context(config, state)
    total = len(DEPLOY_STEPS)
    failed = False

    for i, (step_name, description) in enumerate(DEPLOY_STEPS, 1):
        if state.is_completed(step_name) and resume:
            print_step_skip(i, description)
            continue

        print_step_start(i, total, description)
        state.mark_started(step_name)

        try:
            module = _load_step_module(step_name)
            with StepTimer() as timer:
                result = module.run(ctx)

            if result.get("success", True):
                state.mark_completed(step_name, outputs=result.get("outputs", {}))
                if result.get("resources"):
                    state.update_resources(result["resources"])
                print_step_done(i, description, timer.elapsed)
            else:
                error = result.get("error", "Unknown error")
                state.mark_failed(step_name, error)
                print_step_fail(i, description, error)
                failed = True
                break

        except Exception as e:
            state.mark_failed(step_name, str(e))
            print_step_fail(i, description, str(e))
            console.print_exception(show_locals=False)
            failed = True
            break

    console.print()
    if failed:
        console.print("[red bold]Deployment failed.[/red bold] Fix the error and re-run:")
        console.print("[dim]  cdss-deploy deploy  (resumes from failed step)[/dim]")
        raise typer.Exit(1)
    else:
        console.print("[green bold]Deployment complete![/green bold]")
        if state.deployed_resources:
            print_deployment_summary(state.deployed_resources)


@app.command()
def teardown(
    resource_group: Optional[str] = typer.Option(None, "--resource-group", "-g"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Also permanently purge soft-deleted Key Vault and Cognitive Services "
        "resources after the resource group finishes deleting. Irreversible: this "
        "removes the recovery window (90 days for Key Vault, 48h for Cognitive "
        "Services) and waits for the resource group deletion to complete first.",
    ),
) -> None:
    """Tear down all Azure resources created by this deployment."""
    print_banner()

    state = DeploymentState.load(STATE_FILE)
    rg = resource_group or state.resource_group

    if not rg:
        console.print("[red]No resource group specified. Use --resource-group or deploy first.[/red]")
        raise typer.Exit(1)

    if not yes:
        confirmed = Confirm.ask(
            f"[yellow]Delete ALL resources in '{rg}'? This cannot be undone.[/yellow]"
        )
        if not confirmed:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    if purge and not yes:
        confirmed_purge = Confirm.ask(
            "[yellow]--purge will also PERMANENTLY purge soft-deleted Key Vault and "
            "Cognitive Services resources, removing the recovery window entirely. Continue?[/yellow]"
        )
        if not confirmed_purge:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    module = _load_step_module("s13_teardown")
    ctx = {"state": state, "resource_group": rg, "purge": purge}
    result = module.run(ctx)

    if result.get("success"):
        console.print(f"[green]Resource group '{rg}' deletion initiated.[/green]")
        state.reset()
    else:
        console.print(f"[red]Teardown failed: {result.get('error')}[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show current deployment status."""
    print_banner()
    state = DeploymentState.load(STATE_FILE)

    if not state.steps:
        console.print("[dim]No deployment in progress. Run: cdss-deploy deploy[/dim]")
        return

    print_status_table(state.steps)

    if state.deployed_resources:
        print_deployment_summary(state.deployed_resources)


@app.command(name="smoke-test")
def smoke_test(
    stage: str = typer.Option("pre", help="pre or post"),
) -> None:
    """Run smoke tests (pre-deploy or post-deploy)."""
    print_banner()

    if stage == "pre":
        from cdss_deploy.smoke.pre_deploy import run_pre_checks

        try:
            config = DeployConfig()
            source_dir = config.resolve_source_dir(PROJECT_ROOT)
            import os
            os.environ.setdefault("CDSS_IMAGE_BUILD_MODE", config.cdss_image_build_mode)
        except Exception:
            source_dir = (PROJECT_ROOT / "../cdss-agentic-rag").resolve()
        success = run_pre_checks(source_dir)
    elif stage == "post":
        from cdss_deploy.smoke.post_deploy import run_post_checks

        state = DeploymentState.load(STATE_FILE)
        success = run_post_checks(state)
    else:
        console.print("[red]Stage must be 'pre' or 'post'.[/red]")
        raise typer.Exit(1)

    if not success:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
