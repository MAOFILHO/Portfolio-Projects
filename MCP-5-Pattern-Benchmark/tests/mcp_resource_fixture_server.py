"""Minimal MCP server exposing one resource, used only to test
MCPStdioServer's resource support in isolation from this project's real
backend and pattern servers.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("resource-fixture")


@mcp.resource("fixture://hello")
def hello() -> str:
    return "hello from fixture resource"


@mcp.resource("fixture://{item_id}")
def item(item_id: str) -> str:
    return f"fixture item {item_id}"


if __name__ == "__main__":
    mcp.run()
