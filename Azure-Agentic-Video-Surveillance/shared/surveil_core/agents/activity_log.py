"""Structured agent-activity logging, consumed by the "AI Agents Activity"
dashboard page (`GET /api/v1/agents/activity`).

Every line is tagged with the `[AGENT]` prefix so it can be pulled out of
Application Insights (the same Log Analytics workspace already used by the
Observability page) with a simple `Message startswith "[AGENT]"` filter --
no new telemetry pipeline, no new external service.
"""

from __future__ import annotations

import logging

_TAG = "[AGENT]"


def log_agent_event(logger: logging.Logger, agent: str, phase: str, **fields: object) -> None:
    detail = " ".join(f"{key}={value!r}" for key, value in fields.items())
    logger.info("%s %s | %s | %s", _TAG, agent, phase, detail)
