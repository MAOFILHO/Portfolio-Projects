from __future__ import annotations

from azure.monitor.query import LogsQueryStatus
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_logs_client
from app.routes import observability


class _FakeRow(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key)


class _FakeTable:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = [_FakeRow(r) for r in rows]


class _FakeResponse:
    def __init__(self, rows: list[dict], status=LogsQueryStatus.SUCCESS) -> None:
        self.status = status
        self.tables = [_FakeTable(rows)]


class _FakeLogsClient:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def query_workspace(self, workspace_id: str, query: str, timespan):
        return _FakeResponse(self._rows)


def _make_client(rows: list[dict], workspace_id: str = "fake-workspace") -> TestClient:
    app = FastAPI()
    app.include_router(observability.router)
    app.dependency_overrides[get_settings] = lambda: Settings(log_analytics_workspace_id=workspace_id)
    app.dependency_overrides[get_logs_client] = lambda: _FakeLogsClient(rows)
    return TestClient(app)


def test_requests_summary_returns_buckets() -> None:
    client = _make_client([{"TimeGenerated": "2026-07-24T12:00:00Z", "total": 10, "failed": 1}])

    response = client.get("/api/v1/observability/requests-summary")

    assert response.status_code == 200
    assert response.json()["buckets"] == [{"timestamp": "2026-07-24T12:00:00Z", "total": 10, "failed": 1}]


def test_recent_exceptions_returns_list() -> None:
    client = _make_client(
        [{"TimeGenerated": "2026-07-24T12:00:00Z", "SeverityLevel": 3, "OuterMessage": "boom", "ProblemId": "abc"}]
    )

    response = client.get("/api/v1/observability/exceptions")

    assert response.status_code == 200
    assert response.json()["exceptions"] == [
        {"timestamp": "2026-07-24T12:00:00Z", "severity": 3, "message": "boom", "problem_id": "abc"}
    ]


def test_requests_summary_without_workspace_configured_returns_503() -> None:
    client = _make_client([], workspace_id="")

    response = client.get("/api/v1/observability/requests-summary")

    assert response.status_code == 503
