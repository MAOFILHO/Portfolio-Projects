"""Discovery sub-agent — Demo 1.

Owns model catalog exploration, leaderboard comparison, and synthetic-dataset
evaluation (guide §7–§11). Talks to Foundry only through MCP tools.
"""

from __future__ import annotations

from typing import Any

from app import jobs
from app.agents.state import AgentState
from app.config import get_settings
from app.mcp_clients.registry import call_tool
from app.schemas.catalog import METRIC_DIRECTION
from app.telemetry import span


async def run_discovery(state: AgentState) -> dict[str, Any]:
    """Browse the catalog, rank the leaderboard, compare, then evaluate."""
    settings = get_settings()
    trace: list[str] = []

    with span("agent.discovery", demo="discovery", mode=settings.demo_mode):
        jobs.report("starting: model catalog")
        with span("mcp.list_models"):
            catalog = await call_tool("list_models")
            trace.append(f"list_models → {catalog['count']} models")

        # Rank on every leaderboard axis; the interesting result is that no single
        # model wins all four, which is the whole point of the trade-off view.
        leaderboards: dict[str, Any] = {}
        for metric in METRIC_DIRECTION:
            with span("mcp.get_leaderboard", metric=metric):
                board = await call_tool("get_leaderboard", {"metric": metric, "limit": 5})
            leaderboards[metric] = board
            trace.append(f"get_leaderboard[{metric}] → winner {board['winner']}")

        with span("mcp.compare_models"):
            comparison = await call_tool(
                "compare_models",
                {"model_a": settings.model_compare_a, "model_b": settings.model_compare_b},
            )
            trace.append(
                f"compare_models → {settings.model_compare_a} vs {settings.model_compare_b}"
            )

        jobs.report(
            f"starting evaluation: {settings.eval_row_count} rows — "
            "this is the long part, see below for row/evaluator progress"
        )
        with span("mcp.create_evaluation", rows=settings.eval_row_count):
            evaluation = await call_tool(
                "create_evaluation",
                {
                    "deployment": settings.model_compare_a,
                    "row_count": settings.eval_row_count,
                },
            )
        with span("mcp.get_evaluation_results"):
            results = await call_tool("get_evaluation_results")
            trace.append(f"evaluation → {results['overall_score']}")

    return {
        "result": {
            "demo": "discovery",
            "catalog": catalog,
            "leaderboards": leaderboards,
            "comparison": comparison,
            "evaluation": results,
            "evaluation_raw": evaluation,
        },
        "trace": trace,
    }
