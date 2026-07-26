from __future__ import annotations

from fastapi import APIRouter, Depends
from surveil_core.alert_rules import DEFAULT_SEVERITY_MAP

from app.config import Settings, get_settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("")
async def get_current_settings(settings: Settings = Depends(get_settings)):
    """Read-only view of the alert configuration this deployment is running
    with. These values are baked into the Container App at deploy time from
    root .env -- not editable here; see docs/deployment.md to change them.
    """
    # ALERT_SEVERITY_MAP only overrides/extends the built-in defaults (see
    # AlertRuleConfig.severity_map), so the effective map -- not just the
    # override -- is what's actually meaningful to show here.
    effective_severity_map = {**DEFAULT_SEVERITY_MAP, **(settings.severity_map_dict() or {})}

    return {
        "alert_watch_tags": settings.watch_tags_list(),
        "alert_min_confidence": settings.alert_min_confidence,
        "alert_min_count": settings.alert_min_count,
        "capture_interval_seconds": settings.capture_interval_seconds,
        "analyzer_backend": settings.analyzer_backend,
        "alert_crowd_threshold": settings.alert_crowd_threshold,
        "alert_restricted_zone": settings.alert_restricted_zone,
        "alert_severity_map": effective_severity_map,
    }
