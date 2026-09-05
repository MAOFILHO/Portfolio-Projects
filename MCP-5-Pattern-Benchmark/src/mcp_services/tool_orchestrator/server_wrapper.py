"""Control server for the Tool Orchestrator module.

A flat 1:1 wrapper over the /tickets HTTP API: one tool per endpoint,
vendor-named, raw JSON payloads, HTTP status codes surfaced as error text.
Reused as-is as the baseline for the Domain-Specific Adapter module (Phase 2,
service "domain_wrapper"), which adds get_ticket_customer for that purpose.
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tool-orchestrator-wrapper")

client = httpx.AsyncClient(base_url=os.environ.get("TICKETS_API_URL", "http://localhost:8000"))


@mcp.tool()
async def list_tickets() -> list[dict]:
    response = await client.get("/tickets")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    response = await client.get(f"/tickets/{ticket_id}")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no ticket with id {ticket_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def create_ticket(title: str, description: str = "") -> dict[str, Any]:
    response = await client.post("/tickets", json={"title": title, "description": description})
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def update_ticket(
    ticket_id: int, status: str | None = None, assignee: str | None = None
) -> dict[str, Any]:
    response = await client.patch(
        f"/tickets/{ticket_id}", json={"status": status, "assignee": assignee}
    )
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no ticket with id {ticket_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def add_comment(ticket_id: int, body: str) -> dict[str, Any]:
    response = await client.post(f"/tickets/{ticket_id}/comments", json={"body": body})
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def add_attachment(ticket_id: int, filename: str) -> dict[str, Any]:
    response = await client.post(f"/tickets/{ticket_id}/attachments", json={"filename": filename})
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def get_ticket_customer(ticket_id: int) -> dict[str, Any]:
    response = await client.get(f"/tickets/{ticket_id}/customer")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no customer linked to ticket {ticket_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def list_runbooks(repo_id: int) -> list[dict]:
    response = await client.get("/runbooks", params={"repo_id": repo_id})
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def get_runbook(runbook_id: int) -> dict[str, Any]:
    response = await client.get(f"/runbooks/{runbook_id}")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no runbook with id {runbook_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def create_deploy(repo_id: int, environment: str) -> dict[str, Any]:
    response = await client.post("/deploys", json={"repo_id": repo_id, "environment": environment})
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def get_deploy(deploy_id: int) -> dict[str, Any]:
    response = await client.get(f"/deploys/{deploy_id}")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no deploy with id {deploy_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def update_deploy_status(deploy_id: int, status: str) -> dict[str, Any]:
    response = await client.patch(f"/deploys/{deploy_id}", json={"status": status})
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no deploy with id {deploy_id}")
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def acknowledge_runbook(runbook_id: int, note: str) -> dict[str, Any]:
    response = await client.post(f"/runbooks/{runbook_id}/acknowledgements", json={"note": note})
    response.raise_for_status()
    return response.json()


@mcp.tool()
async def get_change_request(change_request_id: int) -> dict[str, Any]:
    response = await client.get(f"/change-requests/{change_request_id}")
    if response.status_code == 404:
        raise ValueError(f"404 Not Found: no change request with id {change_request_id}")
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run()
