"""Structured (JSONL) diagnostic logging for WebRTC capture sessions.

Additive to the existing free-text `logger.warning`/`logger.info` calls
already in `webrtc_capture.py` -- this doesn't replace them, it gives the
same information a machine-parseable form so `diagnose_webrtc.py` can feed it
to `WebrtcDiagnosticAgent` instead of regex-parsing prose. Opt-in only (see
`webrtc_capture.set_diagnostic_log_path`); normal ingestor runs pay zero
overhead and write no files nobody asked for.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DiagnosticEvent(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: str
    camera_id: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class DiagnosticLogWriter:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._file = self._path.open("a", encoding="utf-8")

    def write(self, kind: str, camera_id: str | None = None, **fields: Any) -> None:
        event = DiagnosticEvent(kind=kind, camera_id=camera_id, fields=fields)
        self._file.write(event.model_dump_json() + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()
