"""HTTP surface for the Code Review Assistant."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pydantic_ai import UsageLimitExceeded, UsageLimits

from app.shared.cache import DemoCache

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


@router.post("/analyze", response_model=ReviewResponse)
async def analyze(request: ReviewRequest) -> ReviewResponse:
    diff = request.diff.strip()
    if not diff:
        raise HTTPException(status_code=400, detail="Paste a diff to review")
    if len(diff) > MAX_DIFF_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Diff is {len(diff):,} characters; this demo reviews up to {MAX_DIFF_CHARS:,}",
        )

    cached = RESPONSE_CACHE.get(diff)
    if cached is not None:
        return cached

    try:
        result = await lead_reviewer_agent.run(
            "Review the diff in your dependencies and give a consolidated verdict.",
            deps=ReviewDeps(diff=diff),
            usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
        )
    except UsageLimitExceeded as e:
        # The guardrail firing is a real outcome, not a server fault: the review
        # ran away, we stopped paying for it, and the caller deserves to be told
        # that in as many words rather than getting an opaque 500.
        raise HTTPException(
            status_code=422,
            detail=(
                f"Review stopped at the {REQUEST_LIMIT}-request budget before reaching a "
                f"verdict ({e}). Try a smaller diff."
            ),
        ) from e

    usage = result.usage
    response = ReviewResponse(
        verdict=result.output,
        usage=UsageReport(
            requests=usage.requests,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            request_limit=REQUEST_LIMIT,
        ),
    )
    RESPONSE_CACHE.set(diff, response)
    return response
