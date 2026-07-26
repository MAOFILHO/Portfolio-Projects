from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from azure.core.exceptions import ResourceNotFoundError
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from surveil_core.analyzer import AzureVisionAnalyzer
from surveil_core.storage import SurveillanceStorage

from app.deps import get_storage, get_vision_analyzer, require_frame_upload_key

logger = logging.getLogger("surveil.frames")
router = APIRouter(prefix="/api/v1/frames", tags=["frames"])

_VALID_ON_DEMAND_FEATURES = {"tags", "read", "smartcrops"}


def _blob_name(camera_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return f"{camera_id}/{timestamp}-{uuid4().hex[:8]}.jpg"


@router.post("", dependencies=[Depends(require_frame_upload_key)])
async def upload_frame(
    camera_id: str = Form(...),
    file: UploadFile = File(...),
    storage: SurveillanceStorage = Depends(get_storage),
):
    """Upload a captured JPEG frame. Analysis happens asynchronously in the
    Azure Function (blob-trigger on the 'frames' container); this endpoint's
    only job is to land the frame in Blob Storage quickly.
    """
    if file.content_type not in ("image/jpeg", "image/jpg"):
        raise HTTPException(status_code=400, detail="Only image/jpeg frames are accepted")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty frame payload")

    blob_name = _blob_name(camera_id)
    url = storage.upload_frame(camera_id=camera_id, blob_name=blob_name, image_bytes=image_bytes)
    logger.info("Uploaded frame %s (%d bytes) for camera %s", blob_name, len(image_bytes), camera_id)
    return {"blob_name": blob_name, "url": url, "camera_id": camera_id}


@router.get("/{camera_id}/{file_name}")
async def get_frame(
    camera_id: str,
    file_name: str,
    storage: SurveillanceStorage = Depends(get_storage),
):
    """Serve a previously-uploaded frame's raw JPEG bytes, for thumbnails in
    the dashboard's event history. No auth (matches GET /api/v1/events,
    which already exposes the same camera IDs and timestamps) -- this proxy
    exists because the storage account has allowSharedKeyAccess=false and
    only the backend's managed identity has data-plane read access, so the
    public frontend can't read blobs directly.
    """
    blob_name = f"{camera_id}/{file_name}"
    try:
        image_bytes = storage.download_frame(blob_name)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Frame not found")
    # Blob names are timestamp+uuid-suffixed and never overwritten, so the
    # content behind a given URL never changes -- safe to cache long-term.
    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


@router.post("/{camera_id}/{file_name}/analyze", dependencies=[Depends(require_frame_upload_key)])
async def analyze_frame(
    camera_id: str,
    file_name: str,
    features: str = Query(..., description="Comma-separated: tags, read, smartcrops"),
    storage: SurveillanceStorage = Depends(get_storage),
    analyzer: AzureVisionAnalyzer = Depends(get_vision_analyzer),
):
    """On-demand Vision analysis for a single already-uploaded frame, driven
    by dashboard buttons -- separate from the automatic per-frame detection
    the Function runs for alerting. Not cached: each click is a live,
    billed Vision API call (see docs/cost.md), by design -- these are rare,
    explicit user actions, not part of the always-on pipeline.
    """
    feature_names = [f.strip() for f in features.split(",") if f.strip()]
    unknown = set(feature_names) - _VALID_ON_DEMAND_FEATURES
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown feature(s): {sorted(unknown)}")
    if not feature_names:
        raise HTTPException(status_code=400, detail="No features requested")

    blob_name = f"{camera_id}/{file_name}"
    try:
        image_bytes = storage.download_frame(blob_name)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Frame not found")

    return analyzer.analyze_on_demand(image_bytes, feature_names)
