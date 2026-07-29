"""Natural-Language Event Query Agent: lets a user ask plain-English
questions about camera event history. Wraps `SurveillanceStorage.query_events`
as a Semantic Kernel plugin (function-calling tool) so the model extracts
structured query parameters from the question, then summarizes the results in
plain language -- never echoing raw entity field names back to the user.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Annotated

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import kernel_function

from surveil_core.alert_rules import SEVERITY_ORDER
from surveil_core.storage import SurveillanceStorage

from .activity_log import log_agent_event
from .kernel_factory import get_chat_service

logger = logging.getLogger("surveil_core.agents.query")

_VALID_SEVERITIES = set(SEVERITY_ORDER)

_SYSTEM_PROMPT = """You are an assistant that answers questions about a
camera surveillance system's event history by calling the `query_events`
tool. Convert the user's question into tool arguments (camera id, an ISO 8601
start/end datetime range, alert status, severity, and/or tags), call the
tool, then answer the user's question in plain, natural language based on
the returned events. Never show raw field names (e.g. PartitionKey, RowKey)
or JSON to the user -- describe what happened in plain English. If no events
match, say so plainly rather than guessing.
"""


class EventQueryPlugin:
    """Semantic Kernel plugin wrapping `SurveillanceStorage.query_events`."""

    def __init__(self, storage: SurveillanceStorage) -> None:
        self._storage = storage

    @kernel_function(
        name="query_events",
        description=(
            "Query surveillance camera events by camera, time range, alert status, "
            "severity, or matched tags. Returns matching event records as JSON."
        ),
    )
    def query_events(
        self,
        camera_id: Annotated[str, "Camera ID to filter by, or empty string for all cameras"] = "",
        start_iso: Annotated[str, "ISO 8601 start datetime (inclusive), or empty string for no lower bound"] = "",
        end_iso: Annotated[str, "ISO 8601 end datetime (inclusive), or empty string for no upper bound"] = "",
        is_alert: Annotated[str, "'true', 'false', or empty string for either"] = "",
        severity: Annotated[str, "'critical', 'high', 'medium', 'low', or empty string for any"] = "",
        tags_csv: Annotated[str, "Comma-separated matched tags to filter by, or empty string for any"] = "",
        limit: Annotated[int, "Maximum number of events to return"] = 20,
    ) -> Annotated[str, "JSON array of matching event records"]:
        # Validate every LLM-supplied argument before it reaches Table
        # Storage -- a malformed value here becomes an opaque OData
        # "InvalidInput" error from Azure instead of a clear one the model
        # can act on, and (confirmed live) Semantic Kernel's auto function-
        # calling retry only recovers from this by chance, not reliably.
        try:
            start = datetime.fromisoformat(start_iso) if start_iso else None
        except ValueError:
            return json.dumps({"error": f"start_iso {start_iso!r} is not a valid ISO 8601 datetime"})
        try:
            end = datetime.fromisoformat(end_iso) if end_iso else None
        except ValueError:
            return json.dumps({"error": f"end_iso {end_iso!r} is not a valid ISO 8601 datetime"})

        is_alert_bool = {"true": True, "false": False}.get(is_alert.strip().lower()) if is_alert else None

        severity_normalized = severity.strip().lower() if severity else ""
        if severity_normalized and severity_normalized not in _VALID_SEVERITIES:
            return json.dumps({"error": f"severity must be one of {sorted(_VALID_SEVERITIES)}, got {severity!r}"})

        limit = max(1, min(limit, 200))

        tags = [t.strip() for t in tags_csv.split(",") if t.strip()] or None

        log_agent_event(
            logger, "EventQueryAgent", "tool_call",
            tool="query_events", camera_id=camera_id or None, start_iso=start_iso or None, end_iso=end_iso or None,
            is_alert=is_alert_bool, severity=severity_normalized or None, tags=tags, limit=limit,
        )
        results, _ = self._storage.query_events(
            camera_id=camera_id.strip() or None,
            start=start,
            end=end,
            is_alert=is_alert_bool,
            severity=severity_normalized or None,
            tags=tags,
            limit=limit,
        )
        log_agent_event(logger, "EventQueryAgent", "tool_result", tool="query_events", row_count=len(results))
        return json.dumps(results, default=str)


class EventQueryAgent:
    def __init__(self, kernel: Kernel, storage: SurveillanceStorage) -> None:
        self._kernel = kernel
        self._service = get_chat_service(kernel)
        kernel.add_plugin(EventQueryPlugin(storage), plugin_name="events")

    async def answer(self, question: str) -> str:
        log_agent_event(logger, "EventQueryAgent", "invoke", model=self._service.ai_model_id, question=question)
        started = time.perf_counter()
        history = ChatHistory()
        history.add_system_message(_SYSTEM_PROMPT)
        history.add_user_message(question)
        settings = OpenAIChatPromptExecutionSettings(function_choice_behavior=FunctionChoiceBehavior.Auto())
        try:
            response = await self._service.get_chat_message_content(history, settings, kernel=self._kernel)
        except Exception as exc:
            log_agent_event(logger, "EventQueryAgent", "error", duration_ms=round((time.perf_counter() - started) * 1000), error=str(exc))
            raise
        answer = str(response)
        log_agent_event(
            logger, "EventQueryAgent", "result",
            duration_ms=round((time.perf_counter() - started) * 1000), answer_preview=answer[:120],
        )
        return answer
