from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Detection(BaseModel):
    """A single tagged/object detection returned by a FrameAnalyzer."""

    tag: str
    confidence: float
    bounding_box: tuple[int, int, int, int] | None = None  # x, y, width, height


class SurveillanceEvent(BaseModel):
    """A persisted record of one analyzed frame, written to Azure Table Storage."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    camera_id: str
    frame_blob_name: str
    captured_at: datetime = Field(default_factory=_utcnow)
    analyzed_at: datetime = Field(default_factory=_utcnow)
    caption: str | None = None
    detections: list[Detection] = Field(default_factory=list)
    is_alert: bool = False
    matched_tags: list[str] = Field(default_factory=list)
    # "critical" | "high" | "medium" | "low" | None (no alert). See
    # alert_rules.compute_severity().
    severity: str | None = None


class AlertMessage(BaseModel):
    """Message enqueued on the 'alerts' Storage Queue and fanned out over WebSocket."""

    event_id: str
    camera_id: str
    frame_blob_name: str
    frame_url: str | None = None
    caption: str | None = None
    matched_tags: list[str]
    severity: str | None = None
    detections: list[Detection]
    triggered_at: datetime = Field(default_factory=_utcnow)
