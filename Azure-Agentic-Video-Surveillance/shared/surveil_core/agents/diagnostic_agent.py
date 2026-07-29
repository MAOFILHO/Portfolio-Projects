"""Nest WebRTC Diagnostic Agent: reads a structured JSONL log produced by
`ingestors/nest/diagnostics.py` during a single capture attempt and writes a
plain-language status report. Deliberately standalone from the Azure-deployed
path -- this is a local/on-demand investigative tool (see
`ingestors/nest/diagnose_webrtc.py`), not part of the production alerting
pipeline.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory

from .activity_log import log_agent_event
from .kernel_factory import get_chat_service

logger = logging.getLogger("surveil_core.agents.diagnostic")

_SYSTEM_PROMPT = """You are a WebRTC connectivity diagnostic assistant. You
receive a JSONL log of structured diagnostic events captured during a single
Nest camera WebRTC video-capture attempt (ICE/connection/signaling state
changes, SDP negotiation details, RTCP keyframe requests, inbound-rtp packet
stats, and H264 decode failures with their NAL unit types).

Write a short plain-language status report covering:
- Whether ICE/DTLS negotiation completed successfully.
- Whether video RTP packets were received at all, and whether any contained
  an IDR (keyframe) NAL unit.
- Whether the H264 decoder ever produced a usable frame.
- A plain-language hypothesis for what's going wrong, consistent with (or
  updating, if the evidence differs) the project's existing known
  conclusion: SDP/ICE/DTLS/RTP negotiate successfully and packets arrive,
  but the H264 decoder never emits a frame -- suspected to be an aiortc/
  Google-encoder interop gap below the application layer, compounded by most
  camera models never advertising CameraClipPreview at all (only the
  doorbell does).

Keep the report to a few short paragraphs of plain text, not JSON.
"""


class WebrtcDiagnosticAgent:
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self._service = get_chat_service(kernel)

    async def diagnose(self, log_path: Path | str) -> str:
        events = []
        with Path(log_path).open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        log_agent_event(logger, "WebrtcDiagnosticAgent", "invoke", model=self._service.ai_model_id, event_count=len(events))
        started = time.perf_counter()
        history = ChatHistory()
        history.add_system_message(_SYSTEM_PROMPT)
        history.add_user_message(json.dumps(events, default=str))
        settings = OpenAIChatPromptExecutionSettings()
        try:
            response = await self._service.get_chat_message_content(history, settings, kernel=self._kernel)
        except Exception as exc:
            log_agent_event(logger, "WebrtcDiagnosticAgent", "error", duration_ms=round((time.perf_counter() - started) * 1000), error=str(exc))
            raise
        report = str(response)
        log_agent_event(logger, "WebrtcDiagnosticAgent", "result", duration_ms=round((time.perf_counter() - started) * 1000))
        return report
