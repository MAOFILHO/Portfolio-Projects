from __future__ import annotations

import urllib.error
import urllib.request

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import HealthRow, HealthStatus, log_step, write_health_row, write_summary_block
from forecast_deploy.state import DeploymentState

STEP_NAME = "s05_smoke_post"
STEP_TITLE = "Post-deploy smoke test — checking the live URLs"

REQUEST_TIMEOUT_SECONDS = 15


def _check(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed http(s) URLs we just provisioned
            return response.status == 200, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - report any connection failure as a failed check, not a crash
        return False, str(exc)


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(5, 5, STEP_TITLE)

    dashboard_url = state.resource_outputs["DASHBOARD_URL"]
    airflow_url = state.resource_outputs["AIRFLOW_URL"]

    checks = [
        ("Frontend", dashboard_url + "/"),
        ("Backend API (via nginx proxy)", dashboard_url + "/api/health"),
        ("Airflow webserver", airflow_url + "/health"),
    ]

    rows: list[HealthRow] = []
    for label, url in checks:
        ok, detail = _check(url)
        rows.append(HealthRow(label, HealthStatus.PASS if ok else HealthStatus.FAIL, f"{url} -> {detail}"))

    for row in rows:
        write_health_row(row)

    ok = write_summary_block(rows, title="Post-deploy smoke test")
    if not ok:
        raise RuntimeError("One or more live URL checks failed -- see above. The VM may still be settling; re-run `forecast-deploy smoke-test --stage post` in a minute.")

    return {}
