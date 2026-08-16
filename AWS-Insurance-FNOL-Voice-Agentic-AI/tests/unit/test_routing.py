"""`agents/nodes/routing.py` -- the merged router + L2 node (`D90` part 1, `RESULTS.md` §33/§35).

Never had its own test file: it was only ever exercised indirectly through graph-level and
Lambda-execution-level tests. This file is that missing seam, added alongside the `D90` part 1
fix rather than left absent -- `diagnosing-bugs` Phase 5's "no correct seam is itself a finding"
does not apply here once this file exists.

Every test injects a `FakeBedrockConverseClient`. No real Bedrock call happens in this file
(`ADR-013`).
"""

from __future__ import annotations

from fnol_voice_agent.agents.nodes.routing import make_route_and_classify_node
from fnol_voice_agent.agents.state import AgentState
from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_tool_use_response,
)
from fnol_voice_agent.aws.bedrock_router import CLASSIFY_TURN_TOOL_NAME


def _classification_response(
    *,
    intent: str = "CoverageQuestion",
    safety_flag: bool = False,
    intent_confidence: float = 0.9,
) -> dict[str, object]:
    return converse_tool_use_response(
        CLASSIFY_TURN_TOOL_NAME,
        {
            "safety_flag": safety_flag,
            "intent": intent,
            "intent_confidence": intent_confidence,
        },
    )


def test_route_and_classify_sends_bare_turn_text_when_no_session_context() -> None:
    """First-turn case (`active_slot`/`filled_slots` both unset): the message sent to
    `classify_turn` must be byte-identical to the pre-`D90`-part-1-fix single-line shape.
    Locks the backward-compatibility claim -- this change must not alter what a fresh call
    sends, which is what makes it safe to reason about as not disturbing `C1`'s existing
    first-turn/cold-start measurements.
    """
    fake = FakeBedrockConverseClient(responses=[_classification_response()])
    node = make_route_and_classify_node(caller=fake)

    state: AgentState = {"turn_input": "am I still covered for a rental car"}
    node(state)

    assert fake.call_count == 1
    sent_messages = fake.calls[0]["messages"]
    assert sent_messages == [
        {"role": "user", "content": [{"text": "am I still covered for a rental car"}]}
    ]


def test_route_and_classify_includes_active_slot_in_context() -> None:
    """`D90` part 1's core repro shape: a continuation turn with a pending slot. The
    classifier must be told which slot is currently being elicited -- that signal did not
    reach it at all before this fix.
    """
    fake = FakeBedrockConverseClient(responses=[_classification_response()])
    node = make_route_and_classify_node(caller=fake)

    state: AgentState = {
        "turn_input": "12345",
        "active_slot": "policy_number",
        "filled_slots": {},
    }
    node(state)

    sent_text = fake.calls[0]["messages"][0]["content"][0]["text"]
    assert "policy_number" in sent_text
    assert "12345" in sent_text


def test_route_and_classify_includes_filled_slots_in_context() -> None:
    """Event 13's exact shape (`RESULTS.md` §33): `entitlement_type`/`policy_number` already
    collected, ambiguous turn text. The classifier must see the already-collected slots --
    they are `RentalTowingEntitlement`'s own slot names, the signal event 13's misroute shows
    is currently missing.
    """
    fake = FakeBedrockConverseClient(responses=[_classification_response()])
    node = make_route_and_classify_node(caller=fake)

    state: AgentState = {
        "turn_input": "am I still covered for a rental car",
        "active_slot": None,
        "filled_slots": {"entitlement_type": "rental", "policy_number": "P-000123"},
    }
    node(state)

    sent_text = fake.calls[0]["messages"][0]["content"][0]["text"]
    assert "entitlement_type" in sent_text
    assert "rental" in sent_text
    assert "policy_number" in sent_text
    assert "P-000123" in sent_text
    assert "am I still covered for a rental car" in sent_text


def test_route_and_classify_still_returns_classification_fields() -> None:
    """The context-enrichment change must not alter what this node returns -- only what it
    sends. Same output contract as before (`safety_flag`, `intent`, `intent_confidence`,
    `coverage_question_type`).
    """
    fake = FakeBedrockConverseClient(
        responses=[
            _classification_response(intent="RentalTowingEntitlement", intent_confidence=0.95)
        ]
    )
    node = make_route_and_classify_node(caller=fake)

    state: AgentState = {
        "turn_input": "am I still covered for a rental car",
        "active_slot": None,
        "filled_slots": {"entitlement_type": "rental", "policy_number": "P-000123"},
    }
    result = node(state)

    assert result["intent"] == "RentalTowingEntitlement"
    assert result["intent_confidence"] == 0.95
    assert result["safety_flag"] is False
    assert "coverage_question_type" in result
