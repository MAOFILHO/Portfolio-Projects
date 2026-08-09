"""Shared state for the LangGraph agent graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

Demo = Literal["discovery", "finetune", "comparison"]


class AgentState(TypedDict, total=False):
    """State threaded through the orchestrator and its sub-agents.

    `trace` accumulates across nodes (hence the `operator.add` reducer) so the UI
    can show which agent did what, and which MCP tools it called.
    """

    request: str
    demo: Demo | None
    route_reason: str
    result: dict[str, Any]
    trace: Annotated[list[str], operator.add]
    error: str | None


def new_state(request: str, demo: Demo | None = None) -> AgentState:
    return AgentState(request=request, demo=demo, trace=[], result={}, error=None)
