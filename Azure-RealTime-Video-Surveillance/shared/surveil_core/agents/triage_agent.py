"""Triage Agent: reviews a rule-engine alert and may recommend an upward
severity escalation or a (never auto-applied) suppression, with a mandatory
reason. Never touches `critical` -- callers must not invoke this agent at all
once the rule engine has already classified something as critical; see the
guardrail in `function_app.py`.
"""

from __future__ import annotations

import logging
import time

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.contents import ChatHistory

from .activity_log import log_agent_event
from .kernel_factory import get_chat_service
from .models import TriageResult

logger = logging.getLogger("surveil_core.agents.triage")

_SYSTEM_PROMPT = """You are a surveillance alert triage assistant. You receive
a single frame's detection results (caption, matched tags, and the severity
already assigned by a deterministic rule engine) and decide whether context
justifies adjusting the response.

Rules you MUST follow, with no exceptions:
- You may only recommend escalating severity upward, through this exact
  order: low -> medium -> high -> critical. Never recommend a downward
  change.
- The input severity is never "critical" when you are called (the caller
  filters that case out before invoking you) -- do not assume otherwise, and
  never output "escalated_severity" for a case you believe should be
  downgraded.
- You may RECOMMEND suppression (e.g. an obviously repeated/duplicate
  detection) but you do not have the authority to suppress anything
  yourself -- always provide a `suppress_reason` when `suppress_recommended`
  is true. The caller decides whether to act on this recommendation.
- Respond only with the requested structured fields. Keep `reasoning` to one
  or two sentences.
"""


class TriageAgent:
    def __init__(self, kernel: Kernel) -> None:
        self._kernel = kernel
        self._service = get_chat_service(kernel)

    async def triage(self, caption: str | None, matched_tags: list[str], rule_severity: str | None) -> TriageResult:
        log_agent_event(
            logger, "TriageAgent", "invoke",
            model=self._service.ai_model_id, rule_severity=rule_severity, matched_tags=matched_tags,
        )
        started = time.perf_counter()
        history = ChatHistory()
        history.add_system_message(_SYSTEM_PROMPT)
        history.add_user_message(
            f"Caption: {caption or 'n/a'}\n"
            f"Matched tags: {', '.join(matched_tags) or 'none'}\n"
            f"Rule-engine severity: {rule_severity or 'none'}"
        )
        settings = OpenAIChatPromptExecutionSettings(response_format=TriageResult)
        try:
            response = await self._service.get_chat_message_content(history, settings, kernel=self._kernel)
            result = TriageResult.model_validate_json(str(response))
        except Exception as exc:
            log_agent_event(logger, "TriageAgent", "error", duration_ms=round((time.perf_counter() - started) * 1000), error=str(exc))
            raise
        log_agent_event(
            logger, "TriageAgent", "result",
            duration_ms=round((time.perf_counter() - started) * 1000),
            escalate=result.escalate, escalated_severity=result.escalated_severity,
            suppress_recommended=result.suppress_recommended,
        )
        return result
