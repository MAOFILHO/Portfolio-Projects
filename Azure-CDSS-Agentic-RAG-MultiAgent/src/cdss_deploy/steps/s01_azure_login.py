"""Step 1: Azure login and subscription selection."""

from __future__ import annotations

import json

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_az, run_cmd


def run(ctx: dict) -> dict:
    config = ctx["config"]
    subscription_id = config.azure_subscription_id

    # Check if already logged in
    result = run_az(["account", "show"])
    if not result.success:
        print_substep("Not logged in to Azure CLI — launching browser login...", "info")
        login_result = run_cmd(["az", "login"], stream=True, timeout=120)
        if not login_result.success:
            return {"success": False, "error": f"Azure login failed: {login_result.stderr}"}

    # Set subscription
    print_substep(f"Setting subscription: {subscription_id}", "info")
    result = run_az(["account", "set", "--subscription", subscription_id])
    if not result.success:
        return {"success": False, "error": f"Failed to set subscription: {result.stderr}"}

    # Verify
    result = run_az(["account", "show"])
    if not result.success:
        return {"success": False, "error": "Failed to verify account"}

    try:
        account = json.loads(result.stdout)
        name = account.get("name", "Unknown")
        sub_id = account.get("id", "Unknown")
        tenant = account.get("tenantId", "Unknown")
        print_substep(f"Subscription: {name}", "ok")
        print_substep(f"Subscription ID: {sub_id}", "ok")
        print_substep(f"Tenant ID: {tenant}", "ok")
    except json.JSONDecodeError:
        print_substep("Logged in (could not parse account details)", "warn")

    return {
        "success": True,
        "resources": {"tenant_id": tenant, "subscription_id": sub_id},
    }
