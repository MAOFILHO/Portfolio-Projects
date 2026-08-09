"""Health and metadata endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.mcp_clients.registry import list_tools

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "demo_mode": settings.demo_mode,
        "region": settings.azure_location,
        "billing": "none — mock mode" if settings.is_mock else "LIVE — tokens are billed",
    }


@router.get("/mcp/tools")
async def mcp_tools() -> dict[str, Any]:
    """Every MCP tool the agents can call, grouped by server."""
    tools = await list_tools()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for tool in tools:
        grouped.setdefault(tool.server, []).append(
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": sorted(tool.input_schema.get("properties", {})),
            }
        )
    return {"count": len(tools), "servers": grouped}
