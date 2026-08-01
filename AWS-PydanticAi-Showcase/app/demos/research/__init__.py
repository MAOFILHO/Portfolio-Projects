"""Research Analyst — the `pydantic_graph` orchestration demo."""

from __future__ import annotations

from app.demos.base import Demo

from .router import router

demo = Demo(
    id="research",
    title="Research Analyst",
    mechanism="pydantic_graph pipeline",
    blurb=(
        "An orchestrator plans sub-topics, specialist workers research each one in parallel, "
        "a synthesizer drafts the report, an evaluator gates a revision loop, and a human "
        "compliance officer signs off before it's final."
    ),
    router=router,
)

__all__ = ["demo"]
