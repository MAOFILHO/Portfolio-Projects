"""ADR-012's falsifiable test -- the core deliverable of Phase 5 Stage 2, not a nice-to-have.

ADR-012 decides that the LangGraph runtime calls these tool handlers in-process, never over the MCP
wire protocol, for latency reasons -- but it only gets to make that framing honestly if the *same*
handlers, unmodified, really are servable over the wire. This module is the check: for each of the four
domain servers, it launches the actual server subprocess -- the same command a `.claude/mcp.json` entry
runs (`sys.executable -m fnol_voice_agent.mcp.<name>_server`, exactly as registered in `.claude/mcp.json`
at the repo root) -- drives it with the real `mcp` SDK client over real stdio, calls each tool, and
asserts the result matches calling the handler directly, in-process, for the same input.

This is a real subprocess and a real JSON-RPC round trip. Nothing here is mocked: no monkeypatched
transport, no in-memory fake session, no stub server.

If a handler needed to import `mcp`, take a `Context` parameter, or otherwise "know" it might be called
over the wire in order for this file to pass, that would falsify ADR-012's premise -- see
`test_mcp_policy_server.py::test_importing_this_module_does_not_import_the_mcp_transport_package` (and
its siblings in the other three domain test files) for the direct, automated check of exactly that
property. No such modification was needed to write this file: every domain module's handler(s) are
registered with a plain `server.add_tool(handler)` call, using each handler's own existing type-hinted
signature and Pydantic return type as the tool schema, with no handler-side code aware that this is
happening.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from fnol_voice_agent.mcp.claims_server import get_claim_status, get_rental_status
from fnol_voice_agent.mcp.escalation_server import initiate_escalation
from fnol_voice_agent.mcp.policy_server import get_policyholder_elections


@pytest.fixture
def anyio_backend() -> str:
    # asyncio only -- trio isn't a project dependency and nothing here needs it.
    return "asyncio"


@asynccontextmanager
async def _server_session(module: str) -> AsyncIterator[ClientSession]:
    """Launches `python -m <module>` as a real subprocess -- the exact command a `.claude/mcp.json`
    entry for that module runs (see the repo-root `.claude/mcp.json`) -- and yields an initialized
    `ClientSession` connected to it over real stdio.
    """
    params = StdioServerParameters(command=sys.executable, args=["-m", module])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


# --- policy_server (required minimum per the task) -------------------------------------------------


@pytest.mark.anyio
async def test_policy_server_wire_call_matches_in_process_call() -> None:
    in_process = get_policyholder_elections("PY4821")

    async with _server_session("fnol_voice_agent.mcp.policy_server") as session:
        tools = await session.list_tools()
        assert "get_policyholder_elections" in {t.name for t in tools.tools}

        result = await session.call_tool("get_policyholder_elections", {"policy_number": "PY4821"})

    assert result.is_error is False
    assert result.structured_content == in_process.model_dump(mode="json")


@pytest.mark.anyio
async def test_policy_server_wire_call_error_path_matches_in_process_exception() -> None:
    from fnol_voice_agent.mcp.policy_server import PolicyNotFoundError

    with pytest.raises(PolicyNotFoundError) as excinfo:
        get_policyholder_elections("PY9999")
    in_process_message = str(excinfo.value)

    async with _server_session("fnol_voice_agent.mcp.policy_server") as session:
        result = await session.call_tool("get_policyholder_elections", {"policy_number": "PY9999"})

    assert result.is_error is True
    wire_message = result.content[0].text  # type: ignore[union-attr]
    assert in_process_message in wire_message


# --- claims_server -----------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_claims_server_wire_call_matches_in_process_call_by_claim_number() -> None:
    in_process = get_claim_status(claim_number="CLM-2608-00042-4")

    async with _server_session("fnol_voice_agent.mcp.claims_server") as session:
        result = await session.call_tool("get_claim_status", {"claim_number": "CLM-2608-00042-4"})

    assert result.is_error is False
    assert result.structured_content == in_process.model_dump(mode="json")


@pytest.mark.anyio
async def test_claims_server_wire_call_matches_in_process_call_by_policy_number() -> None:
    # Exercises the "most recent open claim" resolution path over the wire too, not just the
    # direct-claim-number path.
    in_process = get_claim_status(policy_number="PY4821")

    async with _server_session("fnol_voice_agent.mcp.claims_server") as session:
        result = await session.call_tool("get_claim_status", {"policy_number": "PY4821"})

    assert result.is_error is False
    assert result.structured_content == in_process.model_dump(mode="json")


@pytest.mark.anyio
async def test_claims_server_wire_call_matches_in_process_call_for_rental_status() -> None:
    in_process = get_rental_status("CLM-2608-00042-4")

    async with _server_session("fnol_voice_agent.mcp.claims_server") as session:
        result = await session.call_tool("get_rental_status", {"claim_number": "CLM-2608-00042-4"})

    assert result.is_error is False
    assert result.structured_content == in_process.model_dump(mode="json")


# --- contact_server ------------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_contact_server_wire_call_matches_in_process_call() -> None:
    # The write path's in-memory store is process-local (contact_server.py's own docstring), so the
    # subprocess and this test process each start from their own fresh copy of the same synthetic
    # corpus -- there is no shared state to read back across the process boundary, by design. What is
    # comparable, deterministically, is that an identical write against an identical starting record
    # produces an identical result in both places.
    from fnol_voice_agent.mcp.contact_server import update_contact_info

    in_process = update_contact_info("PY4821", "phone", "555-4242")

    async with _server_session("fnol_voice_agent.mcp.contact_server") as session:
        result = await session.call_tool(
            "update_contact_info",
            {"policy_number": "PY4821", "field": "phone", "new_value": "555-4242"},
        )

    assert result.is_error is False
    assert result.structured_content == in_process.model_dump(mode="json")


# --- escalation_server ---------------------------------------------------------------------------------


@pytest.mark.anyio
async def test_escalation_server_wire_call_matches_in_process_call() -> None:
    in_process = initiate_escalation(
        contact_id="contact-999",
        triggering_layer="L1",
        context={"policy_number": "PY4821", "triggering_utterance": "someone is hurt"},
    )

    async with _server_session("fnol_voice_agent.mcp.escalation_server") as session:
        result = await session.call_tool(
            "initiate_escalation",
            {
                "contact_id": "contact-999",
                "triggering_layer": "L1",
                "context": {"policy_number": "PY4821", "triggering_utterance": "someone is hurt"},
            },
        )

    assert result.is_error is False
    assert result.structured_content == in_process.model_dump(mode="json")
