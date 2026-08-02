"""Types for the Support Triage Copilot.

The interesting one is `TriageDecision`: a *discriminated union*, not a string
enum with a pile of optional fields. Each outcome carries exactly the data that
outcome needs — an escalation has a team and a severity, a resolution has a
draft reply, a request for information has questions — and the model is forced
to produce a shape that's already valid for whatever the caller does next. On
the Python side that means `match` on the union member with no `if decision.team
is not None` defensive checks anywhere.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
Plan = Literal["free", "business", "enterprise"]


class Account(BaseModel):
    """The customer record a support agent would have open beside the ticket."""

    account_id: str
    company: str
    plan: Plan
    seats: int
    monthly_spend_usd: int
    support_sla_hours: int
    open_incidents: int = 0


class PastTicket(BaseModel):
    ticket_id: str
    subject: str
    resolved: bool
    days_ago: int


@dataclass
class TriageDeps:
    """Injected per request; the tools read the customer's world from here.

    In production `accounts` and `tickets` would be a database session or an
    authenticated CRM client. The agent's tools don't care which — they only
    ever touch `RunContext.deps`, which is exactly what makes them testable
    without a network or a fixture-shaped monkeypatch.
    """

    account_id: str
    accounts: dict[str, Account] = field(default_factory=dict)
    tickets: dict[str, list[PastTicket]] = field(default_factory=dict)
    # Optional: lets a tool report a progress-log line as it runs, without the
    # agent or its tools knowing anything about SSE. None in every test and in
    # any other caller that doesn't want a progress trail.
    progress: Callable[[str], Awaitable[None]] | None = None


class Resolve(BaseModel):
    """The agent is confident enough to answer the customer directly."""

    action: Literal["resolve"] = "resolve"
    draft_reply: str = Field(description="A complete reply, ready for a human to send")
    confidence: float = Field(ge=0, le=1)


class Escalate(BaseModel):
    """The ticket needs a specialist team."""

    action: Literal["escalate"] = "escalate"
    team: Literal["billing", "security", "infrastructure", "account-management"]
    severity: Severity
    reason: str = Field(description="Why this can't be handled by front-line support")


class NeedsInfo(BaseModel):
    """The ticket can't be actioned until the customer answers something."""

    action: Literal["needs_info"] = "needs_info"
    questions: list[str] = Field(description="Specific questions to send back to the customer")


# The union travels in two directions, and each leg wants a different spelling.
#
# Going *out* to the model, `agents.py` passes the members as a sequence. Pydantic
# AI generates one output tool per member (`final_result_Resolve`,
# `final_result_Escalate`, ...), so the model commits to a branch by choosing a
# tool — the `action` field is redundant on that leg.
#
# Coming *back*, this app serializes the decision to JSON and FastAPI parses it
# again. That's where the discriminator earns its keep: without it Pydantic tries
# each member in turn and can pick the wrong one when shapes overlap; with it the
# `action` field decides outright, and validation errors name the real branch.
TriageDecision = Annotated[Resolve | Escalate | NeedsInfo, Field(discriminator="action")]


class ToolCall(BaseModel):
    """One tool the agent chose to call, surfaced so the UI can show its work."""

    tool_name: str
    args: dict[str, object] = Field(default_factory=dict)


class TriageResult(BaseModel):
    decision: TriageDecision
    tool_calls: list[ToolCall] = Field(default_factory=list)
