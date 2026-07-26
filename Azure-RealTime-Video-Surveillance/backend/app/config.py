from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Identity — set by Container Apps to the user-assigned managed identity's
    # client ID in Azure; left empty for local dev (falls back to az CLI login).
    azure_client_id: str = ""

    storage_blob_endpoint: str = ""
    vision_endpoint: str = ""
    log_analytics_workspace_id: str = ""

    alert_watch_tags: str = "person"
    alert_min_confidence: float = 0.6
    alert_min_count: int = 1
    alert_crowd_threshold: int = 0
    alert_restricted_zone: str = ""
    alert_severity_map: str = ""
    capture_interval_seconds: int = 3
    # Display-only here (the backend doesn't run detection itself) -- shows
    # which FrameAnalyzer the Function is actually using, see Settings page.
    analyzer_backend: str = "azure_vision"

    acs_connection_string: str = ""
    acs_sender_email: str = ""
    acs_sms_from: str = ""
    alert_email_to: str = ""
    alert_sms_to: str = ""

    applicationinsights_connection_string: str = ""

    cors_allow_origins: str = "*"

    # Shared secret required on POST /api/v1/frames via the X-Api-Key header.
    # Empty (default) disables the check entirely -- backward compatible for
    # local dev and anyone running this project without the always-on Nest
    # ingestor enabled.
    frame_upload_api_key: str = ""

    def watch_tags_list(self) -> list[str]:
        return [t.strip() for t in self.alert_watch_tags.split(",") if t.strip()]

    def restricted_zone_tuple(self) -> tuple[float, float, float, float] | None:
        parts = [p.strip() for p in self.alert_restricted_zone.split(",") if p.strip()]
        if len(parts) != 4:
            return None
        try:
            x0, y0, x1, y1 = (float(p) for p in parts)
        except ValueError:
            return None
        return (x0, y0, x1, y1)

    def severity_map_dict(self) -> dict[str, str] | None:
        if not self.alert_severity_map.strip():
            return None
        mapping: dict[str, str] = {}
        for pair in self.alert_severity_map.split(","):
            if ":" not in pair:
                continue
            tag, _, severity = pair.partition(":")
            tag, severity = tag.strip().lower(), severity.strip().lower()
            if tag and severity:
                mapping[tag] = severity
        return mapping or None

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
