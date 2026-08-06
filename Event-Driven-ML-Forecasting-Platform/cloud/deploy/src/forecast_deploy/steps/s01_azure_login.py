from __future__ import annotations

import json

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import log_info, log_step, log_success, log_warning
from forecast_deploy.runner import run as run_command
from forecast_deploy.state import DeploymentState

STEP_NAME = "s01_azure_login"
STEP_TITLE = "Azure login — verifying subscription and generating an SSH key if needed"


def _ensure_ssh_keypair(config: DeployConfig) -> str:
    public_key_path = config.ssh_public_key_path
    if not public_key_path.exists():
        log_info(f"No SSH key found at {public_key_path} — generating one for the VM's admin user")
        private_key_path = public_key_path.with_suffix("")
        private_key_path.parent.mkdir(parents=True, exist_ok=True)
        run_command(
            ["ssh-keygen", "-t", "ed25519", "-f", str(private_key_path), "-N", "", "-C", "forecast-deploy"],
            stream=False,
        )
        log_success(f"Generated {public_key_path}")
    return public_key_path.read_text().strip()


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(1, 5, STEP_TITLE)

    result = run_command(["az", "account", "show", "-o", "json"], stream=False, check=False)
    if result.returncode != 0:
        log_warning("Not logged in to Azure CLI — launching `az login`")
        run_command(["az", "login"], stream=True)
        result = run_command(["az", "account", "show", "-o", "json"], stream=False)

    account = json.loads(result.stdout)
    log_success(f"Logged in as {account['user']['name']}")
    log_info(f"Subscription: {account['name']} ({account['id']})")

    if config.azure_subscription_id and config.azure_subscription_id != account["id"]:
        log_info(f"Switching to subscription {config.azure_subscription_id}")
        run_command(["az", "account", "set", "--subscription", config.azure_subscription_id])
        account["id"] = config.azure_subscription_id

    ssh_public_key = _ensure_ssh_keypair(config)

    return {
        "AZURE_SUBSCRIPTION_ID": account["id"],
        "AZURE_TENANT_ID": account.get("tenantId", ""),
        "SSH_PUBLIC_KEY": ssh_public_key,
    }
