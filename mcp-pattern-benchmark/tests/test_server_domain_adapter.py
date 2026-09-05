"""Tests for the Domain-Specific Adapter pattern server (server_domain_adapter).

Same seam as server_wrapper's/server_orchestrator's tests: a real in-memory
MCP ClientSession, tools backed by the real /tickets API + a real (throwaway)
Postgres, no mocking.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.domain_adapter import server_domain_adapter
from src.mcp_services.domain_adapter.server_domain_adapter import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_domain_adapter, "client",
        httpx.AsyncClient(transport=transport, base_url="http://testserver"),
    )
    return mcp


async def test_exposes_exactly_one_tool_resolve_customer_ticket():
    async with create_connected_server_and_client_session(mcp) as session:
        tools = await session.list_tools()

    assert [tool.name for tool in tools.tools] == ["resolve_customer_ticket"]


async def test_resolve_customer_ticket_gives_a_premium_customer_priority_handling(wrapped_mcp):
    # Seeded linked to Acme Corp, a premium customer.
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool(
            "resolve_customer_ticket",
            {
                "ticket_title": "Printer not connecting to network",
                "resolution_note": "Replaced the cable",
            },
        )
        assert not result.isError, result.content

    assert result.structuredContent == {
        "ticket": {
            "id": 1,
            "title": "Printer not connecting to network",
            "status": "resolved",
            "assignee": "priority-support",
        },
        "comment": {"id": 1, "ticket_id": 1, "body": "[PRIORITY] Replaced the cable"},
    }


async def test_resolve_customer_ticket_does_not_double_tag_an_already_tagged_note(wrapped_mcp):
    # An agent following the task's own policy wording may tag the note
    # itself; the tool must not tag it a second time.
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool(
            "resolve_customer_ticket",
            {
                "ticket_title": "Printer not connecting to network",
                "resolution_note": "[PRIORITY] Replaced the cable",
            },
        )
        assert not result.isError, result.content

    assert result.structuredContent["comment"]["body"] == "[PRIORITY] Replaced the cable"


async def test_resolve_customer_ticket_gives_a_standard_customer_normal_handling(wrapped_mcp):
    # Seeded linked to Bob's Shop, a standard customer.
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool(
            "resolve_customer_ticket",
            {"ticket_title": "Password reset request", "resolution_note": "Reset the password"},
        )
        assert not result.isError, result.content

    assert result.structuredContent == {
        "ticket": {
            "id": 2,
            "title": "Password reset request",
            "status": "resolved",
            "assignee": "support-standard",
        },
        "comment": {"id": 1, "ticket_id": 2, "body": "Reset the password"},
    }


async def test_resolve_customer_ticket_reports_an_unknown_title_as_an_error(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool(
            "resolve_customer_ticket",
            {"ticket_title": "No such ticket", "resolution_note": "n/a"},
        )

    assert result.isError
    assert "No such ticket" in result.content[0].text
