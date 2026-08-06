from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/forecast_deploy/config.py -> forecast_deploy -> src -> deploy (this
# package's own root, where deployment_state.json lives, gitignored).
DEPLOY_ROOT = Path(__file__).resolve().parents[2]
# deploy -> cloud (contains infra/main.bicep and cloud-init/bootstrap.sh).
CLOUD_ROOT = DEPLOY_ROOT.parent


class DeployConfig(BaseSettings):
    """Every deployment knob, sourced from .env (in this package's own
    directory) or the environment -- same convention as
    Azure-Agentic-Video-Surveillance/src/surveil_deploy/config.py.
    """

    model_config = SettingsConfigDict(env_file=str(DEPLOY_ROOT / ".env"), extra="ignore")

    azure_subscription_id: str = ""
    azure_location: str = "eastus"

    # Base names before naming.py's incremental-suffix collision resolution
    # -- see naming.py for why these aren't made unique by a random/hash
    # suffix the way Azure-Agentic-Video-Surveillance's Bicep does.
    resource_group_base: str = "rg-forecasting-platform"
    name_prefix_base: str = "forecast"

    # D4s_v3, not D4s_v5: `az vm list-usage` showed 0 quota for every
    # v5-generation D-family SKU on this subscription (standardDSv5Family
    # etc. all Limit: 0), while v3/v4-generation families already had 10
    # cores of unused headroom -- same 4 vCPU/16GB shape, older CPU
    # generation, deploys immediately with no quota request needed.
    vm_size: str = "Standard_D4s_v3"
    # Regular, not Spot: this subscription's Spot/LowPriorityCores quota (3
    # cores) is too small for a 4-vCPU size regardless of generation, and
    # the smaller D2s_v5 Spot fallback that does fit it hit a separate
    # transient Spot capacity shortage in eastus. Regular pricing draws from
    # standard compute capacity instead -- still cheap for a 1-2 day demo
    # (~$4-8 total, billed per-second either way). Set to "Spot" once a
    # LowPriorityCores increase is confirmed, if the discount is worth the
    # added capacity/eviction risk.
    vm_priority: str = "Regular"
    os_disk_size_gb: int = 64
    admin_username: str = "azureuser"
    ssh_public_key_path: Path = Path.home() / ".ssh" / "id_ed25519.pub"

    def state_file(self) -> Path:
        return DEPLOY_ROOT / "deployment_state.json"

    def bicep_template(self) -> Path:
        return CLOUD_ROOT / "infra" / "main.bicep"


@lru_cache
def get_config() -> DeployConfig:
    return DeployConfig()
