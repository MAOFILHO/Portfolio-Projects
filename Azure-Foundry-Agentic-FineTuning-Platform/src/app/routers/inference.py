"""Workflow 3 endpoints — inference and baseline-vs-fine-tuned comparison."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import CANONICAL_TRAVEL_PROMPTS, TRAVEL_SYSTEM_PROMPT
from app.mcp_clients.registry import call_tool

router = APIRouter(prefix="/inference", tags=["workflow3-comparison"])


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    deployment: str = ""
    system_prompt: str = ""
    fine_tuned: bool = False


class CompareRequest(BaseModel):
    prompts: list[str] | None = Field(
        default=None, description="Omit to use the five canonical lab prompts"
    )
    baseline_deployment: str = ""
    fine_tuned_deployment: str = ""


@router.get("/prompts")
async def canonical_prompts() -> dict[str, Any]:
    """The five prompts the guides use for the baseline/fine-tuned comparison."""
    return {
        "system_prompt": TRAVEL_SYSTEM_PROMPT,
        "prompts": list(CANONICAL_TRAVEL_PROMPTS),
        "note": (
            "This system prompt is identical to the one on every row of the "
            "training file, which is what makes the comparison fair."
        ),
    }


@router.post("/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    return await call_tool("chat_completion", request.model_dump())


@router.post("/compare")
async def compare(request: CompareRequest) -> dict[str, Any]:
    return await call_tool("compare_completions", request.model_dump())
