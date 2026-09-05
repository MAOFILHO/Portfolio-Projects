"""Baseline server for the Stateful Session Server module.

Its own server, not the reused control, per ADR 0002 — the module under
test is the baseline's resend behavior, not a smaller tool surface (ADR
0007). It remembers nothing between calls: save_review with no verdict is a
pure checkpoint (validates, returns a count, writes nothing); the agent must
resend every comment so far on each call, and only the call carrying a
verdict persists anything to the real /repos API.
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stateful-session-baseline")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))


@mcp.tool()
async def list_change_requests() -> list[dict]:
    response = await client.get("/change-requests")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def get_change_request(change_request_id: int) -> dict[str, Any]:
    response = await client.get(f"/change-requests/{change_request_id}")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no change request with id {change_request_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def save_review(
    change_request_id: int, comments: list[str], verdict: str | None = None
) -> dict[str, Any]:
    """Save (or submit) a review draft. This call remembers nothing from any
    previous call: `comments` must be the full list of every comment in this
    review so far, not just new ones, or earlier comments are lost. Pass
    `verdict` only on the final call, once every comment is included, to
    persist the review and close it."""
    if verdict is None:
        return {"comment_count": len(comments)}

    for body in comments:
        response = await client.post(
            f"/change-requests/{change_request_id}/comments", json={"body": body}
        )
        response.raise_for_status()
    response = await client.patch(
        f"/change-requests/{change_request_id}", json={"status": verdict}
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run()
