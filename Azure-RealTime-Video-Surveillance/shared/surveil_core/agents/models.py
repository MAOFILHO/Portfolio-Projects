"""Structured output contracts for the Semantic Kernel agents.

Every agent call returns one of these models -- via Azure OpenAI structured
output (`response_format=<Model>`), never free-text parsed with regex. Kept
alongside `alert_rules.py`'s `SEVERITY_ORDER` vocabulary so severity values
agents produce are always comparable against the deterministic rule engine's
own severities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriageResult(BaseModel):
    """Output of `TriageAgent.triage(...)`.

    Escalation is the only mutation this result may cause in the caller: an
    `escalated_severity` may only be applied if it is strictly higher (per
    `alert_rules.SEVERITY_ORDER`) than the rule engine's own severity, and
    only when that severity isn't already "critical" -- see the guardrail in
    `function_app.py`. Suppression is advisory-only in v1: `suppress_recommended`
    is logged, never auto-applied, regardless of severity.
    """

    escalate: bool = False
    escalated_severity: str | None = None
    reasoning: str = ""
    suppress_recommended: bool = False
    suppress_reason: str | None = None


class NotificationDecision(BaseModel):
    """Output of `NotificationPolicyAgent.decide(...)`.

    Only selects delivery channels/framing -- it cannot affect `is_alert` or
    `severity`, which are read-only inputs to this agent.
    """

    channels: list[str] = Field(default_factory=lambda: ["email", "sms"])
    reasoning: str = ""
    urgency_note: str | None = None


class MonitoringReport(BaseModel):
    """Output of `MonitoringAgent.analyze(...)`.

    Advisory-only in v1: flags anomalies for a human to read on the
    Observability page, does not page/notify anyone.
    """

    flags: list[str] = Field(default_factory=list)
    severity: str = "low"
    summary: str = ""
