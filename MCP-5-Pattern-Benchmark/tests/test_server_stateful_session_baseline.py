"""Tests for the Stateful Session Server module's baseline (server_baseline).

Same seam as test_server_wrapper.py: a real in-memory MCP ClientSession,
tools backed by the real /repos API + a real (throwaway) Postgres, no
mocking. This baseline is its own server per ADR 0002 (not a reuse of
server_wrapper), because the module under test is the baseline's resend
behavior itself.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.stateful_session import server_baseline
from src.mcp_services.stateful_session.server_baseline import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_baseline, "client",
        httpx.AsyncClient(transport=transport, base_url="http://testserver"),
    )
    return mcp


async def call(mcp_instance, tool_name: str, arguments: dict | None = None):
    async with create_connected_server_and_client_session(mcp_instance) as session:
        result = await session.call_tool(tool_name, arguments or {})
        assert not result.isError, result.content
        return result.structuredContent


async def test_exposes_exactly_three_tools():
    async with create_connected_server_and_client_session(mcp) as session:
        tools = await session.list_tools()

    assert sorted(tool.name for tool in tools.tools) == [
        "get_change_request",
        "list_change_requests",
        "save_review",
    ]


async def test_list_change_requests_returns_every_change_request(wrapped_mcp):
    crs = (await call(wrapped_mcp, "list_change_requests"))["result"]

    assert len(crs) == 8
    assert any(cr["title"] == "Add retry to payment webhook" for cr in crs)


async def test_get_change_request_returns_it_from_the_real_backend(wrapped_mcp):
    cr = await call(wrapped_mcp, "get_change_request", {"change_request_id": 1})

    assert cr["title"] == "Fix rounding error in invoice totals"
    assert cr["status"] == "open"


async def test_save_review_without_a_verdict_persists_nothing(wrapped_mcp):
    result = await call(
        wrapped_mcp,
        "save_review",
        {"change_request_id": 1, "comments": ["First pass"]},
    )

    assert result == {"comment_count": 1}
    refetched = (await server_baseline.client.get("/change-requests/1/comments")).json()
    assert refetched == []


async def test_save_review_with_a_verdict_persists_every_comment_and_the_status(wrapped_mcp):
    await call(
        wrapped_mcp,
        "save_review",
        {
            "change_request_id": 1,
            "comments": ["First pass", "Second pass"],
            "verdict": "approved",
        },
    )

    comments = (await server_baseline.client.get("/change-requests/1/comments")).json()
    assert [c["body"] for c in comments] == ["First pass", "Second pass"]
    cr = (await server_baseline.client.get("/change-requests/1")).json()
    assert cr["status"] == "approved"
