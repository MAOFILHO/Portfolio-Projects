"""Tests for the Tool Orchestrator pattern server (server_orchestrator).

Same seam as server_wrapper's tests: a real in-memory MCP ClientSession,
tools backed by the real /tickets API + a real (throwaway) Postgres, no
mocking.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.tool_orchestrator import server_orchestrator
from src.mcp_services.tool_orchestrator.server_orchestrator import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_orchestrator, "client",
        httpx.AsyncClient(transport=transport, base_url="http://testserver"),
    )
    return mcp


async def test_exposes_exactly_one_tool_coordinate_incident():
    async with create_connected_server_and_client_session(mcp) as session:
        tools = await session.list_tools()

    assert [tool.name for tool in tools.tools] == ["coordinate_incident"]


async def test_coordinate_incident_creates_attaches_assigns_and_notifies_in_one_call(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        result = await session.call_tool(
            "coordinate_incident",
            {
                "title": "Printer offline",
                "evidence_filename": "log.txt",
                "assignee": "asmith",
                "notification": "Assigned to asmith",
            },
        )
        assert not result.isError, result.content

    assert result.structuredContent == {
        "ticket": {"id": 9, "title": "Printer offline", "status": "open", "assignee": "asmith"},
        "attachment": {"id": 1, "ticket_id": 9, "filename": "log.txt"},
        "comment": {"id": 1, "ticket_id": 9, "body": "Assigned to asmith"},
    }
