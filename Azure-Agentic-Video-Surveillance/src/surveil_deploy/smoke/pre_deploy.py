from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import write_banner
from surveil_deploy.state import DeploymentState
from surveil_deploy.steps import s00_preflight


def run(config: DeployConfig) -> bool:
    write_banner("Pre-Deploy Smoke Test", "Verifying local prerequisites before touching Azure")
    try:
        s00_preflight.run(config, DeploymentState())
        return True
    except RuntimeError:
        return False
