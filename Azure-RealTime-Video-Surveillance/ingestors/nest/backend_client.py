from __future__ import annotations

import logging

import requests

logger = logging.getLogger("nest_ingestor.backend")


def post_frame(backend_url: str, camera_id: str, image_bytes: bytes, api_key: str = "") -> None:
    url = f"{backend_url.rstrip('/')}/api/v1/frames"
    headers = {"X-Api-Key": api_key} if api_key else {}
    response = requests.post(
        url,
        data={"camera_id": camera_id},
        files={"file": ("frame.jpg", image_bytes, "image/jpeg")},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    logger.info("Posted frame for %s -> %s", camera_id, response.json().get("blob_name"))
