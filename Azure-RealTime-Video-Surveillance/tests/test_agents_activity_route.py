from __future__ import annotations

from azure.monitor.query import LogsQueryStatus
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_logs_client
from app.routes import agents


class _FakeRow(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key)


class _FakeTable:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = [_FakeRow(r) for r in rows]


class _FakeResponse:
    def __init__(self, rows: list[dict]) -> None:
        self.status = LogsQueryStatus.SUCCESS
        self.tables = [_FakeTable(rows)]


class _FakeLogsClient:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def query_workspace(self, workspace_id: str, query: str, timespan):
        return _FakeResponse(self._rows)


def _make_client(rows: list[dict], workspace_id: str = "fake-workspace") -> TestClient:
    app = FastAPI()
    app.include_router(agents.router)
    app.dependency_overrides[get_settings] = lambda: Settings(log_analytics_workspace_id=workspace_id)
    app.dependency_overrides[get_logs_client] = lambda: _FakeLogsClient(rows)
    return TestClient(app)


def test_agent_activity_returns_entries() -> None:
    client = _make_client(
        [{"TimeGenerated": "2026-07-28T20:31:56Z", "Message": "[AGENT] EventQueryAgent | invoke | model='gpt-5-mini'"}]
    )

    response = client.get("/api/v1/agents/activity")

    assert response.status_code == 200
    assert response.json()["entries"] == [
        {"timestamp": "2026-07-28T20:31:56Z", "message": "[AGENT] EventQueryAgent | invoke | model='gpt-5-mini'"}
    ]


def test_agent_activity_without_workspace_configured_returns_503() -> None:
    client = _make_client([], workspace_id="")

    response = client.get("/api/v1/agents/activity")

    assert response.status_code == 503
