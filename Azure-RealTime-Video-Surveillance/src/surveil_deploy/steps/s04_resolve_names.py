from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import run_json
from surveil_deploy.state import DeploymentState
from surveil_deploy.steps.s03_deploy_infra import DEPLOYMENT_NAME

STEP_NAME = "s04_resolve_names"
STEP_TITLE = "Resolving deployed resource names"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(4, 12, STEP_TITLE)

    # If s03 already captured outputs in this run, reuse them. This step
    # mainly matters when resuming a pipeline that crashed *after*
    # provisioning but *before* recording outputs (or when re-run manually
    # with `surveil-deploy status` showing s03 already complete).
    if state.is_complete("s03_deploy_infra") and state.resource_outputs:
        log_info("Reusing resource outputs captured during infrastructure deployment")
        outputs = state.resource_outputs
    else:
        log_info(f"Querying `az deployment sub show --name {DEPLOYMENT_NAME}` for outputs")
        payload = run_json(["az", "deployment", "sub", "show", "--name", DEPLOYMENT_NAME, "-o", "json"])
        # See s03_deploy_infra.py: ARM mangles the case of every Bicep output
        # name in the returned JSON; .upper() restores it since every
        # declared output name is fully uppercase.
        outputs = {
            k.upper(): v["value"]
            for k, v in payload.get("properties", {}).get("outputs", {}).items()
        }

    required = ["STORAGE_ACCOUNT_NAME", "VISION_ENDPOINT", "CONTAINER_APP_NAME", "FUNCTION_APP_NAME", "STATIC_WEB_APP_NAME"]
    missing = [key for key in required if not outputs.get(key)]
    if missing:
        raise RuntimeError(f"Missing expected deployment outputs: {missing}. Re-run `surveil-deploy deploy --fresh`.")

    log_success(f"Resolved {len(outputs)} resource outputs")
    return dict(outputs)
