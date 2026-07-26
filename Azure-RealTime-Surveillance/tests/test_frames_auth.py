from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_storage
from app.routes import frames


class _FakeStorage:
    def upload_frame(self, camera_id: str, blob_name: str, image_bytes: bytes) -> str:
        return f"https://fake.blob.core.windows.net/frames/{blob_name}"


def _make_client(api_key: str) -> TestClient:
    app = FastAPI()
    app.include_router(frames.router)
    app.dependency_overrides[get_storage] = lambda: _FakeStorage()
    app.dependency_overrides[get_settings] = lambda: Settings(frame_upload_api_key=api_key)
    return TestClient(app)


def _post_frame(client: TestClient, headers: dict[str, str] | None = None) -> object:
    return client.post(
        "/api/v1/frames",
        data={"camera_id": "nest-front-door"},
        files={"file": ("frame.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
        headers=headers or {},
    )


def test_upload_frame_allowed_when_no_key_configured() -> None:
    client = _make_client(api_key="")
    response = _post_frame(client)
    assert response.status_code == 200


def test_upload_frame_rejected_when_key_missing() -> None:
    client = _make_client(api_key="secret123")
    response = _post_frame(client)
    assert response.status_code == 401


def test_upload_frame_rejected_when_key_wrong() -> None:
    client = _make_client(api_key="secret123")
    response = _post_frame(client, headers={"X-Api-Key": "wrong"})
    assert response.status_code == 401


def test_upload_frame_allowed_when_key_correct() -> None:
    client = _make_client(api_key="secret123")
    response = _post_frame(client, headers={"X-Api-Key": "secret123"})
    assert response.status_code == 200
    assert response.json()["camera_id"] == "nest-front-door"
