from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import HealthRow, HealthStatus, log_step, write_health_row, write_summary_block
from surveil_deploy.runner import tool_version
from surveil_deploy.state import DeploymentState

STEP_NAME = "s00_preflight"
STEP_TITLE = "Preflight — checking required tools"

REQUIRED_TOOLS = {
    "Azure CLI": (["az", "--version"], 2),
    "Node.js": (["node", "--version"], 20),
    "npm": (["npm", "--version"], None),
    "Azure Functions Core Tools": (["func", "--version"], 4),
    "git": (["git", "--version"], None),
}


def _major_version(version: str) -> int | None:
    digits = ""
    for ch in version.lstrip("v"):
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(0, 12, STEP_TITLE)

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

    source_dir_ok = config.source_dir.exists() and (config.source_dir / "infra" / "main.bicep").exists()
    rows.append(HealthRow(
        "Source directory",
        HealthStatus.PASS if source_dir_ok else HealthStatus.FAIL,
        str(config.source_dir),
    ))

    for row in rows:
        write_health_row(row)

    ok = write_summary_block(rows, title="Preflight")
    if not ok:
        raise RuntimeError("Preflight checks failed — install the missing tools above and re-run.")

    return {}
