"""Pattern server for the Tool Orchestrator module.

Exposes one tool, coordinate_incident, that performs the create incident ->
attach evidence -> assign owner -> post notification sequence in one
server-side call against the /tickets API, instead of four agent-driven
calls. Fronts the same backend as server_wrapper (Ticket 02).
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tool-orchestrator-pattern")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))


@mcp.tool()
async def coordinate_incident(
    title: str,
    evidence_filename: str,
    assignee: str,
    notification: str,
    description: str = "",
) -> dict[str, Any]:
    ticket = (
        await client.post("/tickets", json={"title": title, "description": description})
    ).json()
    ticket_id = ticket["id"]

    attachment = (
        await client.post(
            f"/tickets/{ticket_id}/attachments", json={"filename": evidence_filename}
        )
    ).json()
    ticket = (await client.patch(f"/tickets/{ticket_id}", json={"assignee": assignee})).json()
    comment = (
        await client.post(f"/tickets/{ticket_id}/comments", json={"body": notification})
    ).json()

    return {"ticket": ticket, "attachment": attachment, "comment": comment}


if __name__ == "__main__":
    mcp.run()
