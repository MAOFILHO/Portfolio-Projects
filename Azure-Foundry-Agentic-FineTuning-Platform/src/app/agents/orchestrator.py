"""LangGraph orchestrator.

A supervisor node classifies the request and routes it to exactly one of three
sub-agents, each of which owns one demo and reaches Foundry only through MCP
tools.

    supervisor ──┬─→ discovery  ──┐
                 ├─→ finetune   ──┼─→ END
                 └─→ comparison ──┘

Routing is keyword-based rather than LLM-based on purpose: it must be
deterministic, free, and work in mock mode with no model deployed. Swapping in
an LLM classifier means replacing `classify()` alone.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.comparison_agent import run_comparison
from app.agents.discovery_agent import run_discovery
from app.agents.finetune_agent import run_finetune
from app.agents.state import AgentState, Demo, new_state
from app.telemetry import span

_KEYWORDS: dict[Demo, tuple[str, ...]] = {
    "discovery": (
        "catalog",
        "leaderboard",
        "benchmark",
        "evaluate",
        "evaluation",
        "compare models",
        "quality",
        "throughput",
        "safety",
        "discover",
        "explore",
        "synthetic",
        "demo1",
        "demo 1",
    ),
    "finetune": (
        "fine-tune",
        "finetune",
        "fine tune",
        "sft",
        "training",
        "train",
        "jsonl",
        "dataset",
        "job",
        "epoch",
        "checkpoint",
        "demo2",
        "demo 2",
    ),
    "comparison": (
        "baseline",
        "side-by-side",
        "side by side",
        "versus",
        "vs",
        "tone",
        "behaviour",
        "behavior",
        "inference",
        "chat",
        "prompt",
        "demo3",
        "demo 3",
    ),
}


def classify(request: str) -> tuple[Demo, str]:
    """Pick a sub-agent, returning the choice and a human-readable reason."""
    text = (request or "").lower()
    scores: dict[Demo, int] = {
        demo: sum(1 for kw in words if kw in text) for demo, words in _KEYWORDS.items()
    }
    best = max(scores, key=lambda d: scores[d])
    if scores[best] == 0:
        return "discovery", "no keyword matched; defaulting to model discovery"
    matched = [kw for kw in _KEYWORDS[best] if kw in text]
    return best, f"matched {', '.join(matched[:3])}"


async def supervisor(state: AgentState) -> dict[str, Any]:
    """Route the request. An explicit `demo` always wins over classification."""
    explicit = state.get("demo")
    if explicit:
        return {
            "demo": explicit,
            "route_reason": "demo selected explicitly",
            "trace": [f"supervisor → {explicit} (explicit)"],
        }
    demo, reason = classify(state.get("request", ""))
    with span("agent.supervisor", demo=demo, reason=reason):
        pass
    return {
        "demo": demo,
        "route_reason": reason,
        "trace": [f"supervisor → {demo} ({reason})"],
    }


def _route(state: AgentState) -> str:
    return state.get("demo") or "discovery"


@lru_cache
def build_graph() -> Any:
    """Compile the orchestrator graph once."""
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor)
    graph.add_node("discovery", run_discovery)
    graph.add_node("finetune", run_finetune)
    graph.add_node("comparison", run_comparison)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route,
        {"discovery": "discovery", "finetune": "finetune", "comparison": "comparison"},
    )
    for node in ("discovery", "finetune", "comparison"):
        graph.add_edge(node, END)

    return graph.compile()


async def invoke(request: str, demo: Demo | None = None) -> AgentState:
    """Run the orchestrator end to end for one request."""
    graph = build_graph()
    with span("orchestrator.invoke", request=request[:120], demo=demo or "auto"):
        return await graph.ainvoke(new_state(request, demo))
