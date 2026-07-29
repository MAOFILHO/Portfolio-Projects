from __future__ import annotations

from datetime import timedelta

from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.deps import get_logs_client

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Both the Function (Triage/Notification Policy agents, during frame
# analysis) and this backend (NL Query/Monitoring agents) log to the same
# Application Insights resource, tagged with the "[AGENT]" prefix (see
# shared/surveil_core/agents/activity_log.py) -- one query surfaces activity
# from both components, no separate telemetry pipeline needed.
_ACTIVITY_QUERY = """
AppTraces
| where Message startswith "[AGENT]"
| where TimeGenerated > ago({hours}h)
| project TimeGenerated, Message
| order by TimeGenerated desc
| take {limit}
"""


@router.get("/activity")
async def agent_activity(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    settings: Settings = Depends(get_settings),
    client: LogsQueryClient = Depends(get_logs_client),
):
    """Recent agent/orchestration log lines -- invocations, tool calls,
    results, errors -- across both the Function and this backend.
    """
    if not settings.log_analytics_workspace_id:
        raise HTTPException(status_code=503, detail="Log Analytics workspace not configured")

    response = client.query_workspace(
        workspace_id=settings.log_analytics_workspace_id,
        query=_ACTIVITY_QUERY.format(hours=hours, limit=limit),
        timespan=timedelta(hours=hours),
    )
    if response.status != LogsQueryStatus.SUCCESS:
        raise HTTPException(status_code=502, detail="Log Analytics query did not fully succeed")

    table = response.tables[0] if response.tables else None
    if table is None:
        return {"entries": []}
    return {
        "entries": [{"timestamp": row["TimeGenerated"], "message": row["Message"]} for row in table.rows]
    }
