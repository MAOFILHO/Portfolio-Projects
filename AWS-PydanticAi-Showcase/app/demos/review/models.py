"""Types for the Code Review Assistant."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "minor", "major", "critical"]
Category = Literal["style", "security", "tests"]


@dataclass
class ReviewDeps:
    """The diff under review, injected once and read by every specialist.

    Passing the diff through deps rather than re-pasting it into each sub-agent's
    prompt keeps the delegation tools' arguments to just the focus area — the
    lead reviewer can't accidentally hand a specialist a truncated diff.
    """

    diff: str
    # Optional: lets a delegation tool report a progress-log line as each
    # specialist starts and finishes. None in every test and in any other
    # caller that doesn't want a progress trail.
    progress: Callable[[str], Awaitable[None]] | None = None


class ReviewComment(BaseModel):
    file: str = Field(description="Path of the file the comment applies to")
    line: int = Field(description="Line number in the new version of the file, or 0 if unknown")
    severity: Severity
    category: Category
    message: str


class SpecialistFindings(BaseModel):
    """What one specialist sub-agent returns to the lead reviewer."""

    comments: list[ReviewComment] = Field(default_factory=list)
    summary: str = Field(description="One sentence on what this specialist looked for and found")


class ReviewVerdict(BaseModel):
    """The lead reviewer's consolidated call."""

    verdict: Literal["approve", "comment", "request_changes"]
    summary: str = Field(
        description="What a human reviewer needs to know in two or three sentences"
    )
    comments: list[ReviewComment] = Field(default_factory=list)


class UsageReport(BaseModel):
    """What the delegated run actually cost, surfaced so the guardrail is visible."""

    requests: int
    input_tokens: int
    output_tokens: int
    request_limit: int


class ReviewResponse(BaseModel):
    verdict: ReviewVerdict
    usage: UsageReport
