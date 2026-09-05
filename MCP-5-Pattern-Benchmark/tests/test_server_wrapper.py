"""Tests for the Tool Orchestrator control server (server_wrapper).

Drives the server's tools through a real MCP ClientSession, in-memory,
exactly the interface the agent calls through. server_wrapper's tools call
the real /tickets API in turn, backed by a real (throwaway) Postgres --
no subprocess, no LLM, no mocking.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.tool_orchestrator import server_wrapper
from src.mcp_services.tool_orchestrator.server_wrapper import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    """Point server_wrapper's HTTP client at the real API in-process, backed
    by the real (seeded) test Postgres."""
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_wrapper, "client", httpx.AsyncClient(transport=transport, base_url="http://testserver")
    )
    return mcp


async def call(mcp_instance, tool_name: str, arguments: dict | None = None):
    """Call a tool through a real in-memory MCP session and return its
    structured result (the same data an agent's client receives)."""
    async with create_connected_server_and_client_session(mcp_instance) as session:
        result = await session.call_tool(tool_name, arguments or {})
        assert not result.isError, result.content
        return result.structuredContent


async def test_list_tickets_returns_tickets_from_the_real_backend(wrapped_mcp):
    tickets = (await call(wrapped_mcp, "list_tickets"))["result"]

    assert tickets == [
        {"id": 1, "title": "Printer not connecting to network", "status": "open", "assignee": None},
        {"id": 2, "title": "Password reset request", "status": "closed", "assignee": "jdoe"},
        {"id": 3, "title": "VPN access failing for remote team", "status": "open", "assignee": None},
        {"id": 4, "title": "Invoice not received for last billing cycle", "status": "open", "assignee": None},
        {"id": 5, "title": "Security camera feed offline at HQ", "status": "open", "assignee": None},
        {"id": 6, "title": "Loyalty points not applied at checkout", "status": "open", "assignee": None},
        {"id": 7, "title": "API rate limit errors on integration", "status": "open", "assignee": None},
        {"id": 8, "title": "Shipping label printer jammed", "status": "open", "assignee": None},
    ]


async def test_get_ticket_returns_a_ticket_that_only_exists_in_the_real_backend(wrapped_mcp):
    created = (await server_wrapper.client.post("/tickets", json={"title": "New issue"})).json()

    ticket = await call(wrapped_mcp, "get_ticket", {"ticket_id": created["id"]})

    assert ticket == created


async def test_get_ticket_reports_unknown_id_as_an_error(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("get_ticket", {"ticket_id": 999})

    assert result.isError
    assert "404" in result.content[0].text


async def test_create_ticket_persists_a_new_ticket_in_the_real_backend(wrapped_mcp):
    ticket = await call(wrapped_mcp, "create_ticket", {"title": "New issue", "description": "n/a"})

    assert ticket == {"id": 9, "title": "New issue", "status": "open", "assignee": None}
    refetched = (await server_wrapper.client.get("/tickets/9")).json()
    assert refetched == ticket


async def test_update_ticket_persists_the_change_in_the_real_backend(wrapped_mcp):
    ticket = await call(wrapped_mcp, "update_ticket", {"ticket_id": 1, "status": "closed", "assignee": "asmith"})

    assert ticket == {
        "id": 1,
        "title": "Printer not connecting to network",
        "status": "closed",
        "assignee": "asmith",
    }
    refetched = (await server_wrapper.client.get("/tickets/1")).json()
    assert refetched == ticket


async def test_add_comment_persists_a_comment_in_the_real_backend(wrapped_mcp):
    comment = await call(wrapped_mcp, "add_comment", {"ticket_id": 1, "body": "Looking into it"})

    assert comment == {"id": 1, "ticket_id": 1, "body": "Looking into it"}


async def test_add_comment_rejects_an_unknown_ticket_id(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("add_comment", {"ticket_id": 999, "body": "orphaned"})

    assert result.isError


async def test_add_attachment_persists_an_attachment_in_the_real_backend(wrapped_mcp):
    attachment = await call(wrapped_mcp, "add_attachment", {"ticket_id": 1, "filename": "screenshot.png"})

    assert attachment == {"id": 1, "ticket_id": 1, "filename": "screenshot.png"}


async def test_add_attachment_rejects_an_unknown_ticket_id(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("add_attachment", {"ticket_id": 999, "filename": "x.png"})

    assert result.isError


async def test_get_ticket_customer_returns_the_linked_customer(wrapped_mcp):
    customer = await call(wrapped_mcp, "get_ticket_customer", {"ticket_id": 1})

    assert customer == {"id": 1, "name": "Acme Corp", "tier": "premium"}


async def test_get_ticket_customer_reports_no_link_as_an_error(wrapped_mcp):
    ticket = await call(wrapped_mcp, "create_ticket", {"title": "No customer"})

    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("get_ticket_customer", {"ticket_id": ticket["id"]})

    assert result.isError
    assert "404" in result.content[0].text


async def test_create_deploy_persists_a_new_deploy_in_the_real_backend(wrapped_mcp):
    deploy = await call(wrapped_mcp, "create_deploy", {"repo_id": 1, "environment": "production"})

    assert deploy == {"id": 1, "repo_id": 1, "environment": "production", "status": "pending"}
    refetched = (await server_wrapper.client.get("/deploys/1")).json()
    assert refetched == deploy


async def test_get_deploy_returns_a_deploy_that_only_exists_in_the_real_backend(wrapped_mcp):
    created = await call(wrapped_mcp, "create_deploy", {"repo_id": 1, "environment": "staging"})

    deploy = await call(wrapped_mcp, "get_deploy", {"deploy_id": created["id"]})

    assert deploy == created


async def test_get_deploy_reports_unknown_id_as_an_error(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("get_deploy", {"deploy_id": 999})

    assert result.isError
    assert "404" in result.content[0].text


async def test_update_deploy_status_persists_the_change_in_the_real_backend(wrapped_mcp):
    created = await call(wrapped_mcp, "create_deploy", {"repo_id": 1, "environment": "production"})

    deploy = await call(wrapped_mcp, "update_deploy_status", {"deploy_id": created["id"], "status": "succeeded"})

    assert deploy == {**created, "status": "succeeded"}
    refetched = (await server_wrapper.client.get(f"/deploys/{created['id']}")).json()
    assert refetched == deploy


async def test_update_deploy_status_rejects_an_unknown_deploy_id(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("update_deploy_status", {"deploy_id": 999, "status": "succeeded"})

    assert result.isError
    assert "404" in result.content[0].text


async def test_get_change_request_returns_a_change_request_from_the_real_backend(wrapped_mcp):
    change_request = await call(wrapped_mcp, "get_change_request", {"change_request_id": 1})

    assert change_request == {
        "id": 1,
        "repo_id": 1,
        "title": "Fix rounding error in invoice totals",
        "diff": "--- a/invoice.py\n+++ b/invoice.py\n",
        "status": "open",
    }


async def test_get_change_request_reports_unknown_id_as_an_error(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("get_change_request", {"change_request_id": 999})

    assert result.isError
    assert "404" in result.content[0].text


async def test_list_runbooks_returns_runbooks_for_a_repo_from_the_real_backend(wrapped_mcp):
    runbooks = (await call(wrapped_mcp, "list_runbooks", {"repo_id": 1}))["result"]

    assert runbooks == [
        {
            "id": 1,
            "repo_id": 1,
            "title": "Rolling back a bad billing deploy",
            "body": "1. Halt traffic. 2. Redeploy last tag.",
            "internal_notes": (
                "Escalate to payments-oncall before rolling back; "
                "past rollbacks corrupted the ledger."
            ),
        },
        {
            "id": 2,
            "repo_id": 1,
            "title": "Reconciling a stuck payment webhook",
            "body": "1. Check dead-letter queue. 2. Replay.",
            "internal_notes": "The vendor sandbox key is hardcoded in webhook.py; rotate it after use.",
        },
    ]


async def test_get_runbook_returns_a_runbook_that_only_exists_in_the_real_backend(wrapped_mcp):
    runbook = await call(wrapped_mcp, "get_runbook", {"runbook_id": 1})

    assert runbook == {
        "id": 1,
        "repo_id": 1,
        "title": "Rolling back a bad billing deploy",
        "body": "1. Halt traffic. 2. Redeploy last tag.",
        "internal_notes": (
            "Escalate to payments-oncall before rolling back; "
            "past rollbacks corrupted the ledger."
        ),
    }


async def test_get_runbook_reports_unknown_id_as_an_error(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool("get_runbook", {"runbook_id": 999})

    assert result.isError
    assert "404" in result.content[0].text


async def test_acknowledge_runbook_persists_a_note_in_the_real_backend(wrapped_mcp):
    ack = await call(wrapped_mcp, "acknowledge_runbook", {"runbook_id": 1, "note": "Reviewed"})

    assert ack == {"id": 1, "runbook_id": 1, "note": "Reviewed"}
    refetched = (await server_wrapper.client.get("/runbooks/1/acknowledgements")).json()
    assert refetched == [ack]
