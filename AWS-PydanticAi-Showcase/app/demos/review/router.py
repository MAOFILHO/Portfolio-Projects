"""HTTP surface for the Code Review Assistant.

`POST /analyze` streams over SSE — the same progress-trail UX as the other
three demos, built by giving `ReviewDeps` a `progress` callback that the
delegation tools call as each specialist starts and finishes (see
`agents.py`), drained alongside the lead reviewer's `.run()` with
`drain_progress`. Because the three specialists run as parallel tool calls,
their start/finish lines land at genuinely different times, so the log
doubles as a real trace of which specialist was the long pole.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_ai import UsageLimitExceeded, UsageLimits

from app.shared.cache import DemoCache
from app.shared.sse import drain_progress, sse, sse_response

from .agents import REQUEST_LIMIT, lead_reviewer_agent
from .fixtures import SAMPLE_DIFF
from .models import ReviewDeps, ReviewResponse, UsageReport

router = APIRouter()

RESPONSE_CACHE: DemoCache[ReviewResponse] = DemoCache()

# A whole diff of pasted text is cheap to hold but not unbounded; anything larger
# than this is past what the model can review usefully in one pass anyway.
MAX_DIFF_CHARS = 20_000


class ReviewRequest(BaseModel):
    diff: str


@router.get("/sample-diff")
async def sample_diff() -> dict[str, str]:
    return {"diff": SAMPLE_DIFF}


@router.post("/analyze")
async def analyze(request: ReviewRequest) -> StreamingResponse:
    diff = request.diff.strip()
    if not diff:
        raise HTTPException(status_code=400, detail="Paste a diff to review")
    if len(diff) > MAX_DIFF_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Diff is {len(diff):,} characters; this demo reviews up to {MAX_DIFF_CHARS:,}",
        )

    async def event_stream() -> AsyncIterator[str]:
        cached = RESPONSE_CACHE.get(diff)
        if cached is not None:
            yield sse({"type": "progress", "message": "Using cached result"})
            yield sse({"type": "done", "response": cached.model_dump(mode="json")})
            return

        queue: asyncio.Queue[str] = asyncio.Queue()

        async def report_progress(message: str) -> None:
            await queue.put(message)

        deps = ReviewDeps(diff=diff, progress=report_progress)
        run_result = None
        try:
            async for item in drain_progress(
                lead_reviewer_agent.run(
                    "Review the diff in your dependencies and give a consolidated verdict.",
                    deps=deps,
                    usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
                ),
                queue,
            ):
                if isinstance(item, str):
                    yield sse({"type": "progress", "message": item})
                else:
                    run_result = item
        except UsageLimitExceeded as e:
            # The guardrail firing is a real outcome, not a server fault: the
            # review ran away, we stopped paying for it, and the caller deserves
            # to be told that in as many words rather than getting a silent cutoff.
            yield sse(
                {
                    "type": "error",
                    "message": (
                        f"Review stopped at the {REQUEST_LIMIT}-request budget before reaching "
                        f"a verdict ({e}). Try a smaller diff."
                    ),
                }
            )
            return
        except Exception as e:  # noqa: BLE001 - surface any agent failure to the client
            yield sse({"type": "error", "message": str(e)})
            return

        assert run_result is not None
        yield sse({"type": "progress", "message": "Lead reviewer: consolidating verdict"})

        usage = run_result.usage
        response = ReviewResponse(
            verdict=run_result.output,
            usage=UsageReport(
                requests=usage.requests,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                request_limit=REQUEST_LIMIT,
            ),
        )
        RESPONSE_CACHE.set(diff, response)
        yield sse({"type": "done", "response": response.model_dump(mode="json")})

    return sse_response(event_stream())
