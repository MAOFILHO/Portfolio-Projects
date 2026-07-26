from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraEvent:
    device_name: str
    event_type: str
    event_id: str | None
    preview_url: str | None = None


def parse_camera_events(message_data: bytes) -> list[CameraEvent]:
    """Parse an SDM Pub/Sub message payload into zero or more CameraEvents.

    SDM message shape (one message commonly carries multiple trait events for
    the same underlying occurrence):
    {
      "resourceUpdate": {
        "name": "enterprises/{project}/devices/{device_id}",
        "events": {
          "sdm.devices.events.CameraPerson.Person": {"eventId": "...", ...},
          "sdm.devices.events.CameraClipPreview.ClipPreview": {"previewUrl": "...", ...}
        }
      },
      ...
    }

    CameraEventImage.GenerateImage (keyed off eventId) only works on cameras
    that support RTSP; current WebRTC-only Nest hardware 400s on it despite
    advertising the trait. CameraClipPreview's previewUrl is delivered
    directly in the message and needs no extra command call, so it's
    preferred whenever present.
    """
    payload = json.loads(message_data)
    resource_update = payload.get("resourceUpdate")
    if not resource_update:
        return []

    device_name = resource_update.get("name", "")
    events = resource_update.get("events", {})

    parsed: list[CameraEvent] = []
    for event_type, event_body in events.items():
        event_id = event_body.get("eventId")
        preview_url = event_body.get("previewUrl")
        if event_id or preview_url:
            parsed.append(
                CameraEvent(
                    device_name=device_name,
                    event_type=event_type,
                    event_id=event_id,
                    preview_url=preview_url,
                )
            )
    return parsed
