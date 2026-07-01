"""Step 9: Create frontend production environment file and ensure Static Web App exists."""

from __future__ import annotations

import json

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_az


SWA_NAME = "cdss-frontend-prod"
SPA_APP_DISPLAY_NAME = "cdss-frontend-spa"
API_APP_DISPLAY_NAME = "cdss-api"
SCOPE_NAME = "access_as_user"


def run(ctx: dict) -> dict:
    config = ctx["config"]
    state = ctx["state"]
    source_dir = ctx["source_dir"]
    rg = config.azure_resource_group
    location = config.azure_location
    api_fqdn = state.deployed_resources.get("api_fqdn", "")

    if config.cdss_skip_frontend_deploy:
        print_substep("Frontend deploy skipped (CDSS_SKIP_FRONTEND_DEPLOY=true)", "info")
        return {"success": True}

    # Ensure SWA exists
    swa_name = state.deployed_resources.get("swa_name", SWA_NAME)
    # SWA is only available in select regions; fallback to eastus2 if needed
    swa_regions = ["centralus", "eastus2", "westus2", "westeurope", "eastasia"]
    swa_location = location if location in swa_regions else "eastus2"

    result = run_az(["staticwebapp", "show", "--name", swa_name, "--resource-group", rg])
    if not result.success:
        print_substep(f"Creating Static Web App: {swa_name} in {swa_location}...", "info")
        result = run_az([
            "staticwebapp", "create",
            "--name", swa_name,
            "--resource-group", rg,
            "--location", swa_location,
            "--sku", "Standard",
        ])
        if not result.success:
            return {"success": False, "error": f"Failed to create SWA: {result.stderr}"}

    # Get SWA hostname
    result = run_az([
        "staticwebapp", "show", "--name", swa_name, "--resource-group", rg,
        "--query", "defaultHostname", "-o", "tsv",
    ])
    swa_host = result.stdout.strip() if result.success else ""

    # Get SWA deployment token
    result = run_az([
        "staticwebapp", "secrets", "list", "--name", swa_name,
        "--resource-group", rg, "--query", "properties.apiKey", "-o", "tsv",
    ])
    swa_token = result.stdout.strip() if result.success else ""

    if not swa_host or not swa_token:
        return {"success": False, "error": "Could not get SWA hostname or deployment token"}

    print_substep(f"SWA hostname: {swa_host}", "ok")

    # Get tenant ID
    result = run_az(["account", "show", "--query", "tenantId", "-o", "tsv"])
    tenant_id = result.stdout.strip() if result.success else ""

    # Get SPA client ID
    result = run_az([
        "ad", "app", "list", "--display-name", SPA_APP_DISPLAY_NAME,
        "--query", "[0].appId", "-o", "tsv",
    ])
    spa_client_id = result.stdout.strip() if result.success else ""

    # Get API identifier URI
    result = run_az([
        "ad", "app", "list", "--display-name", API_APP_DISPLAY_NAME,
        "--query", "[0].appId", "-o", "tsv",
    ])
    api_client_id = result.stdout.strip() if result.success else ""

    api_identifier_uri = ""
    if api_client_id:
        result = run_az([
            "ad", "app", "show", "--id", api_client_id,
            "--query", "identifierUris[0]", "-o", "tsv",
        ])
        api_identifier_uri = result.stdout.strip() if result.success else ""

    api_scope = f"{api_identifier_uri}/{SCOPE_NAME}" if api_identifier_uri else ""

    # WebPubSub check
    result = run_az([
        "resource", "list", "-g", rg,
        "--resource-type", "Microsoft.SignalRService/webPubSub",
        "--query", "[0].name", "-o", "tsv",
    ])
    webpubsub_name = result.stdout.strip() if result.success else ""
    ws_endpoint = (
        f"wss://{webpubsub_name}.webpubsub.azure.com"
        if webpubsub_name
        else f"wss://{api_fqdn}"
    )

    # Write frontend/.env.production
    env_content = (
        f"VITE_USE_MOCK_API=false\n"
        f"VITE_API_BASE_URL=https://{api_fqdn}/api\n"
        f"VITE_AZURE_CLIENT_ID={spa_client_id}\n"
        f"VITE_AZURE_TENANT_ID={tenant_id}\n"
        f"VITE_AZURE_AUTHORITY=https://login.microsoftonline.com/{tenant_id}\n"
        f"VITE_API_SCOPE={api_scope}\n"
        f"VITE_REDIRECT_URI=https://{swa_host}\n"
        f"VITE_POST_LOGOUT_URI=https://{swa_host}\n"
        f"VITE_WS_ENDPOINT={ws_endpoint}\n"
        f"VITE_ENVIRONMENT=production\n"
    )

    env_path = source_dir / "frontend" / ".env.production"
    env_path.write_text(env_content)
    print_substep(f"Wrote {env_path}", "ok")

    state.update_resources({
        "swa_name": swa_name,
        "swa_host": swa_host,
        "swa_token": swa_token,
        "spa_client_id": spa_client_id,
        "tenant_id": tenant_id,
    })

    return {"success": True}
