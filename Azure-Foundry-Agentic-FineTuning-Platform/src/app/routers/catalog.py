"""Workflow 1 endpoints — model discovery, leaderboard, and evaluation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.mcp_clients.registry import call_tool
from app.schemas.catalog import METRIC_DIRECTION

router = APIRouter(prefix="/catalog", tags=["workflow1-discovery"])


@router.get("/models")
async def list_models() -> dict[str, Any]:
    return await call_tool("list_models")


@router.get("/models/{name}")
async def get_model_card(name: str) -> dict[str, Any]:
    card = await call_tool("get_model_card", {"name": name})
    if "error" in card:
        raise HTTPException(status_code=404, detail=card["error"])
    return card


@router.get("/benchmarks/{name}")
async def get_benchmarks(name: str) -> dict[str, Any]:
    result = await call_tool("get_benchmarks", {"name": name})
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/leaderboard")
async def get_leaderboard(
    metric: str = Query("quality_index", description="Leaderboard axis to rank by"),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    if metric not in METRIC_DIRECTION:
        raise HTTPException(
            status_code=422,
            detail=f"unknown metric {metric!r}; valid: {list(METRIC_DIRECTION)}",
        )
    return await call_tool("get_leaderboard", {"metric": metric, "limit": limit})


@router.get("/leaderboard/all")
async def get_all_leaderboards(limit: int = Query(10, ge=1, le=50)) -> dict[str, Any]:
    """All four axes at once — the trade-off view needs every metric together."""
    return {
        metric: await call_tool("get_leaderboard", {"metric": metric, "limit": limit})
        for metric in METRIC_DIRECTION
    }


@router.get("/compare")
async def compare_models(model_a: str = "", model_b: str = "") -> dict[str, Any]:
    result = await call_tool("compare_models", {"model_a": model_a, "model_b": model_b})
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/evaluate")
async def create_evaluation(
    deployment: str = "", row_count: int = Query(0, ge=0, le=200)
) -> dict[str, Any]:
    settings = get_settings()
    return await call_tool(
        "create_evaluation",
        {
            "deployment": deployment or settings.model_compare_a,
            "row_count": row_count or settings.eval_row_count,
        },
    )


@router.get("/evaluate/results")
async def evaluation_results() -> dict[str, Any]:
    result = await call_tool("get_evaluation_results")
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.get("/dataset/synthetic")
async def synthetic_dataset(row_count: int = Query(0, ge=0, le=200)) -> dict[str, Any]:
    return await call_tool("generate_synthetic_dataset", {"row_count": row_count})
