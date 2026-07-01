"""Step 7: Configure Entra SPA/API auth (app registrations, scopes, consent)."""

from __future__ import annotations

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_script


SPA_APP_DISPLAY_NAME = "cdss-frontend-spa"
API_APP_DISPLAY_NAME = "cdss-api"


def run(ctx: dict) -> dict:
    config = ctx["config"]
    state = ctx["state"]
    source_dir = ctx["source_dir"]
    rg = config.azure_resource_group
    app_name = state.deployed_resources.get("app_name", "")

    if config.cdss_skip_auth_setup:
        print_substep("Auth setup skipped (CDSS_SKIP_AUTH_SETUP=true)", "info")
        return {"success": True}

    script = source_dir / "infra" / "scripts" / "setup-entra-spa-auth.sh"
    if not script.exists():
        return {"success": False, "error": f"setup-entra-spa-auth.sh not found at {script}"}

    args = [
        "--resource-group", rg,
        "--container-app-name", app_name,
        "--spa-app-display-name", SPA_APP_DISPLAY_NAME,
        "--api-app-display-name", API_APP_DISPLAY_NAME,
    ]

    print_substep("Configuring Entra ID app registrations...", "info")
    result = run_script(script, args=args, cwd=source_dir, timeout=120)

    if not result.success:
        error = result.stderr[-300:] if result.stderr else "Unknown error"
        return {"success": False, "error": f"Entra auth setup failed: {error}"}

    print_substep("Entra SPA/API auth configured", "ok")
    return {
        "success": True,
        "resources": {
            "spa_app_display_name": SPA_APP_DISPLAY_NAME,
            "api_app_display_name": API_APP_DISPLAY_NAME,
        },
    }
