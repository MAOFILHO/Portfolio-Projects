"""Pattern server for the Domain-Specific Adapter module.

Exposes one tool, resolve_customer_ticket, named for the business outcome
rather than for the CRUD steps underneath it: given the ticket's title (the
identifier a support agent actually has, not an internal row id), it looks
up the ticket, checks its customer's tier, and applies that tier's handling
(priority queue + flagged note for premium, standard queue otherwise) in one
server-side call, instead of the agent having to discover the id, fetch the
customer, learn the tier rule, and apply it itself. Fronts the same
/tickets API as server_wrapper (Phase 1) and server_orchestrator, extended
with customer_id (Phase 2).
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("domain-adapter-pattern")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))

PREMIUM_ASSIGNEE = "priority-support"
STANDARD_ASSIGNEE = "support-standard"


@mcp.tool()
async def resolve_customer_ticket(ticket_title: str, resolution_note: str) -> dict[str, Any]:
    tickets = (await client.get("/tickets")).json()
    matches = [t for t in tickets if t["title"] == ticket_title]
    if not matches:
        raise ValueError(f"No such ticket: {ticket_title!r}")
    ticket_id = matches[0]["id"]

    customer_response = await client.get(f"/tickets/{ticket_id}/customer")
    if customer_response.status_code == 404:
        raise ValueError(f"404 Not Found: no customer linked to ticket {ticket_id}")
    customer_response.raise_for_status()
    is_premium = customer_response.json()["tier"] == "premium"

    ticket = (
        await client.patch(
            f"/tickets/{ticket_id}",
            json={
                "status": "resolved",
                "assignee": PREMIUM_ASSIGNEE if is_premium else STANDARD_ASSIGNEE,
            },
        )
    ).json()
    already_tagged = resolution_note.startswith("[PRIORITY]")
    note = f"[PRIORITY] {resolution_note}" if is_premium and not already_tagged else resolution_note
    comment = (
        await client.post(f"/tickets/{ticket_id}/comments", json={"body": note})
    ).json()

    return {"ticket": ticket, "comment": comment}


if __name__ == "__main__":
    mcp.run()
