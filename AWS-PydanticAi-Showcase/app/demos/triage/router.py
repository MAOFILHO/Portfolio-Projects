"""HTTP surface for the Support Triage Copilot.

`POST /classify` streams over SSE: the same "each line is a real model/tool
call" progress trail as the other three demos, built by giving `TriageDeps` a
`progress` callback that the tools call as they run (see `agents.py`) and
draining it alongside the agent's `.run()` with `drain_progress` — the same
mechanism Research Analyst uses for its own pipeline.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_ai.messages import ToolCallPart

from app.shared.cache import DemoCache
from app.shared.sse import drain_progress, sse, sse_response

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


@router.post("/classify")
async def classify(request: TriageRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        cache_key = f"{request.account_id}|{request.ticket}"
        cached = RESULT_CACHE.get(cache_key)
        if cached is not None:
            yield sse({"type": "progress", "message": "Using cached result"})
            yield sse({"type": "done", "result": cached.model_dump(mode="json")})
            return

        queue: asyncio.Queue[str] = asyncio.Queue()

        async def report_progress(message: str) -> None:
            await queue.put(message)

        deps = TriageDeps(
            account_id=request.account_id,
            accounts=ACCOUNTS,
            tickets=TICKETS,
            progress=report_progress,
        )

        try:
            result = None
            async for item in drain_progress(triage_agent.run(request.ticket, deps=deps), queue):
                if isinstance(item, str):
                    yield sse({"type": "progress", "message": item})
                else:
                    result = item
        except Exception as e:  # noqa: BLE001 - surface any agent failure to the client
            yield sse({"type": "error", "message": str(e)})
            return

        assert result is not None
        # The agent's own reasoning is opaque, but the tools it reached for are
        # not: replaying the message history shows exactly what it looked up
        # before deciding. Filtered against TOOL_NAMES so the generated output
        # tools don't masquerade as lookups the agent chose to make.
        tool_calls = [
            ToolCall(tool_name=part.tool_name, args=part.args_as_dict())
            for message in result.all_messages()
            for part in message.parts
            if isinstance(part, ToolCallPart) and part.tool_name in TOOL_NAMES
        ]

        yield sse({"type": "progress", "message": "Triage agent: finalizing decision"})
        triage_result = TriageResult(decision=result.output, tool_calls=tool_calls)
        RESULT_CACHE.set(cache_key, triage_result)
        yield sse({"type": "done", "result": triage_result.model_dump(mode="json")})

    return sse_response(event_stream())
