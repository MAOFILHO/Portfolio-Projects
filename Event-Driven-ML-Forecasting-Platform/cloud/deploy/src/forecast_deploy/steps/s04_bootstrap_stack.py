from __future__ import annotations

import time

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import log_info, log_step, log_success
from forecast_deploy.runner import run_json
from forecast_deploy.state import DeploymentState

STEP_NAME = "s04_bootstrap_stack"
STEP_TITLE = "Waiting for the VM to build and start the stack (first boot: ~15-20 min)"

POLL_INTERVAL_SECONDS = 20
DEADLINE_SECONDS = 35 * 60
CREDENTIAL_KEYS = {"PUBLIC_IP", "DASHBOARD_URL", "AIRFLOW_URL", "AIRFLOW_ADMIN_USER", "AIRFLOW_ADMIN_PASSWORD"}


def _run_on_vm(resource_group: str, vm_name: str, script: str) -> str:
    """Runs a shell one-liner on the VM via the Azure VM agent (no SSH
    round-trip needed) and returns its combined stdout+stderr."""
    result = run_json(
        [
            "az", "vm", "run-command", "invoke",
            "--resource-group", resource_group,
            "--name", vm_name,
            "--command-id", "RunShellScript",
            "--scripts", script,
            "-o", "json",
        ],
        timeout=120,
    )
    messages = result.get("value", []) if isinstance(result, dict) else []
    return "\n".join(m.get("message", "") for m in messages)


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(4, 5, STEP_TITLE)

    resource_group = state.resource_outputs["RESOURCE_GROUP"]
    vm_name = state.resource_outputs["VM_NAME"]
    public_ip = state.resource_outputs["PUBLIC_IP"]

    log_info("Polling for /opt/app/.ready -- first boot builds a ~7GB Airflow image plus the backend image, this is normally the slowest step")
    probe_script = (
        "if [ -f /opt/app/.ready ]; then echo __READY__; "
        "elif [ -f /opt/app/.failed ]; then echo __FAILED__; cat /opt/app/.failed; "
        "else echo __PENDING__; fi"
    )

    waited = 0
    while waited < DEADLINE_SECONDS:
        output = _run_on_vm(resource_group, vm_name, probe_script)
        if "__READY__" in output:
            log_success("Stack is up and healthy")
            break
        if "__FAILED__" in output:
            raise RuntimeError(f"bootstrap.sh failed on the VM:\n{output}")
        log_info(f"Still bootstrapping... ({waited}s elapsed, timeout at {DEADLINE_SECONDS}s)")
        time.sleep(POLL_INTERVAL_SECONDS)
        waited += POLL_INTERVAL_SECONDS
    else:
        raise RuntimeError(
            f"Timed out after {DEADLINE_SECONDS}s waiting for the VM to become ready. "
            f"SSH in (ssh {config.admin_username}@{public_ip}) and check "
            "/var/log/forecasting-bootstrap.log and `docker compose ps`."
        )

    creds_output = _run_on_vm(resource_group, vm_name, "cat /opt/app/.cloud-credentials")
    creds: dict[str, str] = {}
    for line in creds_output.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() in CREDENTIAL_KEYS:
            creds[key.strip()] = value.strip()

    return {
        "PUBLIC_IP": creds.get("PUBLIC_IP", public_ip),
        "DASHBOARD_URL": creds.get("DASHBOARD_URL", f"http://{public_ip}"),
        "AIRFLOW_URL": creds.get("AIRFLOW_URL", f"http://{public_ip}:8081"),
        "AIRFLOW_ADMIN_USER": creds.get("AIRFLOW_ADMIN_USER", "admin"),
        "AIRFLOW_ADMIN_PASSWORD": creds.get("AIRFLOW_ADMIN_PASSWORD", ""),
    }
