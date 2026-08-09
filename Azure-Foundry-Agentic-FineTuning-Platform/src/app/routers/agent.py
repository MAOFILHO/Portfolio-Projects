"""Agentic endpoint — drives the LangGraph orchestrator."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import jobs
from app.agents.orchestrator import classify, invoke

router = APIRouter(prefix="/agent", tags=["agent"])


class InvokeRequest(BaseModel):
    request: str = Field(default="", max_length=4000)
    demo: Literal["discovery", "finetune", "comparison"] | None = None


class RouteRequest(BaseModel):
    request: str = Field(min_length=1, max_length=4000)


@router.post("/route")
async def route(payload: RouteRequest) -> dict[str, Any]:
    """Show which sub-agent a request would go to, without running it."""
    demo, reason = classify(payload.request)
    return {"demo": demo, "reason": reason}


@router.post("/invoke")
async def agent_invoke(payload: InvokeRequest) -> dict[str, Any]:
    """Run the orchestrator; the supervisor routes to one sub-agent."""
    if not payload.request and not payload.demo:
        raise HTTPException(status_code=422, detail="provide either `request` or `demo`")

    state = await invoke(payload.request or (payload.demo or ""), payload.demo)

    if state.get("error"):
        # A blocked run is a real result, not a server fault — return it as data
        # with the trace so the UI can explain what happened.
        return {
            "demo": state.get("demo"),
            "route_reason": state.get("route_reason"),
            "error": state["error"],
            "result": state.get("result", {}),
            "trace": state.get("trace", []),
        }

    return {
        "demo": state.get("demo"),
        "route_reason": state.get("route_reason"),
        "result": state.get("result", {}),
        "trace": state.get("trace", []),
    }


@router.post("/invoke/start")
async def agent_invoke_start(payload: InvokeRequest) -> dict[str, Any]:
    """Kick off the orchestrator in the background and return immediately.

    Use this instead of /invoke for anything that might run long (live-mode
    discovery's evaluation can take 30-60 minutes) — poll GET /agent/jobs/{id}
    for progress and the final result. Unlike /invoke, the run survives a page
    refresh: it keeps going server-side and stays in the job registry (see
    app/jobs.py) regardless of whether anyone is still listening.
    """
    if not payload.request and not payload.demo:
        raise HTTPException(status_code=422, detail="provide either `request` or `demo`")

    demo = payload.demo or "discovery"
    record = jobs.start_job(demo, invoke(payload.request or (payload.demo or ""), payload.demo))
    return record.to_payload()


@router.get("/jobs/{job_id}")
async def agent_job_status(job_id: str) -> dict[str, Any]:
    """Poll a background job started via /agent/invoke/start."""
    record = jobs.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no job with id {job_id!r}")
    return record.to_payload()
