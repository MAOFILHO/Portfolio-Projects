"""HTTP surface for the Support Triage Copilot.

A single non-streaming call: triage is a sub-10s decision, so streaming would
add machinery without adding anything a viewer can see. What *is* worth
surfacing is which tools the agent chose to call — that's the visible evidence
that dependency injection is doing something, rather than a claim in a README.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from pydantic_ai.messages import ToolCallPart

from app.shared.cache import DemoCache

from .agents import TOOL_NAMES, triage_agent
from .fixtures import ACCOUNTS, SAMPLE_TICKETS, TICKETS
from .models import Account, ToolCall, TriageDeps, TriageResult

router = APIRouter()

RESULT_CACHE: DemoCache[TriageResult] = DemoCache()


class TriageRequest(BaseModel):
    account_id: str
    ticket: str


class SeedAccount(BaseModel):
    """What the UI needs to populate its account picker."""

    account: Account
    sample_ticket: str


@router.get("/accounts")
async def accounts() -> list[SeedAccount]:
    return [
        SeedAccount(account=account, sample_ticket=SAMPLE_TICKETS.get(account_id, ""))
        for account_id, account in ACCOUNTS.items()
    ]


@router.post("/classify", response_model=TriageResult)
async def classify(request: TriageRequest) -> TriageResult:
    cache_key = f"{request.account_id}|{request.ticket}"
    cached = RESULT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    deps = TriageDeps(account_id=request.account_id, accounts=ACCOUNTS, tickets=TICKETS)
    result = await triage_agent.run(request.ticket, deps=deps)

    # The agent's own reasoning is opaque, but the tools it reached for are not:
    # replaying the message history shows exactly what it looked up before
    # deciding. Filtered against TOOL_NAMES so the generated output tools don't
    # masquerade as lookups the agent chose to make.
    tool_calls = [
        ToolCall(tool_name=part.tool_name, args=part.args_as_dict())
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.tool_name in TOOL_NAMES
    ]

    triage_result = TriageResult(decision=result.output, tool_calls=tool_calls)
    RESULT_CACHE.set(cache_key, triage_result)
    return triage_result
