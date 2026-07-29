from __future__ import annotations

# Must be the first import in this package: it sets the env vars that gate
# Semantic Kernel's own OTel instrumentation as a module-level side effect,
# and Semantic Kernel reads them exactly once, at ITS OWN import time, into a
# frozen settings singleton. Every other import below transitively imports
# semantic_kernel -- if any of them ran first, the env vars would already be
# too late to matter. See tracing.py's module docstring for the full story.
from .tracing import agent_span, flush_langfuse_tracing, set_agent_output

from .diagnostic_agent import WebrtcDiagnosticAgent
from .kernel_factory import build_kernel, get_chat_service
from .models import MonitoringReport, NotificationDecision, TriageResult
from .monitoring_agent import MonitoringAgent
from .notification_policy_agent import NotificationPolicyAgent
from .query_agent import EventQueryAgent, EventQueryPlugin
from .triage_agent import TriageAgent

__all__ = [
    "build_kernel",
    "get_chat_service",
    "TriageResult",
    "NotificationDecision",
    "MonitoringReport",
    "TriageAgent",
    "NotificationPolicyAgent",
    "EventQueryAgent",
    "EventQueryPlugin",
    "WebrtcDiagnosticAgent",
    "MonitoringAgent",
    "flush_langfuse_tracing",
    "agent_span",
    "set_agent_output",
]
