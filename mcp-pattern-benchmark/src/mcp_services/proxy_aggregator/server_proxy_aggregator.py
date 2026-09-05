"""Pattern server for the Proxy Aggregator module.

Fronts three upstream namespaces (repos, runbooks, deploys) behind a static
MCP surface of exactly two tools, per ADR 0006-scoped-discovery-in-the-server:
`discover_tools(service)` returns one service's operations, `call_tool`
dispatches to one of them. No per-namespace tool is ever separately listed,
so the surface stays at two tools no matter how many services get fronted.
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("proxy-aggregator")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))

async def _runbooks_list(args: dict) -> list[dict]:
    response = await client.get("/runbooks", params={"repo_id": args["repo_id"]})
    response.raise_for_status()
    return response.json()


async def _runbooks_get(args: dict) -> dict:
    response = await client.get(f"/runbooks/{args['runbook_id']}")
    response.raise_for_status()
    return response.json()


async def _deploys_create(args: dict) -> dict:
    response = await client.post(
        "/deploys", json={"repo_id": args["repo_id"], "environment": args["environment"]}
    )
    response.raise_for_status()
    return response.json()


async def _deploys_get(args: dict) -> dict:
    response = await client.get(f"/deploys/{args['deploy_id']}")
    response.raise_for_status()
    return response.json()


async def _deploys_update_status(args: dict) -> dict:
    response = await client.patch(f"/deploys/{args['deploy_id']}", json={"status": args["status"]})
    response.raise_for_status()
    return response.json()


async def _repos_get_change_request(args: dict) -> dict:
    response = await client.get(f"/change-requests/{args['change_request_id']}")
    response.raise_for_status()
    return response.json()


_OPERATIONS = {
    "runbooks": {
        "list": {
            "description": "List runbooks for a repo.",
            "parameters": ["repo_id"],
            "handler": _runbooks_list,
        },
        "get": {
            "description": "Get one runbook by id.",
            "parameters": ["runbook_id"],
            "handler": _runbooks_get,
        },
    },
    "repos": {
        "get_change_request": {
            "description": "Get one change request by id.",
            "parameters": ["change_request_id"],
            "handler": _repos_get_change_request,
        },
    },
    "deploys": {
        "create": {
            "description": "Create a pending deploy.",
            "parameters": ["repo_id", "environment"],
            "handler": _deploys_create,
        },
        "get": {
            "description": "Get one deploy by id.",
            "parameters": ["deploy_id"],
            "handler": _deploys_get,
        },
        "update_status": {
            "description": "Update a deploy's status.",
            "parameters": ["deploy_id", "status"],
            "handler": _deploys_update_status,
        },
    },
}


@mcp.tool()
async def discover_tools(service: str | None = None) -> list[dict] | list[str]:
    """With no service, list the available services. With a service name,
    list that service's operations."""
    if service is None:
        return list(_OPERATIONS.keys())
    if service not in _OPERATIONS:
        raise ValueError(
            f"Unknown service '{service}'. Valid services: {sorted(_OPERATIONS)}"
        )
    return [
        {"name": name, "description": spec["description"], "parameters": spec["parameters"]}
        for name, spec in _OPERATIONS[service].items()
    ]


@mcp.tool()
async def call_tool(service: str, tool: str, args: dict) -> dict[str, Any]:
    """Dispatch to one operation. Always returns {"result": <payload>} since
    the payload shape (object or list) varies per operation but the tool
    itself declares one static output schema."""
    if service not in _OPERATIONS:
        raise ValueError(
            f"Unknown service '{service}'. Valid services: {sorted(_OPERATIONS)}"
        )
    if tool not in _OPERATIONS[service]:
        raise ValueError(
            f"Unknown tool '{tool}' for service '{service}'. "
            f"Valid tools: {sorted(_OPERATIONS[service])}"
        )
    result = await _OPERATIONS[service][tool]["handler"](args)
    return {"result": result}


if __name__ == "__main__":
    mcp.run()
