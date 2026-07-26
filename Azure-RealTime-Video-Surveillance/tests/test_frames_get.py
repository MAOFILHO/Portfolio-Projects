from __future__ import annotations

from azure.core.exceptions import ResourceNotFoundError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import get_storage
from app.routes import frames


class _FakeStorage:
    def __init__(self, frames: dict[str, bytes]) -> None:
        self._frames = frames

    def download_frame(self, blob_name: str) -> bytes:
        if blob_name not in self._frames:
            raise ResourceNotFoundError("no such blob")
        return self._frames[blob_name]


def _make_client(frames_by_blob_name: dict[str, bytes]) -> TestClient:
    app = FastAPI()
    app.include_router(frames.router)
    app.dependency_overrides[get_storage] = lambda: _FakeStorage(frames_by_blob_name)
    return TestClient(app)


def test_get_frame_returns_jpeg_bytes() -> None:
    image_bytes = b"\xff\xd8\xff\xe0fake-jpeg"
    client = _make_client({"nest-front-door/20260724T140714-abcd1234.jpg": image_bytes})

    response = client.get("/api/v1/frames/nest-front-door/20260724T140714-abcd1234.jpg")

    assert response.status_code == 200
    assert response.content == image_bytes
    assert response.headers["content-type"] == "image/jpeg"
    assert "max-age" in response.headers["cache-control"]


def test_get_frame_missing_blob_returns_404() -> None:
    client = _make_client({})

    response = client.get("/api/v1/frames/nest-front-door/does-not-exist.jpg")

    assert response.status_code == 404
