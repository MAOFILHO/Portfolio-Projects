"""Observability Monitoring Agent: reasons over the same Application
Insights/Log Analytics data the backend's Observability page already queries
(hourly request/failure counts, recent exceptions), flagging anomalies in
plain language instead of just charting them. Advisory-only in v1 -- it
flags, it does not page or notify anyone.
"""

from __future__ import annotations

import json
import logging
import time

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory

from .activity_log import log_agent_event
from .kernel_factory import get_chat_service
from .models import MonitoringReport

logger = logging.getLogger("surveil_core.agents.monitoring")

_SYSTEM_PROMPT = """You are an observability assistant for a surveillance
system's backend and Function. You receive hourly request/failure counts and
a list of recent exceptions, both queried from Application Insights.

Identify anomalies worth a human's attention: sudden failure-rate spikes,
clusters of the same exception (same ProblemId), or a request-volume drop
that suggests an outage rather than a quiet period. Use the severity
vocabulary "critical", "high", "medium", "low" (same as this system's alert
severities) for your overall assessment. If nothing looks unusual, say so
plainly with severity "low" and an empty flags list -- do not invent
problems.
"""


class MonitoringAgent:
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self._service = get_chat_service(kernel)

    async def analyze(self, requests_summary: list[dict], exceptions: list[dict]) -> MonitoringReport:
        log_agent_event(
            logger, "MonitoringAgent", "invoke",
            model=self._service.ai_model_id, request_buckets=len(requests_summary), exception_count=len(exceptions),
        )
        started = time.perf_counter()
        history = ChatHistory()
        history.add_system_message(_SYSTEM_PROMPT)
        history.add_user_message(
            f"Hourly request/failure buckets (most recent last): {json.dumps(requests_summary, default=str)}\n"
            f"Recent exceptions (newest first): {json.dumps(exceptions, default=str)}"
        )
        settings = OpenAIChatPromptExecutionSettings(response_format=MonitoringReport)
        try:
            response = await self._service.get_chat_message_content(history, settings, kernel=self._kernel)
            report = MonitoringReport.model_validate_json(str(response))
        except Exception as exc:
            log_agent_event(logger, "MonitoringAgent", "error", duration_ms=round((time.perf_counter() - started) * 1000), error=str(exc))
            raise
        log_agent_event(
            logger, "MonitoringAgent", "result",
            duration_ms=round((time.perf_counter() - started) * 1000), severity=report.severity, flag_count=len(report.flags),
        )
        return report
