from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from azure.core.exceptions import ResourceNotFoundError
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from surveil_core.storage import SurveillanceStorage

from app.deps import get_storage, require_frame_upload_key

logger = logging.getLogger("surveil.clips")
router = APIRouter(prefix="/api/v1/clips", tags=["clips"])

_ACCEPTED_CONTENT_TYPES = {"video/webm", "video/mp4"}
_EXTENSION_BY_CONTENT_TYPE = {"video/webm": "webm", "video/mp4": "mp4"}


def _blob_name(camera_id: str, content_type: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
    return f"{camera_id}/{timestamp}-{uuid4().hex[:8]}.{extension}"


@router.post("", dependencies=[Depends(require_frame_upload_key)])
async def upload_clip(
    camera_id: str = Form(...),
    file: UploadFile = File(...),
    storage: SurveillanceStorage = Depends(get_storage),
):
    """Upload a short (few-second) video clip captured client-side (browser
    MediaRecorder) -- a periodic companion to the per-frame capture path, for
    human review rather than automated analysis. Clips are not analyzed by
    the Function; alerting still runs on the regular JPEG frame path.
    """
    if file.content_type not in _ACCEPTED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Only {sorted(_ACCEPTED_CONTENT_TYPES)} clips are accepted")

    video_bytes = await file.read()
    if not video_bytes:
        raise HTTPException(status_code=400, detail="Empty clip payload")

    blob_name = _blob_name(camera_id, file.content_type)
    url = storage.upload_clip(
        camera_id=camera_id, blob_name=blob_name, video_bytes=video_bytes, content_type=file.content_type
    )
    logger.info("Uploaded clip %s (%d bytes) for camera %s", blob_name, len(video_bytes), camera_id)
    return {"blob_name": blob_name, "url": url, "camera_id": camera_id}


@router.get("")
async def list_clips(
    limit: int = Query(default=50, ge=1, le=200),
    storage: SurveillanceStorage = Depends(get_storage),
):
    clips = storage.list_recent_clips(limit=limit)
    return {"clips": clips, "count": len(clips)}


@router.get("/{camera_id}/{file_name}")
async def get_clip(
    camera_id: str,
    file_name: str,
    storage: SurveillanceStorage = Depends(get_storage),
):
    """Serve a previously-uploaded clip's raw video bytes -- same private-storage
    proxy rationale as GET /api/v1/frames/{camera_id}/{file_name}.
    """
    blob_name = f"{camera_id}/{file_name}"
    try:
        video_bytes, content_type = storage.download_clip(blob_name)
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Clip not found")
    return Response(
        content=video_bytes,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
