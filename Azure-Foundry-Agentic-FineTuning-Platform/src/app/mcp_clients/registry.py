"""In-process MCP tool registry.

The three servers are real MCP servers and run standalone over stdio. Inside
this application we invoke them in-process via `MCPServer.call_tool` instead of
spawning subprocesses: same tool schemas, same handlers, no IPC overhead, and
tests stay fast and deterministic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mcp.server import MCPServer

from mcp_servers.foundry_catalog.server import server as catalog_server
from mcp_servers.foundry_finetune.server import server as finetune_server
from mcp_servers.foundry_inference.server import server as inference_server

SERVERS: dict[str, MCPServer] = {
    "catalog": catalog_server,
    "finetune": finetune_server,
    "inference": inference_server,
}


@dataclass(frozen=True)
class ToolInfo:
    server: str
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolNotFoundError(KeyError):
    """Raised when a tool name matches no registered server."""


async def list_tools(server: str | None = None) -> list[ToolInfo]:
    """Every tool across the registry, or just one server's."""
    targets = {server: SERVERS[server]} if server else SERVERS
    infos: list[ToolInfo] = []
    for server_name, instance in targets.items():
        for tool in await instance.list_tools():
            infos.append(
                ToolInfo(
                    server=server_name,
                    name=tool.name,
                    description=tool.description or "",
                    # MCP 2.0 renamed this from `inputSchema` to snake_case.
                    input_schema=tool.input_schema or {},
                )
            )
    return infos


async def _resolve(tool_name: str) -> MCPServer:
    for instance in SERVERS.values():
        if any(t.name == tool_name for t in await instance.list_tools()):
            return instance
    available = sorted(t.name for t in await list_tools())
    raise ToolNotFoundError(f"no MCP tool named {tool_name!r}. Available: {available}")


def _unwrap(result: Any) -> Any:
    """Turn a CallToolResult into plain Python.

    Prefers `structured_content` when the server populated it, and otherwise
    parses the first text block as JSON.
    """
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return None


async def call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Invoke an MCP tool by name and return its decoded payload."""
    instance = await _resolve(tool_name)
    result = await instance.call_tool(tool_name, arguments or {})
    payload = _unwrap(result)
    if getattr(result, "is_error", False):
        detail = payload if isinstance(payload, str) else json.dumps(payload)
        raise RuntimeError(f"MCP tool {tool_name!r} failed: {detail}")
    return payload
