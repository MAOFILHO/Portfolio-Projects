"""Tests for GET /api/streaming/windowed-features.

No Kafka broker, no Spark streaming query -- api.main reads Parquet directly
with pandas, so these tests just point WINDOWED_FEATURES_PATH at a fixture
(or nothing) and hit the endpoint via FastAPI's TestClient. This is the first
API-level test in the project; api.main is imported once per test process
(its module-level setup -- OUTPUT_DIR.mkdir, init_job_store -- runs against
the real backend/outputs/ dir, same as it would under uvicorn, since none of
that is streaming-specific).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import api.main as api_main  # noqa: E402

client = TestClient(api_main.app)


def test_returns_inactive_and_empty_when_directory_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "WINDOWED_FEATURES_PATH", tmp_path / "does-not-exist")

    response = client.get("/api/streaming/windowed-features")

    assert response.status_code == 200
    body = response.json()
    assert body == {"streaming_active": False, "features": []}


def test_returns_active_and_empty_when_no_windows_yet(tmp_path, monkeypatch):
    empty_df = pd.DataFrame(
        columns=["city", "window_start", "window_end", "avg_temperature", "min_temperature", "max_temperature", "event_count"]
    )
    path = tmp_path / "windowed_features"
    empty_df.to_parquet(path)
    monkeypatch.setattr(api_main, "WINDOWED_FEATURES_PATH", path)

    response = client.get("/api/streaming/windowed-features")

    assert response.status_code == 200
    body = response.json()
    assert body["streaming_active"] is True
    assert body["features"] == []


def test_returns_windowed_features_sorted_newest_first(tmp_path, monkeypatch):
    df = pd.DataFrame(
        [
            {
                "city": "Bombay",
                "window_start": pd.Timestamp("2026-01-01T00:00:00"),
                "window_end": pd.Timestamp("2026-01-01T00:00:10"),
                "avg_temperature": 25.0,
                "min_temperature": 24.0,
                "max_temperature": 26.0,
                "event_count": 3,
            },
            {
                "city": "London",
                "window_start": pd.Timestamp("2026-01-01T00:00:20"),
                "window_end": pd.Timestamp("2026-01-01T00:00:30"),
                "avg_temperature": 10.0,
                "min_temperature": 9.0,
                "max_temperature": 11.0,
                "event_count": 2,
            },
        ]
    )
    path = tmp_path / "windowed_features"
    df.to_parquet(path)
    monkeypatch.setattr(api_main, "WINDOWED_FEATURES_PATH", path)

    response = client.get("/api/streaming/windowed-features")

    assert response.status_code == 200
    body = response.json()
    assert body["streaming_active"] is True
    assert len(body["features"]) == 2
    # London's window starts later, so it must be sorted first.
    assert body["features"][0]["city"] == "London"
    assert body["features"][1]["city"] == "Bombay"
    assert body["features"][1]["avg_temperature"] == pytest.approx(25.0)
    assert body["features"][1]["event_count"] == 3


def test_degrades_gracefully_on_unreadable_directory(tmp_path, monkeypatch):
    """A Parquet directory can exist but be mid-write (non-atomic overwrite) --
    a read failure must degrade to the same 'not ready yet' response, not a 500."""
    path = tmp_path / "windowed_features"
    path.mkdir()
    (path / "not-actually-parquet.txt").write_text("garbage")
    monkeypatch.setattr(api_main, "WINDOWED_FEATURES_PATH", path)

    response = client.get("/api/streaming/windowed-features")

    assert response.status_code == 200
    assert response.json() == {"streaming_active": False, "features": []}
