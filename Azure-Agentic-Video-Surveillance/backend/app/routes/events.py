from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from surveil_core.storage import SurveillanceStorage

from app.deps import get_storage

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
async def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    storage: SurveillanceStorage = Depends(get_storage),
):
    """Recent analyzed frames (alerts and non-alerts), newest first."""
    events = storage.list_recent_events(limit=limit)
    return {"events": events, "count": len(events)}
