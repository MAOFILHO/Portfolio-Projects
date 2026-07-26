from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import run as run_command, run_json
from surveil_deploy.state import DeploymentState

STEP_NAME = "s08_env_and_config"
STEP_TITLE = "Generating frontend environment and wiring CORS"


def _fetch_frame_upload_api_key(container_app_name: str, resource_group: str) -> str:
    secrets = run_json([
        "az", "containerapp", "secret", "list",
        "--name", container_app_name, "--resource-group", resource_group,
        "--show-values", "-o", "json",
    ])
    for secret in secrets:
        if secret.get("name") == "frame-upload-api-key":
            return secret.get("value", "")
    return ""


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(8, 12, STEP_TITLE)

    outputs = state.resource_outputs
    backend_fqdn = outputs["CONTAINER_APP_FQDN"]
    static_web_app_hostname = outputs["STATIC_WEB_APP_DEFAULT_HOSTNAME"]
    resource_group = outputs["AZURE_RESOURCE_GROUP"]
    container_app_name = outputs["CONTAINER_APP_NAME"]

    api_base_url = f"https://{backend_fqdn}"
    ws_url = f"wss://{backend_fqdn}/ws/alerts"
    frontend_origin = f"https://{static_web_app_hostname}"

    # The browser dashboard is a public static site, so this "shared secret"
    # is really just an anti-scraping gate (embedded in the public JS bundle,
    # same trust model as the Nest ingestor's copy of this key) -- not a
    # substitute for real per-user auth. Fine for this project's stated
    # demo/portfolio scope (see README Disclaimer); flagging here so it's a
    # deliberate choice, not an oversight, if this ever needs to be hardened.
    frame_upload_api_key = _fetch_frame_upload_api_key(container_app_name, resource_group)

    subscription_id = outputs["AZURE_SUBSCRIPTION_ID"]
    appinsights_name = outputs.get("APPINSIGHTS_NAME", "")
    appinsights_portal_url = (
        f"https://portal.azure.com/#resource/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}/providers/microsoft.insights/components/{appinsights_name}/overview"
        if appinsights_name
        else ""
    )

    # Quoted: VITE_APPINSIGHTS_PORTAL_URL contains a `#` (Azure Portal deep
    # links are fragment-based), and dotenv-style parsers -- including
    # Vite's -- treat an unquoted `#` as starting an inline comment, silently
    # truncating everything after it. Quoting every value here defensively,
    # not just that one, since it's cheap and removes the failure mode
    # entirely for any future value that happens to contain `#` or `=`.
    env_path = config.source_dir / "frontend" / ".env.production"
    env_path.write_text(
        f'VITE_API_BASE_URL="{api_base_url}"\n'
        f'VITE_WS_URL="{ws_url}"\n'
        f'VITE_API_KEY="{frame_upload_api_key}"\n'
        f'VITE_APPINSIGHTS_PORTAL_URL="{appinsights_portal_url}"\n'
    )
    log_success(f"Wrote {env_path}")

    log_info(f"Restricting backend CORS to {frontend_origin}")
    run_command([
        "az", "containerapp", "update",
        "--name", container_app_name,
        "--resource-group", resource_group,
        "--set-env-vars", f"CORS_ALLOW_ORIGINS={frontend_origin}",
    ])

    return {
        "API_BASE_URL": api_base_url,
        "WS_URL": ws_url,
        "FRONTEND_ORIGIN": frontend_origin,
    }
