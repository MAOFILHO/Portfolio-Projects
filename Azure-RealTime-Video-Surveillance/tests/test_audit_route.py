from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_storage
from app.routes import audit


class _FakeStorage:
    def __init__(self) -> None:
        self.logged: list[dict] = []

    def log_audit_event(self, actor: str, action: str, details: str = "") -> None:
        self.logged.append({"actor": actor, "action": action, "details": details})

    def list_recent_audit_events(self, limit: int = 50) -> list[dict]:
        return self.logged[:limit]


def _make_client(api_key: str = "") -> tuple[TestClient, _FakeStorage]:
    app = FastAPI()
    app.include_router(audit.router)
    storage = _FakeStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_settings] = lambda: Settings(frame_upload_api_key=api_key)
    return TestClient(app), storage


def test_post_audit_event_logs_and_get_lists_it() -> None:
    client, storage = _make_client()

    post_response = client.post(
        "/api/v1/audit", json={"actor": "alice@contoso.com", "action": "sign_in", "details": ""}
    )
    assert post_response.status_code == 200
    assert storage.logged == [{"actor": "alice@contoso.com", "action": "sign_in", "details": ""}]

    get_response = client.get("/api/v1/audit")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["count"] == 1
    assert body["events"][0]["actor"] == "alice@contoso.com"


def test_post_audit_event_rejected_without_key_when_configured() -> None:
    client, _ = _make_client(api_key="secret123")

    response = client.post("/api/v1/audit", json={"actor": "alice", "action": "sign_in"})

    assert response.status_code == 401
