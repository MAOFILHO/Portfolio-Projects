from __future__ import annotations

import shutil

from forecast_deploy.config import DeployConfig
from forecast_deploy.console import HealthRow, HealthStatus, log_step, write_health_row, write_summary_block
from forecast_deploy.runner import tool_version
from forecast_deploy.state import DeploymentState

STEP_NAME = "s00_preflight"
STEP_TITLE = "Preflight — checking required tools"

# az supports a --version flag; ssh-keygen's CLI differs enough between
# OpenSSH implementations (e.g. macOS's ssh-keygen has no -V/--version flag
# at all) that a plain existence check via PATH lookup is more portable than
# trying to parse a version string out of it.
REQUIRED_TOOLS = {
    "Azure CLI": (["az", "--version"], 2),
}
PATH_ONLY_TOOLS = ["ssh-keygen"]


def _major_version(version: str) -> int | None:
    digits = ""
    for ch in version.lstrip("v"):
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(0, 5, STEP_TITLE)

    rows: list[HealthRow] = []
    for label, (command, min_major) in REQUIRED_TOOLS.items():
        version = tool_version(command)
        if version is None:
            rows.append(HealthRow(label, HealthStatus.FAIL, "not found on PATH"))
            continue
        major = _major_version(version.split()[-2]) if label == "Azure CLI" else _major_version(version)
        if min_major is not None and (major is None or major < min_major):
            rows.append(HealthRow(label, HealthStatus.WARN, f"found but expected {min_major}.x+: {version}"))
        else:
            rows.append(HealthRow(label, HealthStatus.PASS, version[:60]))

    for label in PATH_ONLY_TOOLS:
        found = shutil.which(label)
        rows.append(HealthRow(label, HealthStatus.PASS if found else HealthStatus.FAIL, found or "not found on PATH"))

    bicep_ok = config.bicep_template().exists()
    rows.append(HealthRow(
        "Bicep template",
        HealthStatus.PASS if bicep_ok else HealthStatus.FAIL,
        str(config.bicep_template()),
    ))

    for row in rows:
        write_health_row(row)

    ok = write_summary_block(rows, title="Preflight")
    if not ok:
        raise RuntimeError("Preflight checks failed — install the missing tools above and re-run.")

    return {}
