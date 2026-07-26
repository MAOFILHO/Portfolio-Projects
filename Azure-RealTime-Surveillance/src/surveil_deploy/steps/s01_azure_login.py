from __future__ import annotations

import json

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success, log_warning
from surveil_deploy.runner import run as run_command
from surveil_deploy.state import DeploymentState

STEP_NAME = "s01_azure_login"
STEP_TITLE = "Azure login — verifying subscription and region"

# Regions confirmed to support Azure AI Vision Image Analysis 4.0 and
# Container Apps at the time this pipeline was written. Not exhaustive —
# treated as a warning, not a hard failure, since Azure adds regions often.
RECOMMENDED_REGIONS = {"eastus", "eastus2", "westus2", "westeurope", "swedencentral"}


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(1, 12, STEP_TITLE)

    result = run_command(["az", "account", "show", "-o", "json"], stream=False, check=False)
    if result.returncode != 0:
        log_warning("Not logged in to Azure CLI — launching `az login`")
        run_command(["az", "login"], stream=True)
        result = run_command(["az", "account", "show", "-o", "json"], stream=False)

    account = json.loads(result.stdout)
    log_success(f"Logged in as {account['user']['name']}")
    log_info(f"Current subscription: {account['name']} ({account['id']})")

    if config.azure_subscription_id and config.azure_subscription_id != account["id"]:
        log_info(f"Switching to subscription {config.azure_subscription_id}")
        run_command(["az", "account", "set", "--subscription", config.azure_subscription_id])
        account["id"] = config.azure_subscription_id

    if config.azure_location not in RECOMMENDED_REGIONS:
        log_warning(
            f"AZURE_LOCATION={config.azure_location} is not in the list of regions this pipeline "
            f"has been validated against ({', '.join(sorted(RECOMMENDED_REGIONS))}). "
            "Deployment may fail if Image Analysis 4.0 or Container Apps aren't available there."
        )
    else:
        log_success(f"Region {config.azure_location} is supported")

    return {"AZURE_SUBSCRIPTION_ID": account["id"], "AZURE_TENANT_ID": account.get("tenantId", "")}
