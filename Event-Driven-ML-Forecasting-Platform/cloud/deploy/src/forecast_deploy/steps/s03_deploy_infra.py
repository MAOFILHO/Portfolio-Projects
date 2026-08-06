from __future__ import annotations

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import log_step, log_success
from forecast_deploy.runner import run as run_command, run_json
from forecast_deploy.state import DeploymentState

STEP_NAME = "s03_deploy_infra"
STEP_TITLE = "Deploying infrastructure — VNet, NSG, Public IP, VM, Log Analytics (Bicep)"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(3, 5, STEP_TITLE)

    resource_group = state.resource_outputs["RESOURCE_GROUP"]
    name_prefix = state.resource_outputs["NAME_PREFIX"]
    ssh_public_key = state.resource_outputs["SSH_PUBLIC_KEY"]

    deployment_name = f"forecast-deploy-{name_prefix}"

    result = run_json(
        [
            "az", "deployment", "sub", "create",
            "--name", deployment_name,
            "--location", config.azure_location,
            "--template-file", str(config.bicep_template()),
            "--parameters",
            f"resourceGroupName={resource_group}",
            f"namePrefix={name_prefix}",
            f"location={config.azure_location}",
            f"sshPublicKey={ssh_public_key}",
            f"adminUsername={config.admin_username}",
            f"vmSize={config.vm_size}",
            f"vmPriority={config.vm_priority}",
            f"osDiskSizeGb={config.os_disk_size_gb}",
            "-o", "json",
        ],
        timeout=900,
    )

    outputs = result["properties"]["outputs"]
    log_success(f"Infrastructure deployed to {resource_group}")

    return {
        "RESOURCE_GROUP": outputs["resourceGroupName"]["value"],
        "VM_NAME": outputs["vmName"]["value"],
        "PUBLIC_IP": outputs["publicIpAddress"]["value"],
        "LOG_ANALYTICS_WORKSPACE": outputs["logAnalyticsWorkspaceName"]["value"],
    }
