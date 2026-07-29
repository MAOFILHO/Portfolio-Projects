from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

INGESTOR_DIR = Path(__file__).resolve().parent


class NestIngestorConfig(BaseSettings):
    """Config for the Nest -> Azure ingestor. Deliberately separate from the
    root .env: this component has its own credential set (Google OAuth) with
    nothing else in common, whether it runs locally or as an Azure Container
    App.
    """

    model_config = SettingsConfigDict(env_file=str(INGESTOR_DIR / ".env"), extra="ignore")

    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    google_device_access_project_id: str = ""

    # Comma-separated "device_id:camera_id" pairs, one per camera you want
    # watched, e.g. "AVPHwEvy...:nest-front-yard,AVPHwEtp...:nest-front-door".
    # camera_id is just the label this camera shows up as in the dashboard/
    # event history -- pick anything.
    google_devices: str = ""

    gcp_pubsub_project_id: str = ""
    gcp_pubsub_subscription_id: str = "nest-surveillance-sub"

    watch_event_types: str = (
        "sdm.devices.events.CameraMotion.Motion,"
        "sdm.devices.events.CameraPerson.Person,"
        "sdm.devices.events.CameraClipPreview.ClipPreview"
    )

    backend_url: str = "http://localhost:8000"
    backend_api_key: str = ""

    def watch_event_types_list(self) -> list[str]:
        return [t.strip() for t in self.watch_event_types.split(",") if t.strip()]

    def devices(self) -> dict[str, str]:
        """Maps full SDM device name -> camera_id label for every configured device."""
        result: dict[str, str] = {}
        for pair in self.google_devices.split(","):
            pair = pair.strip()
            if not pair:
                continue
            device_id, _, camera_id = pair.partition(":")
            device_name = f"enterprises/{self.google_device_access_project_id}/devices/{device_id}"
            result[device_name] = camera_id
        return result

    def subscription_path(self) -> str:
        return f"projects/{self.gcp_pubsub_project_id}/subscriptions/{self.gcp_pubsub_subscription_id}"


@lru_cache
def get_config() -> NestIngestorConfig:
    return NestIngestorConfig()
