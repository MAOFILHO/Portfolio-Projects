"""In-memory background job registry for the orchestrator.

`POST /agent/invoke` (see routers/agent.py) is a single blocking request: the
whole LangGraph run happens inside one request/response cycle, and in live
mode that run can take 30-60 minutes. Two consequences follow from that:

1. A page refresh (or a lost connection) discards the response with no way to
   recover it, even though the run keeps going server-side and keeps billing.
2. There is nothing to poll for progress, because the server never talks back
   until the very end.

This module fixes both by running the orchestrator as a fire-and-forget
`asyncio.Task` tracked by a job id, with a lightweight progress-event log any
caller can poll. It is intentionally in-process/in-memory, not a persisted
queue — the goal is "survive a page refresh", not "survive a server restart"
or "scale across workers". A single-process dev/demo deployment is exactly
this project's target (see PLAN.md); if this ever runs behind multiple
workers, this registry stops being authoritative and would need to move to
shared storage (e.g. Redis) — flagged here rather than silently wrong.

`current_job_id` is a contextvar rather than a parameter threaded through
every function, so `report()` can be called from deep inside
`services/azure_foundry.py` (which has no idea a "job" concept exists) without
changing any of those function signatures. asyncio propagates contextvars
through nested awaits *and* into `asyncio.to_thread()` worker threads
automatically, so this works even though the actual Azure calls are
synchronous and run off the event loop (see mcp_servers/foundry_inference/
server.py's `to_thread` wrapping — without that, the event loop would be
blocked for the run's full duration and this polling endpoint couldn't
respond either).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Literal

JobStatus = Literal["running", "succeeded", "failed"]

current_job_id: ContextVar[str | None] = ContextVar("current_job_id", default=None)

#: Cap so a long-lived process doesn't accumulate unbounded event history if
#: a caller never stops polling a stale job.
_MAX_EVENTS = 500


@dataclass
class JobEvent:
    ts: float
    message: str


@dataclass
class JobRecord:
    job_id: str
    demo: str
    status: JobStatus = "running"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    events: list[JobEvent] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        now = self.finished_at or time.time()
        return {
            "job_id": self.job_id,
            "demo": self.demo,
            "status": self.status,
            "elapsed_seconds": round(now - self.started_at, 1),
            "events": [{"ts": e.ts, "message": e.message} for e in self.events],
            "trace": self.trace,
            "result": self.result,
            "error": self.error,
        }


_JOBS: dict[str, JobRecord] = {}


def report(message: str) -> None:
    """Append a progress event to the job currently running on this task/thread.

    A no-op outside a tracked job (e.g. during unit tests that call service
    functions directly), so nothing needs to guard calls to this.
    """
    job_id = current_job_id.get()
    if not job_id:
        return
    record = _JOBS.get(job_id)
    if record is None:
        return
    record.events.append(JobEvent(ts=time.time(), message=message))
    if len(record.events) > _MAX_EVENTS:
        del record.events[: len(record.events) - _MAX_EVENTS]


def get_job(job_id: str) -> JobRecord | None:
    return _JOBS.get(job_id)


def start_job(demo: str, coro: Any) -> JobRecord:
    """Register a job and run `coro` (an orchestrator.invoke(...) call) in the
    background. Returns immediately with the job record (status="running")."""
    job_id = uuid.uuid4().hex[:12]
    record = JobRecord(job_id=job_id, demo=demo)
    _JOBS[job_id] = record

    async def _runner() -> None:
        token = current_job_id.set(job_id)
        try:
            state = await coro
            record.trace = state.get("trace", [])
            record.result = state.get("result", {})
            record.error = state.get("error")
            record.status = "failed" if record.error else "succeeded"
        except Exception as exc:  # noqa: BLE001 - surfaced to the poller, not swallowed
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.finished_at = time.time()
            current_job_id.reset(token)

    asyncio.create_task(_runner())
    return record
