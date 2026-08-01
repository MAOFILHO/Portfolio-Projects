"""Code Review Assistant — the agent-delegation demo."""

from __future__ import annotations

from app.demos.base import Demo

from .router import router

demo = Demo(
    id="review",
    title="Code Review Assistant",
    mechanism="Agent delegation + usage limits",
    blurb=(
        "A lead reviewer consults style, security, and test specialists as tools, deciding "
        "for itself which to consult — the same fan-out as Research Analyst, but driven by the "
        "model instead of a graph, and capped by a shared request budget."
    ),
    router=router,
)

__all__ = ["demo"]
