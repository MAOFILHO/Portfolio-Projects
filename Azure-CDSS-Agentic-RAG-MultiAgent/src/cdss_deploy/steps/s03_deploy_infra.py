"""Step 3: Deploy Azure infrastructure via bootstrap-deploy.sh (Bicep → 56+ resources).

This is the heaviest step — provisions VNet, Cosmos DB, OpenAI, AI Search,
Document Intelligence, Key Vault, Container Apps, ACR, Redis, Storage, and more.
Takes 15-30 minutes on first run.
"""

from __future__ import annotations

from cdss_deploy.console import console, print_substep
from cdss_deploy.runner import run_script


def run(ctx: dict) -> dict:
    config = ctx["config"]
    source_dir = ctx["source_dir"]

    script = source_dir / "infra" / "scripts" / "bootstrap-deploy.sh"
    if not script.exists():
        return {"success": False, "error": f"bootstrap-deploy.sh not found at {script}"}

    env_vars = config.env_vars_for_scripts
    env_vars["CDSS_PUBMED_API_KEY"] = config.cdss_pubmed_api_key
    env_vars["CDSS_PUBMED_EMAIL"] = config.cdss_pubmed_email

    args = [config.azure_environment, config.azure_resource_group, config.azure_location]

    console.print()
    print_substep(
        "Deploying infrastructure (this takes 15-30 minutes)...", "info"
    )
    print_substep(f"Environment: {config.azure_environment}", "info")
    print_substep(f"Resource Group: {config.azure_resource_group}", "info")
    print_substep(f"Location: {config.azure_location}", "info")
    console.print()

    result = run_script(
        script,
        args=args,
        env_overrides=env_vars,
        cwd=source_dir,
        auto_confirm=True,
        timeout=2400,
    )

    if not result.success:
        error_msg = result.stderr[-500:] if result.stderr else "Unknown error"
        return {"success": False, "error": f"Infrastructure deployment failed: {error_msg}"}

    print_substep("Infrastructure deployment completed", "ok")
    return {"success": True}
