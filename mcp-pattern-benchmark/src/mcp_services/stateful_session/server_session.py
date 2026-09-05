"""Pattern server for the Stateful Session Server module.

Holds working state across turns behind session tools instead of forcing
the agent to resend it (contrast server_baseline). start_review opens a
session; add_comment appends one comment to server-held state, in memory,
not Postgres — the backend stays free of MCP-layer concepts, confirmed with
the user over a Postgres sessions table. submit_review persists every
accumulated comment plus the verdict in one shot, then forgets the session.
"""

import os
from typing import Any
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stateful-session-pattern")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))

# ponytail: process-local dict, one pattern-server process per task run
# (matches every other in-process server in this repo) — a multi-worker
# deployment would need a shared store instead.
_sessions: dict[str, dict[str, Any]] = {}


@mcp.tool()
async def list_change_requests() -> list[dict]:
    response = await client.get("/change-requests")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def start_review(change_request_id: int) -> str:
    session_id = str(uuid4())
    _sessions[session_id] = {"change_request_id": change_request_id, "comments": []}
    return session_id


@mcp.tool()
async def add_comment(session_id: str, body: str) -> dict[str, int]:
    """Add one comment to the open review session. Already safely held by
    the session the moment this returns — there is no separate save or
    checkpoint step."""
    if session_id not in _sessions:
        raise ValueError(f"no open review session {session_id}")
    _sessions[session_id]["comments"].append(body)
    return {"count": len(_sessions[session_id]["comments"])}


@mcp.tool()
async def submit_review(session_id: str, verdict: str) -> dict[str, Any]:
    """Finalize the review and close the session. Call this exactly once,
    only after every comment has been added — it is not a way to save
    progress, and closing the session loses any comments not yet added."""
    if session_id not in _sessions:
        raise ValueError(f"no open review session {session_id}")
    state = _sessions.pop(session_id)

    for body in state["comments"]:
        response = await client.post(
            f"/change-requests/{state['change_request_id']}/comments", json={"body": body}
        )
        response.raise_for_status()
    response = await client.patch(
        f"/change-requests/{state['change_request_id']}", json={"status": verdict}
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run()
