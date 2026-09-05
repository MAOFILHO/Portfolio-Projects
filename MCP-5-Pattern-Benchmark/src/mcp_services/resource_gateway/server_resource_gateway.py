"""Pattern server for the Resource Gateway module.

Exposes each runbook as a native MCP resource at `runbook://{id}`, containing
only the sanitized `body` -- `internal_notes` is never forwarded, unlike the
control's flat `get_runbook`/`list_runbooks` tools (server_wrapper), which
return it unconditionally. Two narrow tools cover the rest: `search_runbooks`
(repo-scoped lookup, so the agent can find an id without wading through every
resource by hand) and `acknowledge_runbook` (the one write action, mirroring
the control's tool exactly).
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("resource-gateway")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))


@mcp.resource("runbook://{id}")
async def get_runbook_resource(id: str) -> str:
    response = await client.get(f"/runbooks/{id}")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no runbook with id {id}")
    response.raise_for_status()
    return response.json()["body"]


@mcp.tool()
async def search_runbooks(repo_id: int) -> list[dict]:
    """List a repo's runbooks by id and title only -- read `runbook://{id}` for
    a runbook's body."""
    response = await client.get("/runbooks", params={"repo_id": repo_id})
    response.raise_for_status()
    return [{"id": r["id"], "repo_id": r["repo_id"], "title": r["title"]} for r in response.json()]


@mcp.tool()
async def acknowledge_runbook(runbook_id: int, note: str) -> dict[str, Any]:
    response = await client.post(f"/runbooks/{runbook_id}/acknowledgements", json={"note": note})
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run()
