from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from surveil_core.storage import SurveillanceStorage

from app.deps import get_storage, require_frame_upload_key

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditEventIn(BaseModel):
    actor: str
    action: str
    details: str = ""


@router.post("", dependencies=[Depends(require_frame_upload_key)])
async def log_audit_event(
    event: AuditEventIn,
    storage: SurveillanceStorage = Depends(get_storage),
):
    """Records a user-facing action for the Audit Trail page.

    `actor` is whatever the frontend reports from Azure Static Web Apps'
    signed-in identity (see useAuth.ts) -- trusted client-side like the rest
    of this demo/portfolio system, not cryptographically verified server-side.
    """
    storage.log_audit_event(actor=event.actor, action=event.action, details=event.details)
    return {"status": "logged"}


@router.get("")
async def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    storage: SurveillanceStorage = Depends(get_storage),
):
    events = storage.list_recent_audit_events(limit=limit)
    return {"events": events, "count": len(events)}
