from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_storage, get_vision_analyzer
from app.routes import frames


class _FakeStorage:
    def __init__(self, frames: dict[str, bytes]) -> None:
        self._frames = frames

    def download_frame(self, blob_name: str) -> bytes:
        if blob_name not in self._frames:
            raise ResourceNotFoundError("no such blob")
        return self._frames[blob_name]


class _FakeAnalyzer:
    def analyze_on_demand(self, image_bytes: bytes, feature_names: list[str]) -> dict:
        return {"received_features": feature_names, "byte_count": len(image_bytes)}


def _make_client(frames_by_blob_name: dict[str, bytes]) -> TestClient:
    app = FastAPI()
    app.include_router(frames.router)
    app.dependency_overrides[get_storage] = lambda: _FakeStorage(frames_by_blob_name)
    app.dependency_overrides[get_vision_analyzer] = lambda: _FakeAnalyzer()
    app.dependency_overrides[get_settings] = lambda: Settings(frame_upload_api_key="")
    return TestClient(app)


def test_analyze_frame_returns_analyzer_output() -> None:
    client = _make_client({"nest-front-door/frame.jpg": b"fake-jpeg-bytes"})

    response = client.post("/api/v1/frames/nest-front-door/frame.jpg/analyze", params={"features": "tags,read"})

    assert response.status_code == 200
    body = response.json()
    assert body["received_features"] == ["tags", "read"]
    assert body["byte_count"] == len(b"fake-jpeg-bytes")


def test_analyze_frame_rejects_unknown_feature() -> None:
    client = _make_client({"nest-front-door/frame.jpg": b"fake"})

    response = client.post("/api/v1/frames/nest-front-door/frame.jpg/analyze", params={"features": "bogus"})

    assert response.status_code == 400


def test_analyze_frame_missing_blob_returns_404() -> None:
    client = _make_client({})

    response = client.post("/api/v1/frames/nest-front-door/missing.jpg/analyze", params={"features": "tags"})

    assert response.status_code == 404
