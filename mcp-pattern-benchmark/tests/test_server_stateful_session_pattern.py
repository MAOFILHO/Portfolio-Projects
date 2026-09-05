"""Tests for the Stateful Session Server module's pattern server
(server_session).

Same seam as test_server_orchestrator.py. Session state lives in the
server's process memory (a dict keyed by session_id), confirmed with the
user over a Postgres sessions table — the backend stays free of MCP-layer
concepts, and only the final submitted review needs to be durable.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.stateful_session import server_session
from src.mcp_services.stateful_session.server_session import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_session, "client",
        httpx.AsyncClient(transport=transport, base_url="http://testserver"),
    )
    return mcp


async def call(mcp_instance, tool_name: str, arguments: dict | None = None):
    async with create_connected_server_and_client_session(mcp_instance) as session:
        result = await session.call_tool(tool_name, arguments or {})
        assert not result.isError, result.content
        return result.structuredContent


async def test_exposes_exactly_four_tools():
    async with create_connected_server_and_client_session(mcp) as session:
        tools = await session.list_tools()

    assert sorted(tool.name for tool in tools.tools) == [
        "add_comment",
        "list_change_requests",
        "start_review",
        "submit_review",
    ]


async def test_list_change_requests_returns_every_change_request(wrapped_mcp):
    crs = (await call(wrapped_mcp, "list_change_requests"))["result"]

    assert len(crs) == 8
    assert any(cr["title"] == "Add retry to payment webhook" for cr in crs)


async def test_full_session_persists_every_comment_and_the_status_on_submit(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        started = await session.call_tool("start_review", {"change_request_id": 1})
        session_id = started.structuredContent["result"]

        first = await session.call_tool("add_comment", {"session_id": session_id, "body": "First pass"})
        assert first.structuredContent == {"count": 1}

        second = await session.call_tool("add_comment", {"session_id": session_id, "body": "Second pass"})
        assert second.structuredContent == {"count": 2}

        submitted = await session.call_tool(
            "submit_review", {"session_id": session_id, "verdict": "approved"}
        )
        assert not submitted.isError, submitted.content

    comments = (await server_session.client.get("/change-requests/1/comments")).json()
    assert [c["body"] for c in comments] == ["First pass", "Second pass"]
    cr = (await server_session.client.get("/change-requests/1")).json()
    assert cr["status"] == "approved"


async def test_submit_review_forgets_the_session(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        started = await session.call_tool("start_review", {"change_request_id": 1})
        session_id = started.structuredContent["result"]
        await session.call_tool("submit_review", {"session_id": session_id, "verdict": "approved"})

        result = await session.call_tool("add_comment", {"session_id": session_id, "body": "too late"})

    assert result.isError
