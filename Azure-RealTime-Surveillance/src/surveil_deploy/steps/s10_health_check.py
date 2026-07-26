from __future__ import annotations

import time

import httpx

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import HealthRow, HealthStatus, log_step, write_health_row, write_summary_block
from surveil_deploy.runner import run_json
from surveil_deploy.state import DeploymentState

STEP_NAME = "s10_health_check"
STEP_TITLE = "Post-deploy health check"

MAX_WAIT_SECONDS = 300
POLL_INTERVAL_SECONDS = 10


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(10, 12, STEP_TITLE)

    outputs = state.resource_outputs
    backend_fqdn = outputs["CONTAINER_APP_FQDN"]
    function_app_name = outputs["FUNCTION_APP_NAME"]
    resource_group = outputs["AZURE_RESOURCE_GROUP"]
    static_web_app_hostname = outputs["STATIC_WEB_APP_DEFAULT_HOSTNAME"]

    rows: list[HealthRow] = []

    backend_ok, backend_detail = _wait_for_backend(f"https://{backend_fqdn}/api/v1/health")
    rows.append(HealthRow("Backend /api/v1/health", HealthStatus.PASS if backend_ok else HealthStatus.FAIL, backend_detail))

    function_state = run_json(
        ["az", "functionapp", "show", "--name", function_app_name, "--resource-group", resource_group, "-o", "json"]
    ).get("state", "Unknown")
    rows.append(HealthRow("Function App state", HealthStatus.PASS if function_state == "Running" else HealthStatus.WARN, function_state))

    swa_ok = _check_url(f"https://{static_web_app_hostname}")
    rows.append(HealthRow("Static Web App reachable", HealthStatus.PASS if swa_ok else HealthStatus.WARN, static_web_app_hostname))

    if outputs.get("NEST_INGESTOR_ENABLED") == "True" and outputs.get("NEST_INGESTOR_CONTAINER_APP_NAME"):
        rows.append(_check_nest_ingestor(outputs["NEST_INGESTOR_CONTAINER_APP_NAME"], resource_group))

    for row in rows:
        write_health_row(row)

    ok = write_summary_block(rows, title="Health Check")
    if not ok:
        raise RuntimeError("Health check failed — see the Fail rows above. Re-run `surveil-deploy smoke-test --stage post` after investigating.")

    return {}


def _wait_for_backend(url: str) -> tuple[bool, str]:
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    last_error = "no response"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=10)
            if response.status_code == 200:
                return True, "200 OK"
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(POLL_INTERVAL_SECONDS)
    return False, f"timed out after {MAX_WAIT_SECONDS}s ({last_error})"


def _check_url(url: str) -> bool:
    try:
        response = httpx.get(url, timeout=10, follow_redirects=True)
        return response.status_code < 500
    except httpx.HTTPError:
        return False


# Azure Container Apps reports a fixed-scale revision (minReplicas ==
# maxReplicas, as the ingestor always is -- see nest-ingestor.bicep) as
# "RunningAtMaxScale" rather than plain "Running". Both mean healthy.
_HEALTHY_RUNNING_STATES = {"Running", "RunningAtMaxScale", "RunningAtMinScale"}


def _check_nest_ingestor(container_app_name: str, resource_group: str) -> HealthRow:
    # No HTTP endpoint to poll (outbound-only, no ingress) -- check the
    # latest revision's runningState instead.
    revisions = run_json([
        "az", "containerapp", "revision", "list",
        "--name", container_app_name, "--resource-group", resource_group, "-o", "json",
    ])
    running_state = revisions[0].get("properties", {}).get("runningState", "Unknown") if revisions else "not found"
    status = HealthStatus.PASS if running_state in _HEALTHY_RUNNING_STATES else HealthStatus.FAIL
    return HealthRow("Nest ingestor Container App", status, running_state)
