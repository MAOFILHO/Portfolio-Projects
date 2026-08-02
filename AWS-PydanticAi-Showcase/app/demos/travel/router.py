"""HTTP surface for the Travel Itinerary Planner.

`POST /plan` streams over SSE as `Itinerary` is validated in partial mode
straight off the model's token stream — the only demo where a Pydantic model
visibly fills in field-by-field in the browser, rather than arriving whole.
Tool-call progress (the same trail as the other three demos) rides the same
stream via `event_stream_handler`, which pydantic-ai runs concurrently with
the partial-output iteration below rather than in place of it.

`POST /refine` is the multi-turn leg: it re-runs the agent with the prior
`message_history`, so "make it cheaper" is interpreted against the itinerary
already on screen instead of starting over.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic_ai import FunctionToolCallEvent, FunctionToolResultEvent, RunContext
from pydantic_ai.messages import AgentStreamEvent, ModelMessage

from app.shared.cache import DemoCache
from app.shared.sse import drain_progress, sse, sse_response

from .agents import TOOL_LABELS, travel_agent
from .models import Itinerary, PlanRequest, RefineRequest, TravelDeps

router = APIRouter()

# Keyed by session_id; holds the conversation so /refine has something to
# refine. In-memory and single-process, same tradeoff as Research Analyst's
# review store — fine for a demo, not for anything long-lived.
SESSIONS: dict[str, list[ModelMessage]] = {}
PLAN_CACHE: DemoCache[Itinerary] = DemoCache()

# Open-Meteo has no documented rate limit for this volume of demo traffic, but
# a request that never returns shouldn't hang the whole SSE stream.
HTTP_TIMEOUT_SECONDS = 15.0


def _cache_key(request: PlanRequest) -> str:
    return f"{request.destination}|{request.trip_days}|{request.interests}"


async def _stream_itinerary(
    prompt: str,
    *,
    deps: TravelDeps,
    message_history: list[ModelMessage] | None = None,
    on_final: Callable[[Itinerary], Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    session_id = str(uuid.uuid4())
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def handle_events(
        ctx: RunContext[TravelDeps], event_stream: AsyncIterable[AgentStreamEvent]
    ) -> None:
        async for event in event_stream:
            if isinstance(event, FunctionToolCallEvent):
                label = TOOL_LABELS.get(event.part.tool_name)
                if label:
                    await queue.put({"type": "progress", "message": f"Travel agent: {label}"})
            elif isinstance(event, FunctionToolResultEvent):
                label = TOOL_LABELS.get(event.part.tool_name) if event.part.tool_name else None
                if label:
                    await queue.put({"type": "progress", "message": f"{label}: done"})

    async def run() -> Itinerary:
        async with travel_agent.run_stream(
            prompt,
            deps=deps,
            message_history=message_history,
            event_stream_handler=handle_events,
        ) as result:
            async for partial in result.stream_output(debounce_by=0.1):
                await queue.put({"type": "partial", "itinerary": partial.model_dump(mode="json")})
            final = await result.get_output()
            SESSIONS[session_id] = result.all_messages()
        return final

    final: Itinerary | None = None
    async for item in drain_progress(run(), queue):
        if isinstance(item, Itinerary):
            final = item
        else:
            yield sse(item)

    assert final is not None
    if on_final is not None:
        await on_final(final)

    yield sse(
        {"type": "done", "itinerary": final.model_dump(mode="json"), "session_id": session_id}
    )


def _cached_stream(cached: Itinerary) -> AsyncIterator[str]:
    async def event_stream() -> AsyncIterator[str]:
        session_id = str(uuid.uuid4())
        SESSIONS[session_id] = []
        payload = cached.model_dump(mode="json")
        yield sse({"type": "progress", "message": "Using cached itinerary"})
        yield sse({"type": "partial", "itinerary": payload})
        yield sse({"type": "done", "itinerary": payload, "session_id": session_id})

    return event_stream()


@router.post("/plan")
async def plan(request: PlanRequest):
    cached = PLAN_CACHE.get(_cache_key(request))
    if cached is not None:
        return sse_response(_cached_stream(cached))

    prompt = f"Plan a {request.trip_days}-day trip to {request.destination}." + (
        f" Interests: {request.interests}." if request.interests else ""
    )

    async def event_stream() -> AsyncIterator[str]:
        async def cache_it(itinerary: Itinerary) -> None:
            PLAN_CACHE.set(_cache_key(request), itinerary)

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as http_client:
            deps = TravelDeps(http_client=http_client)
            async for event in _stream_itinerary(prompt, deps=deps, on_final=cache_it):
                yield event

    return sse_response(event_stream())


@router.post("/refine")
async def refine(request: RefineRequest):
    history = SESSIONS.get(request.session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    async def event_stream() -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as http_client:
            deps = TravelDeps(http_client=http_client)
            async for event in _stream_itinerary(
                request.instruction, deps=deps, message_history=history
            ):
                yield event

    return sse_response(event_stream())
