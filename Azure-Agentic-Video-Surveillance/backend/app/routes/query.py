from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from surveil_core.agents import EventQueryAgent

from app.deps import get_query_agent

router = APIRouter(prefix="/api/v1/query", tags=["query"])

# Same rationale as function_app.py's _AGENT_CALL_TIMEOUT_SECONDS: a
# rate-limited Azure OpenAI call can honor a `Retry-After` of thousands of
# seconds, which would otherwise hang this request far past any reasonable
# HTTP timeout.
_AGENT_CALL_TIMEOUT_SECONDS = 20.0


class QueryRequest(BaseModel):
    question: str


@router.post("")
async def query_events_nl(
    body: QueryRequest,
    agent: EventQueryAgent = Depends(get_query_agent),
):
    """Ask a plain-English question about camera event history."""
    try:
        answer = await asyncio.wait_for(agent.answer(body.question), timeout=_AGENT_CALL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="The query agent is temporarily unavailable (timed out) -- try again shortly.")
    return {"answer": answer}
