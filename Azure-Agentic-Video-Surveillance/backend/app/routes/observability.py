from __future__ import annotations

import asyncio
from datetime import timedelta

from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from fastapi import APIRouter, Depends, HTTPException, Query
from surveil_core.agents import MonitoringAgent

from app.config import Settings, get_settings
from app.deps import get_logs_client, get_monitoring_agent

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])

# Same rationale as function_app.py's _AGENT_CALL_TIMEOUT_SECONDS: a
# rate-limited Azure OpenAI call can honor a `Retry-After` of thousands of
# seconds, which would otherwise hang this request far past any reasonable
# HTTP timeout.
_AGENT_CALL_TIMEOUT_SECONDS = 20.0

_REQUESTS_SUMMARY_QUERY = """
AppRequests
| where TimeGenerated > ago({hours}h)
| summarize total=count(), failed=countif(Success == false) by bin(TimeGenerated, 1h)
| order by TimeGenerated asc
"""

_RECENT_EXCEPTIONS_QUERY = """
AppExceptions
| where TimeGenerated > ago(24h)
| project TimeGenerated, SeverityLevel, OuterMessage, ProblemId
| order by TimeGenerated desc
| take {limit}
"""


def _run_query(client: LogsQueryClient, workspace_id: str, query: str, hours: int):
    # timespan restricts the query independently of the ago(...) filter
    # baked into the KQL text itself -- both must agree, or timespan silently
    # clips results the query text claims to be asking for.
    response = client.query_workspace(workspace_id=workspace_id, query=query, timespan=timedelta(hours=hours))
    if response.status != LogsQueryStatus.SUCCESS:
        raise HTTPException(status_code=502, detail="Log Analytics query did not fully succeed")
    return response.tables[0] if response.tables else None


@router.get("/requests-summary")
async def requests_summary(
    hours: int = Query(default=24, ge=1, le=168),
    settings: Settings = Depends(get_settings),
    client: LogsQueryClient = Depends(get_logs_client),
):
    """Hourly request count + failure count for the last N hours, from
    Application Insights (via its Log Analytics workspace) -- powers the
    Observability page's request volume chart.
    """
    if not settings.log_analytics_workspace_id:
        raise HTTPException(status_code=503, detail="Log Analytics workspace not configured")

    table = _run_query(
        client, settings.log_analytics_workspace_id, _REQUESTS_SUMMARY_QUERY.format(hours=hours), hours=hours
    )
    if table is None:
        return {"buckets": []}
    return {
        "buckets": [
            {"timestamp": row["TimeGenerated"], "total": row["total"], "failed": row["failed"]} for row in table.rows
        ]
    }


@router.get("/exceptions")
async def recent_exceptions(
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
    client: LogsQueryClient = Depends(get_logs_client),
):
    """Most recent exceptions across the backend + Function, from Application
    Insights via its Log Analytics workspace.
    """
    if not settings.log_analytics_workspace_id:
        raise HTTPException(status_code=503, detail="Log Analytics workspace not configured")

    table = _run_query(
        client, settings.log_analytics_workspace_id, _RECENT_EXCEPTIONS_QUERY.format(limit=limit), hours=24
    )
    if table is None:
        return {"exceptions": []}
    return {
        "exceptions": [
            {
                "timestamp": row["TimeGenerated"],
                "severity": row["SeverityLevel"],
                "message": row["OuterMessage"],
                "problem_id": row["ProblemId"],
            }
            for row in table.rows
        ]
    }


@router.get("/analysis")
async def observability_analysis(
    settings: Settings = Depends(get_settings),
    client: LogsQueryClient = Depends(get_logs_client),
    agent: MonitoringAgent = Depends(get_monitoring_agent),
):
    """AI analysis of the same request/exception data the two endpoints
    above surface as charts/tables -- flags anomalies in plain language.
    Advisory-only: this never pages/notifies anyone, it just answers the
    question a human would otherwise have to eyeball the dashboard for.
    """
    if not settings.log_analytics_workspace_id:
        raise HTTPException(status_code=503, detail="Log Analytics workspace not configured")

    requests_table = _run_query(
        client, settings.log_analytics_workspace_id, _REQUESTS_SUMMARY_QUERY.format(hours=24), hours=24
    )
    exceptions_table = _run_query(
        client, settings.log_analytics_workspace_id, _RECENT_EXCEPTIONS_QUERY.format(limit=20), hours=24
    )

    requests_summary = (
        [{"timestamp": row["TimeGenerated"], "total": row["total"], "failed": row["failed"]} for row in requests_table.rows]
        if requests_table is not None
        else []
    )
    exceptions = (
        [
            {
                "timestamp": row["TimeGenerated"],
                "severity": row["SeverityLevel"],
                "message": row["OuterMessage"],
                "problem_id": row["ProblemId"],
            }
            for row in exceptions_table.rows
        ]
        if exceptions_table is not None
        else []
    )

    try:
        report = await asyncio.wait_for(agent.analyze(requests_summary, exceptions), timeout=_AGENT_CALL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="The monitoring agent is temporarily unavailable (timed out) -- try again shortly.")
    return report.model_dump()
