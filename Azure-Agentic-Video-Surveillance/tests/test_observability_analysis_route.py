from __future__ import annotations

from azure.monitor.query import LogsQueryStatus
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.deps import get_logs_client, get_monitoring_agent
from app.routes import observability


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
    """Returns different canned rows depending on which of the two KQL
    queries observability.py issues (distinguished by table name), so the
    /analysis route -- which runs both -- gets realistic per-query data.
    """

    def __init__(self, requests_rows: list[dict], exception_rows: list[dict]) -> None:
        self._requests_rows = requests_rows
        self._exception_rows = exception_rows

    def query_workspace(self, workspace_id: str, query: str, timespan):
        if "AppExceptions" in query:
            return _FakeResponse(self._exception_rows)
        return _FakeResponse(self._requests_rows)


class _FakeMonitoringAgent:
    def __init__(self, flags: list[str], severity: str, summary: str) -> None:
        self._flags = flags
        self._severity = severity
        self._summary = summary
        self.last_call: tuple | None = None

    async def analyze(self, requests_summary, exceptions):
        self.last_call = (requests_summary, exceptions)
        from surveil_core.agents.models import MonitoringReport

        return MonitoringReport(flags=self._flags, severity=self._severity, summary=self._summary)


def _make_client(requests_rows, exception_rows, agent: _FakeMonitoringAgent) -> TestClient:
    app = FastAPI()
    app.include_router(observability.router)
    app.dependency_overrides[get_settings] = lambda: Settings(log_analytics_workspace_id="fake-workspace")
    app.dependency_overrides[get_logs_client] = lambda: _FakeLogsClient(requests_rows, exception_rows)
    app.dependency_overrides[get_monitoring_agent] = lambda: agent
    return TestClient(app)


def test_analysis_route_returns_agent_report():
    agent = _FakeMonitoringAgent(flags=["failure spike"], severity="high", summary="Elevated failures.")
    client = _make_client(
        requests_rows=[{"TimeGenerated": "2026-07-24T12:00:00Z", "total": 100, "failed": 18}],
        exception_rows=[{"TimeGenerated": "2026-07-24T12:05:00Z", "SeverityLevel": 3, "OuterMessage": "boom", "ProblemId": "P1"}],
        agent=agent,
    )

    response = client.get("/api/v1/observability/analysis")

    assert response.status_code == 200
    assert response.json() == {"flags": ["failure spike"], "severity": "high", "summary": "Elevated failures."}
    requests_summary, exceptions = agent.last_call
    assert requests_summary == [{"timestamp": "2026-07-24T12:00:00Z", "total": 100, "failed": 18}]
    assert exceptions == [{"timestamp": "2026-07-24T12:05:00Z", "severity": 3, "message": "boom", "problem_id": "P1"}]


def test_analysis_route_without_workspace_configured_returns_503():
    agent = _FakeMonitoringAgent(flags=[], severity="low", summary="")
    app = FastAPI()
    app.include_router(observability.router)
    app.dependency_overrides[get_settings] = lambda: Settings(log_analytics_workspace_id="")
    app.dependency_overrides[get_logs_client] = lambda: _FakeLogsClient([], [])
    app.dependency_overrides[get_monitoring_agent] = lambda: agent
    client = TestClient(app)

    response = client.get("/api/v1/observability/analysis")

    assert response.status_code == 503
