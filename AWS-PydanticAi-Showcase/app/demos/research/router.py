"""HTTP surface for the Research Analyst demo.

`POST /research` streams live progress (Server-Sent Events) while the
deterministic multi-agent pipeline (plan -> parallel fan-out -> synthesize ->
evaluate/revise) runs — a real run takes 1-2 minutes, and each event is both
a UI update *and* a keep-alive that resets the ALB's idle timeout, so the
long-running call no longer risks a gateway timeout on a slow connection.
The stream ends with a `done` event carrying the draft `ResearchReport`
pending compliance review. `POST /reviews/{id}/decision` is the
human-in-the-loop step: a compliance officer approves the draft as-is, or
annotates it with notes that get folded into the final report.

Reviews are kept in an in-memory store — fine for a demo/single-process
deployment; swap `_REVIEWS` for a real datastore for anything long-lived.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.shared.cache import DemoCache
from app.shared.sse import drain_progress, sse, sse_response

from .agents import synthesizer_agent
from .models import ResearchDeps, ResearchReport
from .pipeline import PipelineState, research_pipeline

router = APIRouter()


class ReviewRecord(BaseModel):
    review_id: str
    question: str
    status: Literal["pending_review", "final"]
    draft: ResearchReport
    final: ResearchReport | None = None
    officer_notes: str | None = None


REVIEWS: dict[str, ReviewRecord] = {}
REVIEW_DEPS: dict[str, ResearchDeps] = {}
REPORT_CACHE: DemoCache[ResearchReport] = DemoCache()


class AskRequest(BaseModel):
    question: str
    client_name: str = "there"


class DecisionRequest(BaseModel):
    decision: Literal["approve", "annotate"]
    notes: str | None = None


@router.post("/research")
async def research(request: AskRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        deps = ResearchDeps(client_name=request.client_name)

        cached = REPORT_CACHE.get(request.question)
        if cached is not None:
            yield sse({"type": "progress", "message": "Using cached report"})
            draft = cached
        else:
            queue: asyncio.Queue[str] = asyncio.Queue()

            async def report_progress(message: str) -> None:
                await queue.put(message)

            state = PipelineState(question=request.question, deps=deps, progress=report_progress)

            draft = None
            try:
                async for item in drain_progress(research_pipeline.run(state=state), queue):
                    if isinstance(item, str):
                        yield sse({"type": "progress", "message": item})
                    else:
                        draft = item
            except Exception as e:  # noqa: BLE001 - surface any agent/pipeline failure to the client
                yield sse({"type": "error", "message": str(e)})
                return

            assert draft is not None
            REPORT_CACHE.set(request.question, draft)

        review_id = str(uuid.uuid4())
        record = ReviewRecord(
            review_id=review_id,
            question=request.question,
            status="pending_review",
            draft=draft,
        )
        REVIEWS[review_id] = record
        REVIEW_DEPS[review_id] = deps
        yield sse({"type": "done", "record": record.model_dump(mode="json")})

    return sse_response(event_stream())


@router.get("/reviews/{review_id}", response_model=ReviewRecord)
async def get_review(review_id: str) -> ReviewRecord:
    record = REVIEWS.get(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return record


@router.post("/reviews/{review_id}/decision", response_model=ReviewRecord)
async def decide_review(review_id: str, request: DecisionRequest) -> ReviewRecord:
    record = REVIEWS.get(review_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if record.status == "final":
        raise HTTPException(status_code=409, detail="Review already finalized")

    if request.decision == "approve":
        record.final = record.draft
        record.status = "final"
        return record

    if not request.notes:
        raise HTTPException(status_code=400, detail="notes are required to annotate")
    prompt = (
        f"Question: {record.question}\n\n"
        f"Draft report:\n{record.draft.model_dump_json()}\n\n"
        f"A human compliance officer annotated this draft with the following notes; "
        "incorporate them into a final report:\n"
        f"{request.notes}"
    )
    result = await synthesizer_agent.run(prompt, deps=REVIEW_DEPS[review_id])
    record.final = result.output
    record.status = "final"
    record.officer_notes = request.notes
    return record
