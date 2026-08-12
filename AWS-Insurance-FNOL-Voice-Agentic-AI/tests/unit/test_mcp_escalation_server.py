"""In-process handler tests for `fnol_voice_agent.mcp.escalation_server`."""

from __future__ import annotations

import pytest

from fnol_voice_agent.mcp.escalation_server import (
    InvalidEscalationRequestError,
    initiate_escalation,
)


def test_initiate_escalation_returns_structured_handoff_record() -> None:
    result = initiate_escalation(
        contact_id="contact-123",
        triggering_layer="L1",
        context={"policy_number": "PY4821", "triggering_utterance": "he's not breathing"},
    )
    assert result.status == "transfer_initiated"
    assert result.contact_id == "contact-123"
    assert result.triggering_layer == "L1"
    assert result.context == {
        "policy_number": "PY4821",
        "triggering_utterance": "he's not breathing",
    }
    # Never claims a real Connect transfer happened -- that's Phase 8's job (BUILD-PLAN.md Stage 2).
    assert result.real_connect_transfer_executed is False


def test_initiate_escalation_defaults_context_to_empty_dict() -> None:
    result = initiate_escalation(contact_id="contact-1", triggering_layer="L3")
    assert result.context == {}


def test_initiate_escalation_is_a_pure_function_of_its_input() -> None:
    # No timestamp, no generated ID -- calling twice with identical input yields identical output,
    # which is exactly the property test_mcp_wire_protocol.py's equality assertion depends on.
    first = initiate_escalation(contact_id="c1", triggering_layer="L2", context={"a": 1})
    second = initiate_escalation(contact_id="c1", triggering_layer="L2", context={"a": 1})
    assert first == second


@pytest.mark.parametrize("layer", ["L0", "L4", "l1", "", "agent"])
def test_initiate_escalation_rejects_unknown_triggering_layer(layer: str) -> None:
    with pytest.raises(InvalidEscalationRequestError):
        initiate_escalation(contact_id="contact-1", triggering_layer=layer)


def test_initiate_escalation_rejects_blank_contact_id() -> None:
    with pytest.raises(InvalidEscalationRequestError):
        initiate_escalation(contact_id="", triggering_layer="L1")


def test_importing_this_module_does_not_import_the_mcp_transport_package() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fnol_voice_agent.mcp.escalation_server; print('mcp' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
