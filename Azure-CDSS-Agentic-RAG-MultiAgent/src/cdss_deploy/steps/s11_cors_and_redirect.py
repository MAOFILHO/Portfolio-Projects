"""Step 11: Configure backend CORS and Entra redirect URIs for production frontend."""

from __future__ import annotations

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_az


def run(ctx: dict) -> dict:
    config = ctx["config"]
    state = ctx["state"]
    rg = config.azure_resource_group
    app_name = state.deployed_resources.get("app_name", "")
    swa_host = state.deployed_resources.get("swa_host", "")
    spa_client_id = state.deployed_resources.get("spa_client_id", "")

    if not swa_host:
        print_substep("SWA host not found, skipping CORS/redirect config", "warn")
        return {"success": True}

    # Set production redirect URIs on SPA app
    if spa_client_id:
        result = run_az([
            "ad", "app", "show", "--id", spa_client_id, "--query", "id", "-o", "tsv",
        ])
        spa_object_id = result.stdout.strip() if result.success else ""

        if spa_object_id:
            print_substep("Setting production redirect URIs...", "info")
            import json
            body = json.dumps({
                "spa": {
                    "redirectUris": [
                        f"https://{swa_host}",
                        f"https://{swa_host}/auth/callback",
                        "http://localhost:3000",
                        "http://localhost:3001",
                    ]
                }
            })
            result = run_az([
                "rest", "--method", "PATCH",
                "--uri", f"https://graph.microsoft.com/v1.0/applications/{spa_object_id}",
                "--headers", "Content-Type=application/json",
                "--body", body,
            ])
            if result.success:
                print_substep("Redirect URIs configured", "ok")
            else:
                print_substep(f"Redirect URI update warning: {result.stderr[-200:]}", "warn")
    else:
        print_substep("SPA client ID not found, skipping redirect URIs", "warn")

    # Configure backend CORS
    if app_name:
        print_substep("Updating backend CORS origins...", "info")
        result = run_az([
            "containerapp", "ingress", "cors", "update",
            "-g", rg, "-n", app_name,
            "--allowed-origins", f"https://{swa_host}",
        ])
        if result.success:
            print_substep(f"CORS allowed: https://{swa_host}", "ok")
        else:
            print_substep(f"CORS update warning: {result.stderr[-200:]}", "warn")

    return {"success": True}
