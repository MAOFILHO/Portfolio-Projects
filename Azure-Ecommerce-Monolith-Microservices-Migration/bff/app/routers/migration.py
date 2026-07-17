import asyncio

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ..migration_engine import engine
from ..schemas import MigrationSnapshot, MigrationStartResponse

router = APIRouter(prefix="/api/migration", tags=["migration"])


@router.get("/status", response_model=MigrationSnapshot)
async def status():
    return engine.snapshot()


@router.post("/reset", response_model=MigrationSnapshot)
async def reset():
    """Resets step state back to pending AND restarts the monolith process if
    the last run decommissioned it — otherwise the UI would say 'monolith'
    is the active backend again while the process is actually still dead.
    This used to be two separate endpoints (/reset and /restart-monolith)
    that called the exact same engine.restart_monolith() and differed only
    in an error-message string — collapsed into one, since they were never
    actually different actions."""
    if engine.running:
        return engine.snapshot()
    ok = await engine.restart_monolith()
    if not ok:
        engine.last_error = "Timed out waiting for the monolith to come back up."
    return engine.snapshot()


@router.post("/start", response_model=MigrationStartResponse)
async def start(mode: str = "local"):
    if engine.running:
        return MigrationStartResponse(message="Migration already running")

    engine.last_error = None
    asyncio.create_task(engine.run(mode))
    return MigrationStartResponse(message=f"Migration started in {mode} mode")


@router.get("/stream")
async def stream():
    """SSE endpoint. The engine is the single source of truth for state (see
    migration_engine.py); this polls its snapshot rather than consuming an
    event queue, so a browser tab refreshing mid-migration reconnects safely
    and immediately sees the current state instead of missing past events."""

    async def event_generator():
        last_snapshot = None
        while True:
            snapshot = MigrationSnapshot.model_validate(engine.snapshot())
            if snapshot != last_snapshot:
                yield {"event": "state", "data": snapshot.model_dump_json()}
                last_snapshot = snapshot
            if not snapshot.running and last_snapshot is not None and all(
                s.status in ("done", "failed") for s in snapshot.steps
            ):
                yield {"event": "complete", "data": snapshot.model_dump_json()}
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
