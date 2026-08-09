"""MCP server: Azure Foundry model catalog, benchmarks, and leaderboard.

Automates §7–§8 of *Explore and compare models*.

Runnable standalone over stdio (`python -m mcp_servers.foundry_catalog.server`),
so any MCP client — Claude Desktop/Code included — can drive Foundry's catalog,
not just this application.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from app.config import get_settings
from app.schemas.catalog import METRIC_DIRECTION, METRIC_LABEL, METRIC_SUBLABEL
from app.services import fixtures

server = MCPServer(
    name="foundry-catalog",
    version="0.1.0",
    instructions=(
        "Explore the Azure AI Foundry model catalog: model cards, public "
        "benchmarks, the four-axis leaderboard, and side-by-side comparison."
    ),
)


@server.tool(description="List every model in the catalog with its version and provider.")
async def list_models() -> dict[str, Any]:
    cards = fixtures.get_model_cards()
    return {
        "count": len(cards),
        "models": [
            {
                "name": c.name,
                "version": c.version,
                "provider": c.provider,
                "lifecycle": c.lifecycle,
                "supports_fine_tuning": c.supports_fine_tuning,
            }
            for c in cards
        ],
    }


@server.tool(description="Get the full model card for one model, including context limits.")
async def get_model_card(name: str) -> dict[str, Any]:
    try:
        return fixtures.get_model_card(name).model_dump()
    except KeyError as exc:
        return {"error": str(exc)}


@server.tool(
    description=(
        "Get the four public benchmark metrics for a model: quality index, "
        "safety attack success rate, throughput, and benchmark cost."
    )
)
async def get_benchmarks(name: str) -> dict[str, Any]:
    try:
        card = fixtures.get_model_card(name)
    except KeyError as exc:
        return {"error": str(exc)}
    if card.benchmarks is None:
        return {"error": f"no benchmarks recorded for {name!r}"}
    return {
        "model": card.name,
        "version": card.version,
        "metrics": [
            {
                "key": key,
                "label": METRIC_LABEL[key],
                "sublabel": METRIC_SUBLABEL[key],
                "value": getattr(card.benchmarks, key),
                "better": METRIC_DIRECTION[key],
            }
            for key in METRIC_DIRECTION
        ],
    }


@server.tool(
    description=(
        "Get the model leaderboard ranked by one metric. Valid metrics: "
        "quality_index, safety_attack_success_rate, throughput_tps, benchmark_cost_usd."
    )
)
async def get_leaderboard(metric: str = "quality_index", limit: int = 10) -> dict[str, Any]:
    if metric not in METRIC_DIRECTION:
        return {
            "error": f"unknown metric {metric!r}",
            "valid_metrics": list(METRIC_DIRECTION),
        }
    board = fixtures.get_leaderboard()
    ranked = board.ranked_by(metric)[:limit]
    return {
        "metric": metric,
        "label": METRIC_LABEL[metric],
        "sublabel": METRIC_SUBLABEL[metric],
        "better": METRIC_DIRECTION[metric],
        "rows": [r.model_dump() for r in ranked],
        "winner": ranked[0].model_name if ranked else None,
    }


@server.tool(
    description=(
        "Compare two models attribute by attribute, marking the winner per row. "
        "Defaults to the two models this project deploys for comparison."
    )
)
async def compare_models(model_a: str = "", model_b: str = "") -> dict[str, Any]:
    settings = get_settings()
    a = model_a or settings.model_compare_a
    b = model_b or settings.model_compare_b

    comparison = fixtures.get_model_comparison()
    if {a, b} == set(comparison.model_names):
        return comparison.model_dump()

    # Not the pre-recorded pair — build the comparison from the model cards.
    try:
        card_a, card_b = fixtures.get_model_card(a), fixtures.get_model_card(b)
    except KeyError as exc:
        return {"error": str(exc)}

    rows: list[dict[str, Any]] = []
    for key in METRIC_DIRECTION:
        if not (card_a.benchmarks and card_b.benchmarks):
            continue
        va, vb = getattr(card_a.benchmarks, key), getattr(card_b.benchmarks, key)
        higher_wins = METRIC_DIRECTION[key] == "higher"
        winner = a if (va > vb) == higher_wins else b
        rows.append(
            {
                "attribute": METRIC_LABEL[key],
                "values": {a: va, b: vb},
                "winner": None if va == vb else winner,
            }
        )
    rows.append(
        {
            "attribute": "Fine-tuning",
            "values": {a: card_a.supports_fine_tuning, b: card_b.supports_fine_tuning},
            "winner": (
                None
                if card_a.supports_fine_tuning == card_b.supports_fine_tuning
                else (a if card_a.supports_fine_tuning else b)
            ),
        }
    )
    return {"model_names": [a, b], "rows": rows}


if __name__ == "__main__":
    server.run(transport="stdio")
