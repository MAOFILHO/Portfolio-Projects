"""Support Triage Copilot — the dependency-injection demo."""

from __future__ import annotations

from app.demos.base import Demo

from .router import router

demo = Demo(
    id="triage",
    title="Support Triage Copilot",
    mechanism="Typed DI + union output",
    blurb=(
        "One agent, three tools that read injected customer state, and a discriminated-union "
        "output type — so every outcome carries exactly the fields that outcome needs, and "
        "nothing downstream has to check whether a field happens to be set."
    ),
    router=router,
)

__all__ = ["demo"]
