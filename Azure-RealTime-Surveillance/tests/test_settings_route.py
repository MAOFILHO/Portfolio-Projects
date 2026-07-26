from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.routes import settings as settings_route


def _make_client() -> TestClient:
    app = FastAPI()
    app.include_router(settings_route.router)
    app.dependency_overrides[get_settings] = lambda: Settings(
        alert_watch_tags="person,knife",
        alert_min_confidence=0.7,
        alert_min_count=2,
        capture_interval_seconds=5,
        analyzer_backend="ssd_mobilenet",
        alert_crowd_threshold=4,
        alert_restricted_zone="0.1,0.1,0.9,0.9",
    )
    return TestClient(app)


def test_get_settings_reflects_configured_values() -> None:
    client = _make_client()

    response = client.get("/api/v1/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["alert_watch_tags"] == ["person", "knife"]
    assert body["alert_min_confidence"] == 0.7
    assert body["alert_min_count"] == 2
    assert body["capture_interval_seconds"] == 5
    assert body["analyzer_backend"] == "ssd_mobilenet"
    assert body["alert_crowd_threshold"] == 4
    assert body["alert_restricted_zone"] == "0.1,0.1,0.9,0.9"
