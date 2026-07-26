from __future__ import annotations

import logging
import os
import tempfile

import cv2
import requests

from auth import GoogleTokenManager

logger = logging.getLogger("nest_ingestor.sdm")

SDM_BASE_URL = "https://smartdevicemanagement.googleapis.com/v1"


class SdmClient:
    """Thin wrapper around the SDM API's executeCommand for event snapshots.

    Generating an image requires an eventId from an actual motion/person
    event (delivered via Pub/Sub) -- it cannot be called as an arbitrary
    on-demand snapshot. That's the piece the naive polling approach gets wrong.
    """

    def __init__(self, token_manager: GoogleTokenManager) -> None:
        self._tokens = token_manager

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tokens.get_access_token()}",
            "Content-Type": "application/json",
        }

    def generate_event_image(self, device_name: str, event_id: str) -> tuple[str, str]:
        """Returns (image_url, auth_token) for a fired camera event."""
        url = f"{SDM_BASE_URL}/{device_name}:executeCommand"
        body = {
            "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
            "params": {"eventId": event_id},
        }
        response = requests.post(url, headers=self._headers(), json=body, timeout=30)
        if not response.ok:
            logger.error("GenerateImage failed (%d): %s", response.status_code, response.text)
        response.raise_for_status()
        results = response.json()["results"]
        return results["url"], results["token"]

    def download_event_image(self, image_url: str, image_token: str) -> bytes:
        # SDM image URLs require the event token as a Basic auth value, not
        # the OAuth bearer token used for the rest of the API.
        headers = {"Authorization": f"Basic {image_token}"}
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content

    def generate_webrtc_stream(self, device_name: str, offer_sdp: str) -> dict:
        """Negotiates a WebRTC live stream session. Returns a dict with
        answerSdp, mediaSessionId, and expiresAt. This is the fallback for
        cameras that don't advertise CameraClipPreview -- it works on any
        WebRTC-capable device (which is now effectively all of them),
        unlike CameraEventImage, but requires a real media session
        (see webrtc_capture.py) rather than a simple HTTP GET.
        """
        url = f"{SDM_BASE_URL}/{device_name}:executeCommand"
        body = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream",
            "params": {"offerSdp": offer_sdp},
        }
        response = requests.post(url, headers=self._headers(), json=body, timeout=30)
        if not response.ok:
            logger.error("GenerateWebRtcStream failed (%d): %s", response.status_code, response.text)
        response.raise_for_status()
        return response.json()["results"]

    def stop_webrtc_stream(self, device_name: str, media_session_id: str) -> None:
        """Best-effort cleanup; failures here shouldn't break frame capture."""
        url = f"{SDM_BASE_URL}/{device_name}:executeCommand"
        body = {
            "command": "sdm.devices.commands.CameraLiveStream.StopWebRtcStream",
            "params": {"mediaSessionId": media_session_id},
        }
        try:
            response = requests.post(url, headers=self._headers(), json=body, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.warning("Failed to stop WebRTC stream %s (non-fatal)", media_session_id)

    def download_clip_preview_frame(self, preview_url: str) -> bytes:
        """Downloads a CameraClipPreview clip (an MP4, not an image) and
        returns its first frame as JPEG bytes. Unlike CameraEventImage, this
        needs no executeCommand call -- the previewUrl is delivered directly
        in the Pub/Sub message -- and works on WebRTC-only devices where
        GenerateImage 400s.
        """
        headers = {"Authorization": f"Bearer {self._tokens.get_access_token()}"}
        response = requests.get(preview_url, headers=headers, timeout=30)
        response.raise_for_status()

        # cv2.VideoCapture needs a real file path, not an in-memory buffer.
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        try:
            capture = cv2.VideoCapture(tmp_path)
            ok, frame = capture.read()
            capture.release()
            if not ok:
                raise ValueError("Could not decode a frame from the clip preview video")
            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                raise ValueError("Failed to JPEG-encode the extracted frame")
            return encoded.tobytes()
        finally:
            os.unlink(tmp_path)
