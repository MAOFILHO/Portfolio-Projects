"""Structured types shared across the pipeline's agents and nodes."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class ResearchDeps:
    """Runtime dependencies injected into every agent run.

    `client_name` lets the system prompt address the caller by name; a real
    deployment would extend this with things like a database session or an
    authenticated HTTP client for the tools to use via `RunContext.deps`.
    """

    client_name: str = "there"


class Finding(BaseModel):
    """One fact a research worker turned up for a sub-topic."""

    sub_topic: str = Field(description="The sub-topic this finding addresses")
    summary: str = Field(description="A concise statement of the finding")
    sources: list[str] = Field(
        default_factory=list, description="URLs or citations backing the finding"
    )


class SubTopicFindings(BaseModel):
    """Output of a single research-worker run."""

    findings: list[Finding]


class SubTopicPlan(BaseModel):
    """Output of the planner/orchestrator agent."""

    sub_topics: list[str] = Field(description="2-4 focused, non-overlapping sub-topics to research")


class ResearchReport(BaseModel):
    """A synthesized report, produced by the synthesizer agent."""

    question: str = Field(description="The original research question")
    summary: str = Field(description="A synthesized answer across all sub-topics")
    key_findings: list[Finding] = Field(
        description="The most important findings, deduplicated and ranked"
    )
    confidence: float = Field(
        ge=0, le=1, description="0-1 confidence in the summary given the findings"
    )
    open_questions: list[str] = Field(
        default_factory=list, description="Gaps the research did not resolve"
    )


class EvaluationResult(BaseModel):
    """Output of the evaluator agent that gates the revision loop."""

    passed: bool = Field(description="Whether the draft report meets the quality bar")
    feedback: str = Field(default="", description="What to fix if the draft did not pass")
