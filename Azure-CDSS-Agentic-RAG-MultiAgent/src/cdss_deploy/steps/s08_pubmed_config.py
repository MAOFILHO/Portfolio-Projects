"""Step 8: Configure PubMed credentials in production runtime (Key Vault + secretRef)."""

from __future__ import annotations

import os

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_script


def run(ctx: dict) -> dict:
    config = ctx["config"]
    state = ctx["state"]
    source_dir = ctx["source_dir"]
    rg = config.azure_resource_group
    app_name = state.deployed_resources.get("app_name", "")
    kv_name = state.deployed_resources.get("kv_name", "")

    if not config.cdss_pubmed_api_key or not config.cdss_pubmed_email:
        print_substep("PubMed credentials not provided, skipping", "warn")
        return {"success": True}

    script = source_dir / "infra" / "scripts" / "configure-pubmed-prod.sh"
    if not script.exists():
        return {"success": False, "error": f"configure-pubmed-prod.sh not found at {script}"}

    env_vars = {
        "CDSS_PUBMED_API_KEY": config.cdss_pubmed_api_key,
        "CDSS_PUBMED_EMAIL": config.cdss_pubmed_email,
        "CDSS_KV_TEMP_IP_ALLOWLIST": str(config.cdss_kv_temp_ip_allowlist).lower(),
    }

    args = [rg, app_name, kv_name]

    print_substep("Writing PubMed credentials to Key Vault...", "info")
    result = run_script(
        script, args=args, env_overrides=env_vars, cwd=source_dir, timeout=600
    )

    if not result.success:
        error = result.stderr[-300:] if result.stderr else "Unknown error"
        if "ForbiddenByConnection" in error:
            print_substep(
                "Key Vault network restriction detected — retrying with IP allowlist...", "warn"
            )
            env_vars["CDSS_KV_TEMP_IP_ALLOWLIST"] = "true"
            result = run_script(
                script, args=args, env_overrides=env_vars, cwd=source_dir, timeout=900
            )
            if not result.success:
                return {"success": False, "error": f"PubMed config failed after retry: {result.stderr[-300:]}"}

    print_substep("PubMed credentials configured in runtime", "ok")
    return {"success": True}
