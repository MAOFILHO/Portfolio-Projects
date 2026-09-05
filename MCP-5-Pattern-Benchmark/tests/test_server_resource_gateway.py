"""Tests for the Resource Gateway pattern server (server_resource_gateway).

Drives the server's resource and tools through a real MCP ClientSession,
in-memory, exactly the interface the agent calls through, backed by a real
(throwaway) Postgres -- no subprocess, no LLM, no mocking. Same seam as
test_server_wrapper.py/test_server_proxy_aggregator.py.
"""

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from backend.app import app as backend_app
from backend.seed import reset_and_seed
from src.mcp_services.resource_gateway import server_resource_gateway
from src.mcp_services.resource_gateway.server_resource_gateway import mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def wrapped_mcp(db, monkeypatch):
    """Point server_resource_gateway's HTTP client at the real API in-process,
    backed by the real (seeded) test Postgres."""
    reset_and_seed(db)
    transport = httpx.ASGITransport(app=backend_app)
    monkeypatch.setattr(
        server_resource_gateway,
        "client",
        httpx.AsyncClient(transport=transport, base_url="http://testserver"),
    )
    return mcp


async def call(mcp_instance, tool_name: str, arguments: dict | None = None):
    """Call a tool through a real in-memory MCP session and return its
    structured result (the same data an agent's client receives)."""
    async with create_connected_server_and_client_session(mcp_instance) as session:
        result = await session.call_tool(tool_name, arguments or {})
        assert not result.isError, result.content
        return result.structuredContent


async def read(mcp_instance, uri: str) -> str:
    async with create_connected_server_and_client_session(mcp_instance) as session:
        result = await session.read_resource(uri)
        return result.contents[0].text


async def test_read_resource_returns_only_the_sanitized_body(wrapped_mcp):
    body = await read(wrapped_mcp, "runbook://1")

    assert body == "1. Halt traffic. 2. Redeploy last tag."
    assert "payments-oncall" not in body


async def test_read_resource_reports_unknown_id_as_an_error(wrapped_mcp):
    async with create_connected_server_and_client_session(wrapped_mcp) as session:
        with pytest.raises(Exception, match="404"):
            await session.read_resource("runbook://999")


async def test_search_runbooks_omits_body_and_internal_notes(wrapped_mcp):
    runbooks = (await call(wrapped_mcp, "search_runbooks", {"repo_id": 1}))["result"]

    assert runbooks == [
        {"id": 1, "repo_id": 1, "title": "Rolling back a bad billing deploy"},
        {"id": 2, "repo_id": 1, "title": "Reconciling a stuck payment webhook"},
    ]


async def test_acknowledge_runbook_persists_a_note_in_the_real_backend(wrapped_mcp):
    ack = await call(wrapped_mcp, "acknowledge_runbook", {"runbook_id": 1, "note": "Reviewed"})

    assert ack == {"id": 1, "runbook_id": 1, "note": "Reviewed"}
    refetched = (await server_resource_gateway.client.get("/runbooks/1/acknowledgements")).json()
    assert refetched == [ack]
