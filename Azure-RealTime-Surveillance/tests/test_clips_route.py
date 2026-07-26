from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_storage
from app.routes import clips


class _FakeStorage:
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}
        self.clips: list[dict] = []

    def upload_clip(self, camera_id: str, blob_name: str, video_bytes: bytes, content_type: str) -> str:
        self.uploaded[blob_name] = video_bytes
        self.clips.append({"camera_id": camera_id, "blob_name": blob_name, "last_modified": "2026-07-24T00:00:00"})
        return f"https://fake.blob.core.windows.net/clips/{blob_name}"

    def download_clip(self, blob_name: str) -> tuple[bytes, str]:
        if blob_name not in self.uploaded:
            raise ResourceNotFoundError("no such blob")
        return self.uploaded[blob_name], "video/webm"

    def list_recent_clips(self, limit: int = 50) -> list[dict]:
        return self.clips[:limit]


def _make_client(api_key: str = "") -> tuple[TestClient, _FakeStorage]:
    app = FastAPI()
    app.include_router(clips.router)
    storage = _FakeStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_settings] = lambda: Settings(frame_upload_api_key=api_key)
    return TestClient(app), storage


def test_upload_clip_then_list_and_download() -> None:
    client, storage = _make_client()

    upload_response = client.post(
        "/api/v1/clips",
        data={"camera_id": "laptop-webcam"},
        files={"file": ("clip.webm", b"fake-webm-bytes", "video/webm")},
    )
    assert upload_response.status_code == 200
    blob_name = upload_response.json()["blob_name"]
    assert blob_name.startswith("laptop-webcam/") and blob_name.endswith(".webm")

    list_response = client.get("/api/v1/clips")
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1

    get_response = client.get(f"/api/v1/clips/{blob_name}")
    assert get_response.status_code == 200
    assert get_response.content == b"fake-webm-bytes"
    assert get_response.headers["content-type"] == "video/webm"


def test_upload_clip_rejects_bad_content_type() -> None:
    client, _ = _make_client()

    response = client.post(
        "/api/v1/clips",
        data={"camera_id": "laptop-webcam"},
        files={"file": ("clip.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_clip_rejected_without_key_when_configured() -> None:
    client, _ = _make_client(api_key="secret123")

    response = client.post(
        "/api/v1/clips",
        data={"camera_id": "laptop-webcam"},
        files={"file": ("clip.webm", b"bytes", "video/webm")},
    )

    assert response.status_code == 401


def test_get_clip_missing_returns_404() -> None:
    client, _ = _make_client()

    response = client.get("/api/v1/clips/laptop-webcam/does-not-exist.webm")

    assert response.status_code == 404
