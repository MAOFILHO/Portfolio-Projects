from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class DeployConfig(BaseSettings):
    """Every deployment knob, sourced from .env. Mirrors the ${ENV=default}
    convention used in Video-Agents-Foundry-Solution/infra/main.parameters.json:
    each setting has a sensible default so `.env` only needs to override what
    actually differs from the demo defaults.
    """

    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), extra="ignore")

    # Azure identity / target
    azure_subscription_id: str = ""
    azure_location: str = "eastus2"
    azure_resource_group: str = ""
    azure_env_name: str = "surveil"

    # Cost-relevant SKUs
    vision_sku: str = "S1"
    storage_sku_name: str = "Standard_LRS"

    # Alert rules
    alert_watch_tags: str = "person"
    alert_min_confidence: float = 0.6
    alert_min_count: int = 1
    capture_interval_seconds: int = 3

    # Crowd rule: alert when this many "person" detections appear in one
    # frame. 0 disables the rule.
    alert_crowd_threshold: int = 0
    # Trespassing rule: "x0,y0,x1,y1" normalized 0.0-1.0 restricted zone.
    # Empty disables the rule.
    alert_restricted_zone: str = ""
    # Optional override of the tag->severity map, "tag:severity,tag:severity"
    # (e.g. "gun:critical,dog:low"). Empty uses the built-in default (see
    # shared/surveil_core/alert_rules.py DEFAULT_SEVERITY_MAP).
    alert_severity_map: str = ""

    # Detection backend: "azure_vision" (default, pay-per-call, best accuracy)
    # or "ssd_mobilenet" (self-hosted MobileNet-SSD, no Azure cost, fixed set
    # of 20 PASCAL VOC classes, no caption) -- see docs/extending-phase2.md.
    analyzer_backend: str = "azure_vision"

    # Azure region for the Vision resource specifically -- must support Image
    # Analysis 4.0 Captions. Independent of azure_location since ARM cannot
    # move an existing resource between regions in-place (delete + purge +
    # recreate is required to change it after first deploy).
    vision_location: str = "eastus"

    # Azure Communication Services (email/SMS alerting)
    acs_sender_email: str = ""
    alert_email_to: str = ""
    alert_sms_to: str = ""
    acs_sms_from: str = ""

    # Build / deploy behavior
    image_build_mode: str = "acr"  # "acr" (cloud build, recommended) or "local"
    source_dir: Path = Field(default=REPO_ROOT)

    # Nest doorbell ingestor (opt-in; deploys an always-on Container App --
    # see docs/cost.md). All fields below are only required when enabled.
    nest_ingestor_enabled: bool = False
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_device_access_project_id: str = ""
    google_devices: str = ""
    gcp_pubsub_project_id: str = ""
    gcp_pubsub_subscription_id: str = "nest-surveillance-sub"
    gcp_service_account_key_path: Path = Field(default=Path(""))

    def resource_group_name(self) -> str:
        return self.azure_resource_group or f"{self.azure_env_name}-rg"

    def state_file(self) -> Path:
        return REPO_ROOT / "deployment_state.json"


@lru_cache
def get_config() -> DeployConfig:
    return DeployConfig()
