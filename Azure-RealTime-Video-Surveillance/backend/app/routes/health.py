from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from surveil_core.storage import SurveillanceStorage

from app.deps import get_storage

logger = logging.getLogger("surveil.health")
router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health(storage: SurveillanceStorage = Depends(get_storage)):
    storage_ok = True
    detail = "ok"
    try:
        storage.list_recent_events(limit=1)
    except Exception as exc:  # pragma: no cover - exercised via smoke tests against live Azure
        storage_ok = False
        detail = str(exc)
        logger.warning("Health check: storage connectivity failed: %s", exc)

    return {
        "status": "healthy" if storage_ok else "degraded",
        "storage": "ok" if storage_ok else "unreachable",
        "detail": detail,
    }


@router.get("/")
async def root():
    return {"service": "azure-realtime-surveillance-backend", "status": "ok"}
