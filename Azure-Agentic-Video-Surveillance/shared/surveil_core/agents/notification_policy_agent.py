"""Notification Policy Agent: given an already-decided alert (severity and
matched tags are read-only context here), decides which delivery channels to
use and how to frame the message. Cannot affect `is_alert` or `severity`.
"""

from __future__ import annotations

import logging
import time

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory

from surveil_core.models import AlertMessage

from .activity_log import log_agent_event
from .kernel_factory import get_chat_service
from .models import NotificationDecision

logger = logging.getLogger("surveil_core.agents.notification_policy")

_SYSTEM_PROMPT = """You are a surveillance notification policy assistant. You
receive an already-finalized alert (severity, matched tags, caption) and
decide which of the available channels -- "email", "sms" -- should be used
to notify the owner, and a short one-sentence framing note.

Rules you MUST follow:
- You choose channels only. You cannot change whether this is an alert or
  what its severity is -- those are fixed inputs, not decisions you make.
- "critical" severity should almost always use every available channel
  unless there is a clear, stated reason not to (e.g. an explicit quiet-hours
  policy is not being modeled here in v1 -- default to all channels for
  critical).
- Prefer fewer channels for low-severity, non-urgent alerts to avoid
  notification fatigue, but never suppress the notification entirely --
  channels must contain at least one entry.
- Respond only with the requested structured fields.
"""


class NotificationPolicyAgent:
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self._service = get_chat_service(kernel)

    async def decide(self, alert: AlertMessage) -> NotificationDecision:
        log_agent_event(
            logger, "NotificationPolicyAgent", "invoke",
            model=self._service.ai_model_id, severity=alert.severity, camera_id=alert.camera_id,
        )
        started = time.perf_counter()
        history = ChatHistory()
        history.add_system_message(_SYSTEM_PROMPT)
        history.add_user_message(
            f"Severity: {alert.severity or 'none'}\n"
            f"Matched tags: {', '.join(alert.matched_tags) or 'none'}\n"
            f"Caption: {alert.caption or 'n/a'}\n"
            f"Camera: {alert.camera_id}"
        )
        settings = OpenAIChatPromptExecutionSettings(response_format=NotificationDecision)
        try:
            response = await self._service.get_chat_message_content(history, settings, kernel=self._kernel)
            decision = NotificationDecision.model_validate_json(str(response))
        except Exception as exc:
            log_agent_event(logger, "NotificationPolicyAgent", "error", duration_ms=round((time.perf_counter() - started) * 1000), error=str(exc))
            raise
        if not decision.channels:
            decision.channels = ["email", "sms"]
        log_agent_event(
            logger, "NotificationPolicyAgent", "result",
            duration_ms=round((time.perf_counter() - started) * 1000), channels=decision.channels,
        )
        return decision
