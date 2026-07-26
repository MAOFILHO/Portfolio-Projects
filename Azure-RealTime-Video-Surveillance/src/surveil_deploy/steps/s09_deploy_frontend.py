from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import run as run_command
from surveil_deploy.state import DeploymentState

STEP_NAME = "s09_deploy_frontend"
STEP_TITLE = "Building and deploying the React frontend"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(9, 12, STEP_TITLE)

    outputs = state.resource_outputs
    static_web_app_name = outputs["STATIC_WEB_APP_NAME"]
    resource_group = outputs["AZURE_RESOURCE_GROUP"]

    frontend_dir = config.source_dir / "frontend"

    log_info("Installing frontend dependencies (npm ci)")
    run_command(["npm", "ci"], cwd=frontend_dir)

    log_info("Building production bundle (npm run build)")
    run_command(["npm", "run", "build"], cwd=frontend_dir)

    log_info(f"Fetching deployment token for {static_web_app_name}")
    token_result = run_command(
        ["az", "staticwebapp", "secrets", "list", "--name", static_web_app_name,
         "--resource-group", resource_group, "--query", "properties.apiKey", "-o", "tsv"],
        stream=False,
    )
    deployment_token = token_result.stdout.strip()

    log_info("Deploying dist/ via the Static Web Apps CLI")
    run_command(
        ["npx", "--yes", "@azure/static-web-apps-cli", "deploy", "./dist",
         "--deployment-token", deployment_token, "--env", "production"],
        cwd=frontend_dir,
        stream=True,
    )

    log_success(f"Frontend deployed to https://{outputs['STATIC_WEB_APP_DEFAULT_HOSTNAME']}")
    return {}
