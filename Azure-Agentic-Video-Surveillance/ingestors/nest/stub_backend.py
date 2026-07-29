"""Throw-away local stand-in for the real backend's POST /api/v1/frames.

Not part of the deployed system -- just lets you validate the Nest ingestor
(Pub/Sub subscription, SDM auth, event image download) works end-to-end
before deciding to deploy real Azure resources. Run with:

    uvicorn stub_backend:app --port 8000

Saves each received frame to ./received_frames/ so you can open it and
confirm it's actually your front yard, not a blank/black image.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stub_backend")

app = FastAPI()
OUTPUT_DIR = Path(__file__).parent / "received_frames"
OUTPUT_DIR.mkdir(exist_ok=True)


@app.post("/api/v1/frames")
async def upload_frame(camera_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    image_bytes = await file.read()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = OUTPUT_DIR / f"{camera_id}-{timestamp}.jpg"
    out_path.write_bytes(image_bytes)
    logger.info("Received frame for %s (%d bytes) -> saved to %s", camera_id, len(image_bytes), out_path)
    return {"blob_name": str(out_path), "url": str(out_path), "camera_id": camera_id}
