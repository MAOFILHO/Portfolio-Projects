from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_error, write_banner
from surveil_deploy.state import load_state
from surveil_deploy.steps import s10_health_check, s11_validate_e2e


def run(config: DeployConfig) -> bool:
    write_banner("Post-Deploy Smoke Test", "Validating the live deployment end-to-end")
    state = load_state(config.state_file())

    if not state.resource_outputs:
        log_error(f"No deployment state found at {config.state_file()}. Run `surveil-deploy deploy` first.")
        return False

    try:
        s10_health_check.run(config, state)
        s11_validate_e2e.run(config, state)
        return True
    except RuntimeError as exc:
        log_error(str(exc))
        return False
