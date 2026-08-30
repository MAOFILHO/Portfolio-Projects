"""Lex V2 codehook — Phase 8 Stage 4.

**What changed from Stage 3, and why these tests changed with it.** Stage 3's `_dispatch()` branched
purely on `invocationSource`: `Delegate` on every `DialogCodeHook`, `Close` on every `FulfillmentCodeHook`,
regardless of anything else in the event. Stage 4's `_dispatch()` drives the conversation itself, via the
real graph -- response shape is now a function of the GRAPH's returned state (`escalation`/`active_slot`),
not of `invocationSource` at all. Concretely: `Delegate` is no longer part of the happy path. It is now
**only** the fail-open response, returned when the graph could not be reached at all and no safety signal
fired on this turn. Every test below that asserted `Delegate` for a routine `DialogCodeHook` turn under
Stage 3 has been re-scoped to say what it actually now tests: either the fail-open path specifically (no
`_get_graph` override installed, so the real one fails on a missing `FNOL_CHECKPOINT_TABLE` env var), or
the new `ElicitSlot`/`Close` happy path (a fake graph installed via `_install_fake_graph`, zero real AWS).

`_install_fake_graph` mirrors `test_graph_integration.py`'s own pattern exactly: `FakeBedrockConverseClient`
for the router, `MockGuardrailClient` (empty ruleset -- never blocks), `MockEmbedder`, and
`build_test_checkpointer` against moto-mocked DynamoDB. Every test that installs it wraps its body in
`mock_aws()`, and nothing in this file ever makes a real network call, per `CLAUDE.md`.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from moto import mock_aws

from fnol_voice_agent.agents.graph import build_graph
from fnol_voice_agent.agents.nodes.repair import GENERIC_REPROMPT
from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_tool_use_response,
)
from fnol_voice_agent.api import lex_codehook

# `D162`/`OI80` rows 1/2 (`PROJECT_STATE.md` exit-criteria table). Does NOT exist yet as of this
# import -- deliberately the first thing this test file fails on, before any test body runs. Per the
# approved shape (Step 0 of this row's own TDD cycle): a hand-maintained constant in `src/` alongside
# `_SLOT_BEARING_INTENTS` (`lex_codehook.py:372-380`), never a runtime import of
# `scripts/verify_slot_legality_mapping.py` -- that module and the `bot.yaml.tftpl` it parses are both
# outside `infra/terraform/stacks/main/lambda.tf:44-54`'s `source_dir = ".../src"` packaging root and
# never reach the deployed Lambda. Criterion 3's lint is what will assert this constant matches the
# tftpl-derived map once it exists; this file does not duplicate that check.
from fnol_voice_agent.api.lex_codehook import _LEGAL_SLOTS_BY_INTENT
from fnol_voice_agent.aws.checkpointer import build_test_checkpointer
from fnol_voice_agent.guardrails.client import MockGuardrailClient
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, MockEmbedder

_ROUTER_MODEL = "us.amazon.nova-micro-v1:0"


def _classification(
    intent: str,
    *,
    safety_flag: bool = False,
    confidence: float = 0.95,
    coverage_question_type: str = "not_applicable",
) -> dict[str, Any]:
    return converse_tool_use_response(
        "classify_turn",
        {
            "safety_flag": safety_flag,
            "intent": intent,
            "intent_confidence": confidence,
            "coverage_question_type": coverage_question_type,
        },
    )


def _install_fake_graph(
    monkeypatch: pytest.MonkeyPatch,
    *,
    by_model: dict[str, Any],
    responses: list[dict[str, Any]] | None = None,
    table_suffix: str = "default",
) -> Any:
    """Builds a real, locally-backed graph and patches `_get_graph` to return it -- the seam
    `lex_codehook.py` was written with exactly this purpose. Must be called inside a `mock_aws()` block
    that stays open for the duration of the test, since `graph.get_state`/`graph.invoke` make real boto3
    calls against the moto-mocked DynamoDB, not just at construction.

    `responses`, when given, scripts the router turn-by-turn (FIFO, one per `.converse()` call) rather
    than by `modelId` -- `FakeBedrockConverseClient`'s queue is consulted before `by_model`
    (`agents/testing/fake_llm.py:58-59`). `D162`/`OI80` row 2's Layer 0 test is the first caller that
    needs this: it drives the SAME model through a scripted low-confidence sequence across several
    turns, which `by_model`'s one-fixed-response-per-model-id shape cannot express. Default `None`
    leaves every existing caller unaffected.
    """
    store = DynamoVectorStore(
        table_name=f"fnol-codehook-test-kb-{table_suffix}", region="us-west-2"
    )
    store.ensure_table()
    embedder = MockEmbedder()
    checkpointer = build_test_checkpointer(f"fnol-codehook-test-checkpoints-{table_suffix}")
    caller = FakeBedrockConverseClient(responses=responses, by_model=by_model)
    graph = build_graph(
        vector_store=store,
        embedder=embedder,
        bedrock_caller=caller,
        guardrail_client=MockGuardrailClient(),
        checkpointer=checkpointer,
    )
    monkeypatch.setattr(lex_codehook, "_get_graph", lambda: graph)
    return graph


def _event(
    invocation_source: str = "DialogCodeHook",
    intent_name: str = "FileAutoClaim",
    slots: dict[str, Any] | None = None,
    session_attributes: dict[str, str] | None = None,
    transcript: str = "I need to file a claim",
) -> dict[str, Any]:
    """A Lex V2 codehook event, shaped as the service actually sends one.

    Field names come from the Lex V2 Lambda input/output reference, not from a repo in the Phase 0 corpus:
    `docs/phase0/MERGE-MATRIX.md` records that the corpus's codehook examples are Lex V1 in two repos and
    partial in the third.
    """
    return {
        "messageVersion": "1.0",
        "invocationSource": invocation_source,
        "inputMode": "Speech",
        "responseContentType": "text/plain; charset=utf-8",
        "sessionId": "861314472834431",
        "inputTranscript": transcript,
        "bot": {
            "id": "ABCDEFGHIJ",
            "name": "fnol-voice-agent",
            "aliasId": "TSTALIASID",
            "aliasName": "TestBotAlias",
            "localeId": "en_US",
            "version": "DRAFT",
        },
        "interpretations": [
            {
                "intent": {
                    "name": intent_name,
                    "slots": slots if slots is not None else {},
                    "state": "InProgress",
                    "confirmationState": "None",
                },
                "nluConfidence": 0.98,
            }
        ],
        "sessionState": {
            "sessionAttributes": session_attributes if session_attributes is not None else {},
            "intent": {
                "name": intent_name,
                "slots": slots if slots is not None else {},
                "state": "InProgress",
                "confirmationState": "None",
            },
            "originatingRequestId": "a1b2c3d4-0000-0000-0000-000000000000",
        },
    }


def _slot(value: str) -> dict[str, Any]:
    """A filled Lex V2 slot. The value the codehook must read is `value.interpretedValue`."""
    return {
        "shape": "Scalar",
        "value": {
            "originalValue": value,
            "interpretedValue": value,
            "resolvedValues": [value],
        },
    }


# ---------------------------------------------------------------------------------------------------
# Wire contract properties that hold regardless of which path a turn takes
# ---------------------------------------------------------------------------------------------------


def test_slot_values_survive_the_round_trip() -> None:
    """A codehook response that returns an intent without its slots erases every value collected so far
    -- this is the single most expensive mistake available in this contract, silent, and presenting to the
    caller as being asked the same question twice. No `_get_graph` override here: the real one fails on a
    missing env var, so this exercises the fail-open path, and the property under test (slots round-trip)
    holds there exactly as it would on the happy path, because `_intent_from` is the one function every
    response shape (`Delegate`/`ElicitSlot`/`Close`) goes through.
    """
    slots = {"policy_number": _slot("PY4821"), "loss_location": _slot("Main and 5th")}

    response = lex_codehook.handler(_event(slots=slots), None)

    returned = response["sessionState"]["intent"]["slots"]
    assert returned["policy_number"]["value"]["interpretedValue"] == "PY4821"
    assert returned["loss_location"]["value"]["interpretedValue"] == "Main and 5th"


def test_session_attributes_survive_the_round_trip() -> None:
    """`ADR-005` keys the checkpointer on the Connect contact id, which arrives as a session attribute."""
    response = lex_codehook.handler(
        _event(session_attributes={"contactId": "11111111-2222-3333-4444-555555555555"}), None
    )

    assert (
        response["sessionState"]["sessionAttributes"]["contactId"]
        == "11111111-2222-3333-4444-555555555555"
    )


def test_a_dialog_hook_response_carries_the_intent_back() -> None:
    """Lex rejects any response that does not name the intent it concerns."""
    response = lex_codehook.handler(_event(intent_name="CheckClaimStatus"), None)

    assert response["sessionState"]["intent"]["name"] == "CheckClaimStatus"


def test_the_response_is_json_serialisable() -> None:
    """The runtime serialises the return value; a non-serialisable value fails after the handler returns,
    where the traceback names the runtime rather than the line that built the object."""
    json.dumps(lex_codehook.handler(_event(), None))


def test_a_malformed_event_still_returns_a_valid_delegate() -> None:
    response = lex_codehook.handler({"invocationSource": "DialogCodeHook"}, None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"
    assert "intent" in response["sessionState"]


def test_a_non_dict_event_delegates_rather_than_raising() -> None:
    response = lex_codehook.handler(None, None)  # type: ignore[arg-type]

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"


# ---------------------------------------------------------------------------------------------------
# The fail-open path -- Stage 3's whole contract, still real in Stage 4 for the case the graph can't run
# ---------------------------------------------------------------------------------------------------


def test_a_turn_that_cannot_reach_the_graph_fails_open_to_delegate() -> None:
    """No `_get_graph` override is installed, so `_build_graph()` runs for real and fails immediately on
    a missing `FNOL_CHECKPOINT_TABLE` env var (never set in this test process) -- deterministic, no
    network involved. No safety signal fired on this benign turn, so the handler fails OPEN.
    """
    response = lex_codehook.handler(_event(transcript="I need to file a claim"), None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"
    assert "messages" not in response


def test_an_unrecognised_invocation_source_is_treated_like_any_other_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`invocationSource` is no longer inspected by `_dispatch` at all in Stage 4 -- this asserts that
    directly, by installing a fake graph and checking a made-up `invocationSource` still gets the real
    `ElicitSlot` response, not a special-cased Delegate."""
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="unrecognised-source",
        )
        response = lex_codehook.handler(
            _event(invocation_source="SomethingNew", session_attributes={"contactId": "c-unrec"}),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "ElicitSlot"


def test_the_handler_still_delegates_on_a_genuinely_unhandled_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-safety exception anywhere in `_dispatch` (not just a missing env var) still fails open."""

    def _boom() -> Any:
        raise RuntimeError("simulated failure unrelated to safety")

    monkeypatch.setattr(lex_codehook, "_get_graph", _boom)

    response = lex_codehook.handler(_event(transcript="checking on my claim"), None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"


# ---------------------------------------------------------------------------------------------------
# The fail-CLOSED half of the split -- what Stage 3's docstring flagged as unexamined and Stage 4 owns
# ---------------------------------------------------------------------------------------------------


def test_a_raw_text_l1_match_escalates_even_when_the_graph_cannot_be_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1 firing bypasses `_get_graph` entirely in the normal path (see `_dispatch`), so this forces the
    failure at the one place that still matters: `handler`'s own pre-computed raw-text check must still
    catch it even if `_dispatch` blows up for a completely unrelated reason before reaching L1's own
    bypass. Proceeding as `Delegate` here -- silently handing an injury-flagged turn back to Lex's own
    slot machine -- is exactly the `C1` breach wearing a resilience argument the Stage 3 docstring named.
    """

    def _boom(_event: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("simulated failure, unrelated to the safety check itself")

    monkeypatch.setattr(lex_codehook, "_dispatch", _boom)

    response = lex_codehook.handler(
        _event(
            transcript="my passenger isn't moving", session_attributes={"contactId": "c-failclosed"}
        ),
        None,
    )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalate"] == "true"
    # `D81` item 4: the whole point of this test's failure mode -- fail-closed and a genuine detection
    # must not be indistinguishable on the wire, which `escalate="true"` alone always was.
    assert response["sessionState"]["sessionAttributes"]["escalation_reason"] == "fail-closed"
    assert "911" in response["messages"][0]["content"]
    # `D90` part 2 / `RESULTS.md` §34, option B: no graph ever ran on this path, so there is nothing to
    # name -- absence is the honest value, not a gap the field failed to fill.
    assert "executed_node_intent" not in response["sessionState"]["sessionAttributes"]


def test_a_raw_text_l3_match_escalates_even_when_the_graph_cannot_be_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_event: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("simulated failure, unrelated to the override check itself")

    monkeypatch.setattr(lex_codehook, "_dispatch", _boom)

    response = lex_codehook.handler(
        _event(transcript="agent", session_attributes={"contactId": "c-failclosed-l3"}), None
    )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert response["sessionState"]["sessionAttributes"]["escalation_reason"] == "fail-closed"
    # The fail-closed script names the system trouble explicitly -- the graph never ran to say anything
    # else, and a caller who just asked for a human should not be told the safety-specific 911 line for
    # a request that was never about injury in the first place.
    assert "911" not in response["messages"][0]["content"]


def test_a_benign_turn_that_cannot_reach_the_graph_still_fails_open_not_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the split, stated as its own test rather than inferred from the delegate tests
    above: no safety signal on this turn at all, so a graph failure must NOT escalate a caller who never
    said anything safety-relevant -- that would be its own kind of wrong turn, a false escalation induced
    by an infrastructure fault rather than by anything the caller said."""

    def _boom(_event: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(lex_codehook, "_dispatch", _boom)

    response = lex_codehook.handler(_event(transcript="I need to update my phone number"), None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"
    assert "messages" not in response


# ---------------------------------------------------------------------------------------------------
# The real happy path -- a fake graph installed, zero real AWS
# ---------------------------------------------------------------------------------------------------


def test_a_fresh_file_auto_claim_turn_elicits_the_first_missing_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="fresh-turn",
        )
        response = lex_codehook.handler(_event(session_attributes={"contactId": "c-fresh"}), None)

    assert response["sessionState"]["dialogAction"]["type"] == "ElicitSlot"
    assert response["sessionState"]["dialogAction"]["slotToElicit"] == "policy_number"
    assert "policy number" in response["messages"][0]["content"].lower()


def test_state_persists_across_two_turns_via_the_real_checkpointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core Stage 4 property: `ADR-005`'s checkpointer, not Lex's own session, is what carries
    `filled_slots` forward. Turn 2 supplies the policy number as a Lex-interpreted slot value; the
    handler must have remembered turn 1 asked for it and merge it in before invoking the graph again.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="multiturn",
        )
        contact = {"contactId": "c-multiturn"}

        r1 = lex_codehook.handler(_event(session_attributes=contact), None)
        assert r1["sessionState"]["dialogAction"]["slotToElicit"] == "policy_number"

        r2 = lex_codehook.handler(
            _event(
                session_attributes=contact,
                slots={"policy_number": _slot("PY1103")},
                transcript="PY1103",
            ),
            None,
        )

    assert r2["sessionState"]["dialogAction"]["type"] == "ElicitSlot"
    assert r2["sessionState"]["dialogAction"]["slotToElicit"] == "insured_vehicle_vin"


def test_file_auto_claim_reaches_fulfilment_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The replacement for Stage 3's two `FulfillmentCodeHook` tests. `invocationSource` is irrelevant now
    (every call below uses the default `DialogCodeHook`) -- what makes this turn `Close` rather than
    `ElicitSlot` is that the GRAPH considers the conversation done, which `D78`'s renames are what make
    reachable through the real Lex slot vocabulary at all.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="full-claim",
        )
        contact = {"contactId": "c-full-claim"}
        turns: list[tuple[str, dict[str, Any]]] = [
            ("I want to file a claim", {}),
            ("my policy number is PY1103", {"policy_number": "PY1103"}),
            ("it's my only car", {"insured_vehicle_vin": "9SYCD4568G1000102"}),
            ("this morning", {"loss_datetime": "2026-08-11"}),
            ("on Rue Principale in Ottawa", {"loss_location": "Rue Principale, Ottawa, ON"}),
            ("comprehensive, a windshield crack", {"loss_type": "Comprehensive"}),
            ("just the windshield", {"damage_description": "Windshield crack"}),
            ("no one else was involved", {"other_party_involved": "No"}),
            ("no police report", {"police_report_filed": "No"}),
            ("I was driving", {"driver_name": "Marc-Andre Tremblay"}),
        ]

        response: dict[str, Any] = {}
        for transcript, new_slots in turns:
            lex_slots = {name: _slot(str(value)) for name, value in new_slots.items()}
            response = lex_codehook.handler(
                _event(session_attributes=contact, slots=lex_slots, transcript=transcript), None
            )
            assert response["sessionState"]["dialogAction"]["type"] == "ElicitSlot", transcript

        # All 11 SLOT-DESIGN.md slots filled -- next turn is the graph's own confirm-then-file step,
        # targeting `confirm_file_claim` (`D78`), which has no real answer yet.
        response = lex_codehook.handler(
            _event(session_attributes=contact, transcript="that's everything"), None
        )
        assert response["sessionState"]["dialogAction"]["slotToElicit"] == "confirm_file_claim"

        response = lex_codehook.handler(
            _event(
                session_attributes=contact,
                slots={"confirm_file_claim": _slot("Yes")},
                transcript="yes",
            ),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["intent"]["state"] == "Fulfilled"
    assert "your claim number is clm-" in response["messages"][0]["content"].lower()


# ---------------------------------------------------------------------------------------------------
# `D84` -- `_elicit_slot()` names the GRAPH's own intent, never Lex's (possibly-disagreeing) echoed one
# ---------------------------------------------------------------------------------------------------

# The exact 5 negatives measured to crash pre-fix (`PROJECT_STATE.md`, `D84` follow-up): Lex's own NLU
# lands on `InjuryEscalation` (zero declared slots) for these negations, while the graph correctly does
# not escalate and asks for `policy_number` -- a slot only `FileAutoClaim`/`UpdateContactInfo` declare.
_D84_KNOWN_CRASHING_NEGATIVES = [
    "nobody was hurt",
    "no injuries at all, just the two cars",
    "there's no blood or anything, it's just the bumper",
    "everyone's fine, we all walked away from it",
    "thankfully nobody was injured",
]


@pytest.mark.parametrize("index,transcript", list(enumerate(_D84_KNOWN_CRASHING_NEGATIVES)))
def test_a_lex_graph_intent_disagreement_elicits_under_the_graphs_intent_not_lexs(
    index: int, transcript: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduces `D84`'s exact crash shape for all 5 known-crashing negatives. Before the fix this built
    `{"name": "InjuryEscalation", ...}` (Lex's own echoed, zero-slot intent) with `slotToElicit:
    "policy_number"` -- an illegal combination live Lex rejected with `ValidationException: The slot to
    elicit is invalid`. After the fix the response names the GRAPH's own intent (`FileAutoClaim`), which
    always legally owns whatever slot the graph asks for, regardless of what Lex's NLU independently
    picked for the same utterance.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix=f"d84-{index}",
        )
        response = lex_codehook.handler(
            _event(
                intent_name="InjuryEscalation",
                slots={},
                transcript=transcript,
                session_attributes={"contactId": f"c-d84-{index}"},
            ),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "ElicitSlot"
    assert response["sessionState"]["dialogAction"]["slotToElicit"] == "policy_number"
    assert response["sessionState"]["intent"]["name"] == "FileAutoClaim"
    assert response["sessionState"].get("sessionAttributes", {}).get("escalate") != "true"


def test_a_disagreement_between_two_ordinary_slot_bearing_intents_also_elicits_under_the_graphs_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not an injury-adjacent case at all -- shows the fix's property holds generally, not only for the
    zero-slot `InjuryEscalation`/`FallbackIntent` shape `D84` happened to be measured against. Lex's own
    NLU landed on `CheckClaimStatus`; the graph classifies `UpdateContactInfo` and asks for its own first
    slot, which is not even a legal slot under Lex's `CheckClaimStatus`.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("UpdateContactInfo")},
            table_suffix="d84-cross-intent",
        )
        response = lex_codehook.handler(
            _event(
                intent_name="CheckClaimStatus",
                transcript="actually I need to update my address",
                session_attributes={"contactId": "c-d84-cross-intent"},
            ),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "ElicitSlot"
    assert response["sessionState"]["dialogAction"]["slotToElicit"] == "policy_number"
    assert response["sessionState"]["intent"]["name"] == "UpdateContactInfo"


def test_elicit_slot_preserves_lexs_slot_values_even_when_it_overrides_the_intent_name() -> None:
    """`_intent_from`'s own docstring warning still applies: only `name` may change, `slots` must still
    round-trip, or a caller's already-given answers vanish on the exact turn this fix touches."""
    event = _event(intent_name="CheckClaimStatus", slots={"policy_number": _slot("PY9001")})
    result = {"intent": "FileAutoClaim", "active_slot": "loss_datetime"}

    response = lex_codehook._elicit_slot(event, result, "loss_datetime", "When did this happen?")

    returned_slots = response["sessionState"]["intent"]["slots"]
    assert returned_slots["policy_number"]["value"]["interpretedValue"] == "PY9001"


def test_elicit_slot_sets_executed_node_intent_agreeing_with_intent_name() -> None:
    """`D90` part 2 / `RESULTS.md` §34, option B. Corroborating here, not corrective -- the `D84` guard
    already makes `intent.name` agree with the graph's own decision on every `ElicitSlot`, so this field
    and `intent.name` are always equal at this point. Set anyway, so a harness reads one field regardless
    of which `dialogAction.type` came back."""
    event = _event(intent_name="CheckClaimStatus")
    result = {"intent": "FileAutoClaim", "active_slot": "loss_datetime"}

    response = lex_codehook._elicit_slot(event, result, "loss_datetime", "When did this happen?")

    assert response["sessionState"]["intent"]["name"] == "FileAutoClaim"
    assert response["sessionState"]["sessionAttributes"]["executed_node_intent"] == "FileAutoClaim"


def test_close_carries_executed_node_intent_on_an_ordinary_fulfillment() -> None:
    """`D90` part 2's exact repro shape (`RESULTS.md` §34 §1): Lex's own echoed intent
    (`RentalTowingEntitlement`) disagrees with the intent the graph actually routed to and produced
    `response_text` from (`CheckClaimStatus`). `intent.name` stays Lex's echo, unchanged -- option A (not
    built this entry) is the separate fix that would change it. `executed_node_intent` is the new,
    independent ground-truth signal this entry adds.
    """
    event = _event(intent_name="RentalTowingEntitlement")
    result = {
        "intent": "CheckClaimStatus",
        "response_text": "Your claim CLM-2608-00055-6 is currently UnderReview.",
        "active_slot": None,
        "escalation": None,
    }

    response = lex_codehook._respond_from_graph_result(event, result)

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["intent"]["name"] == "RentalTowingEntitlement"
    assert (
        response["sessionState"]["sessionAttributes"]["executed_node_intent"] == "CheckClaimStatus"
    )


def test_close_executed_node_intent_agrees_with_intent_name_when_routing_agrees() -> None:
    """The non-misrouted case -- both fields say the same thing, as they should whenever the graph's
    classification actually matches what Lex's NLU (and thus `intent.name`) already thought was in
    progress."""
    event = _event(intent_name="CheckClaimStatus")
    result = {
        "intent": "CheckClaimStatus",
        "response_text": "Your claim CLM-1103-00001-1 is currently Open.",
        "active_slot": None,
        "escalation": None,
    }

    response = lex_codehook._respond_from_graph_result(event, result)

    assert response["sessionState"]["intent"]["name"] == "CheckClaimStatus"
    assert (
        response["sessionState"]["sessionAttributes"]["executed_node_intent"] == "CheckClaimStatus"
    )


def test_executed_node_intent_is_absent_on_an_escalation_close() -> None:
    """No reliable per-node signal exists on the escalation path -- `injury_escalation` (`agents/nodes/
    injury_escalation.py`) never sets `state["intent"]` at all, so a leftover classification from before
    it preempted the turn would name the wrong thing, not merely an absent one. Absence is the honest
    value here, not a gap `_close()` failed to fill."""
    event = _event(intent_name="FileAutoClaim")
    result = {
        "escalation": {"contact_id": "c-d90-escalation", "triggering_layer": "L2", "route": 1},
        "response_text": "connecting you now",
        "intent": "FileAutoClaim",  # leftover from classification, before injury_escalation preempted it
        "active_slot": None,
    }

    response = lex_codehook._respond_from_graph_result(event, result)

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert "executed_node_intent" not in response["sessionState"]["sessionAttributes"]


def test_close_refuses_the_escalation_path_regardless_of_which_intent_the_graph_named() -> None:
    """Sanity check on condition 1's structural claim, from the test side rather than only the source
    read: `_respond_from_graph_result`'s escalation branch must never reach `_elicit_slot` (and therefore
    never run the `D84` guard at all), no matter what `result["intent"]` holds -- including a value that
    would fail the guard outright. If this ever regressed to reach `_elicit_slot` first, this test would
    raise `_UnroutableIntentError` instead of asserting the escalation shape below."""
    event = _event(intent_name="FileAutoClaim")
    result = {
        "escalation": {"contact_id": "c-d84-close", "triggering_layer": "L2", "route": 1},
        "response_text": "connecting you now",
        "intent": "Ambiguous",  # would fail `_elicit_slot`'s guard -- must never be reached
        "active_slot": "policy_number",  # would also route to `_elicit_slot` if escalation were ignored
    }

    response = lex_codehook._respond_from_graph_result(event, result)

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalation_reason"] == "detection-graph"


# ---------------------------------------------------------------------------------------------------
# `D84` -- the fail-loud guard on a missing/malformed/non-slot-bearing graph intent
# ---------------------------------------------------------------------------------------------------


def test_a_missing_graph_intent_with_an_active_slot_raises_rather_than_echoing_lex() -> None:
    """`result` with no `"intent"` key at all -- the defensive case, not assumed unreachable just because
    the graph is structurally expected to always set it before `active_slot` can be truthy."""
    event = _event(intent_name="FileAutoClaim")
    result = {"active_slot": "policy_number", "response_text": "What's your policy number?"}

    with pytest.raises(lex_codehook._UnroutableIntentError):
        lex_codehook._elicit_slot(event, result, "policy_number", "unused")


@pytest.mark.parametrize(
    "bad_intent",
    [
        None,
        "",
        "not-a-real-intent",
        "Ambiguous",  # a valid `Intent` member, but never a real Lex intent name
        "OutOfScope",  # same
        "InjuryEscalation",  # a real Lex intent, but declares zero slots
        "FallbackIntent",  # a real Lex intent, but not even a member of `Intent`
    ],
    ids=[
        "none",
        "empty-string",
        "garbage",
        "ambiguous-classifier-label",
        "out-of-scope-classifier-label",
        "injury-escalation-zero-slots",
        "fallback-intent-not-an-intent-member",
    ],
)
def test_a_malformed_or_non_slot_bearing_graph_intent_raises_rather_than_echoing_lex(
    bad_intent: str | None,
) -> None:
    """Covers `D84`'s follow-up finding directly: `handle_no_match_or_barge_in` can leave a carried-over
    `active_slot` in place while this turn's `intent` is `Ambiguous`/`OutOfScope` -- valid `Intent` members,
    neither a real Lex intent name. Every case here must fail loudly, never fall back to Lex's own echoed
    intent (`_intent_from(event)`), which is the exact condition-2 requirement this guard exists to meet.
    """
    event = _event(intent_name="FileAutoClaim")
    result = {"intent": bad_intent, "active_slot": "policy_number", "response_text": "..."}

    with pytest.raises(lex_codehook._UnroutableIntentError):
        lex_codehook._elicit_slot(event, result, "policy_number", "unused")


def test_a_malformed_graph_intent_fails_open_to_delegate_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proves the guard's exception actually reaches a fail-open `Delegate` end-to-end, not only that
    `_elicit_slot` raises in isolation -- and critically must NOT return `ElicitSlot` built from Lex's own
    echoed intent, which is the exact `D84` shape this guard exists to keep from reappearing silently.

    **Amended by `D202`/`OI120`**: this scenario is now caught inside `_respond_from_graph_result` (not
    `handler`'s blanket except -- see `_UnroutableIntentError`'s own docstring), and the fail-open
    `Delegate` it falls to now carries `response_text` as a `messages` array rather than silently dropping
    it. This test keeps asserting the `Delegate`-not-`ElicitSlot` shape `D84` cares about; the message
    itself is `test_d202_oi120_...`'s job, directly below.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="d84-malformed-e2e",
        )
        monkeypatch.setattr(
            lex_codehook,
            "_run_graph_turn",
            lambda *a, **k: {
                "active_slot": "policy_number",
                "response_text": "What's your policy number?",
                "intent": "Ambiguous",
            },
        )
        response = lex_codehook.handler(
            _event(
                intent_name="FileAutoClaim",
                transcript="I need to update my phone number",
                session_attributes={"contactId": "c-d84-malformed-e2e"},
            ),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"


def test_d202_oi120_ambiguous_turn_with_stale_active_slot_delivers_response_text_and_holds_the_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`D202`/`OI120` (`PROJECT_STATE.md`). Same raise shape as the `D84` test above (`Ambiguous`
    colliding with a stale `active_slot="policy_number"`), but this test is about what the CALLER hears
    once the guard raises, not just that it raises (that part is already covered). Before this fix,
    `handler`'s blanket `except Exception` catches `_UnroutableIntentError` and falls to bare
    `_delegate(event)`, which carries no `messages` key at all -- the real, already-computed
    `GENERIC_REPROMPT` from `handle_no_match_or_barge_in` is silently discarded, and the caller hears
    nothing this codehook decided to say. Real repro this test reflects: contact
    `157916fe-a33b-48de-ab2b-13e5950cd745`, `"i don't have it handy now"` mid-`FileAutoClaim`'s
    `policy_number` elicitation.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="d202-oi120",
        )
        monkeypatch.setattr(
            lex_codehook,
            "_run_graph_turn",
            lambda *a, **k: {
                "active_slot": "policy_number",
                "response_text": GENERIC_REPROMPT,
                "intent": "Ambiguous",
            },
        )
        response = lex_codehook.handler(
            _event(
                intent_name="FileAutoClaim",
                transcript="i don't have it handy now",
                session_attributes={"contactId": "c-d202-oi120"},
            ),
            None,
        )

    # (a) the caller hears the graph's real answer -- not silence, not a fabricated generic fallback.
    assert response["messages"] == [{"contentType": "PlainText", "content": GENERIC_REPROMPT}]

    # (b) Lex's dialog state does not advance past policy_number -- checked directly on the wire shape,
    # not inferred: not Close/Fulfilled (which would end the intent), and the echoed intent's own
    # policy_number slot is still unfilled, so Lex's own dialog manager keeps trying to fill it.
    assert response["sessionState"]["dialogAction"]["type"] != "Close"
    assert response["sessionState"]["intent"]["state"] != "Fulfilled"
    assert response["sessionState"]["intent"]["slots"].get("policy_number") is None


def test_d202_oi120_same_guard_with_no_response_text_delivers_the_generic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same `D202`/`OI120` raise shape as the test above, but `result["response_text"]` is absent this
    time. `_respond_from_graph_result`'s own fallback line runs unconditionally, BEFORE the `active_slot`
    branch even looks at it: `response_text = result.get("response_text") or ("I'm sorry, ...")`. So the
    text handed into the `except _UnroutableIntentError` catch, and on to `_delegate`, is already that
    fallback string by the time the catch runs -- the catch itself has no separate branch for "was there a
    real answer." Proves the fix is generic to WHAT `response_text` is, not special-cased to the
    `GENERIC_REPROMPT` value the test above happens to use.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="d202-oi120-no-response-text",
        )
        monkeypatch.setattr(
            lex_codehook,
            "_run_graph_turn",
            lambda *a, **k: {
                "active_slot": "policy_number",
                "intent": "Ambiguous",
                # no "response_text" key at all -- result.get("response_text") returns None, falsy.
            },
        )
        response = lex_codehook.handler(
            _event(
                intent_name="FileAutoClaim",
                transcript="i don't have it handy now",
                session_attributes={"contactId": "c-d202-oi120-no-response-text"},
            ),
            None,
        )

    # the caller hears the fallback text, not silence and not an unhandled exception reaching the caller.
    assert response["messages"] == [
        {
            "contentType": "PlainText",
            "content": lex_codehook._GRAPH_RESULT_MISSING_RESPONSE_TEXT_SCRIPT,
        }
    ]
    assert response["sessionState"]["dialogAction"]["type"] != "Close"


# ---------------------------------------------------------------------------------------------------
# `D162`/`OI80` rows 1/2 -- `_elicit_slot` raising on an illegal `slot_name` (row 2) and filtering
# `lex_slots` to `graph_intent`'s legal set (row 1), both against `_LEGAL_SLOTS_BY_INTENT`. RED-first:
# no implementation exists yet. Both use `CoverageQuestion`'s single-slot set (`{"coverage_topic"}`) and
# `FileAutoClaim`'s/`UpdateContactInfo`'s larger sets as the legal/illegal contrast, matching the exact
# `repair.py:43-72` stale-`active_slot` trigger row 2 exists to close: `handle_no_match_or_barge_in`
# never clears `active_slot`, so a slot legal under a PRIOR intent can survive into a turn the graph has
# freshly, validly classified under a different, unrelated intent.
# ---------------------------------------------------------------------------------------------------


def test_an_illegal_slot_name_for_the_graph_intent_raises() -> None:
    """`policy_number` is legal for `FileAutoClaim`/`UpdateContactInfo` but not `CoverageQuestion` --
    a stale `active_slot` left over from a prior intent, surviving into a turn the graph has freshly
    classified as `CoverageQuestion`. Must raise, not silently elicit a combination Lex's own dialog
    manager would reject with `DependencyFailedException`.
    """
    assert "policy_number" not in _LEGAL_SLOTS_BY_INTENT["CoverageQuestion"]
    event = _event(intent_name="CoverageQuestion")
    result = {
        "intent": "CoverageQuestion"
    }  # no "active_slot" -- _elicit_slot never reads it (:383-431)

    with pytest.raises(lex_codehook._UnroutableIntentError):
        lex_codehook._elicit_slot(event, result, "policy_number", "unused")


def test_an_illegal_slot_name_yields_no_response_regardless_of_lex_slots_filterability() -> None:
    """NOT an ordering claim between row 2's raise and row 1's filter -- whether the implementation
    checks legality before or after building a filtered `lex_slots` map is an internal detail with no
    caller-visible difference (both orderings produce the same observable outcome: no response, an
    exception instead), and this test does not and cannot distinguish them. What it does pin: an illegal
    `slot_name` yields no response at all, even when `lex_slots` itself is filterable (carries a legal
    key for the intent in scope) rather than trivially all-illegal -- a filter-only implementation that
    silently degraded the raise to "filter and return" on this input would fail this test.
    """
    assert "policy_number" not in _LEGAL_SLOTS_BY_INTENT["CoverageQuestion"]
    event = _event(
        intent_name="UpdateContactInfo",
        slots={
            "field": _slot("phone"),
            "new_value": _slot("555-0100"),
            "policy_number": _slot("PY9001"),
        },
    )
    result = {
        "intent": "CoverageQuestion"
    }  # no "active_slot" -- _elicit_slot never reads it (:383-431)

    with pytest.raises(lex_codehook._UnroutableIntentError):
        lex_codehook._elicit_slot(event, result, "policy_number", "unused")


def test_the_illegal_slot_name_error_message_embeds_slot_name_and_graph_intent() -> None:
    """Row 4's raised-turn evidence on the live 6-turn run is this exception's own traceback and nothing
    else -- `_log_turn_observability` never runs on the raise path (it fires at `lex_codehook.py:651-652`,
    after the `active_slot`/`_elicit_slot` branch; a raise there exits before that line is reached, caught
    only by `handler`'s blanket `except Exception` and `logger.exception("codehook failed")` at `:765`).

    Event intent (`UpdateContactInfo`) and graph intent (`result["intent"]`, `CoverageQuestion`) are
    deliberately DIFFERENT here -- with them equal, an assertion that the message contains
    "CoverageQuestion" cannot tell whether the implementation embedded the graph's own intent or simply
    echoed Lex's. Row 4's evidence needs the REJECTING (graph) intent specifically, not whatever Lex
    happened to send that turn, so this test can only prove the right thing when the two differ. Message
    format otherwise matches the existing 3-part guard's own convention (`lex_codehook.py:400-402`/
    `:406-408`/`:410-412`, each embedding `slot_name`/`active_slot` alongside the intent value).
    """
    event = _event(intent_name="UpdateContactInfo")
    result = {
        "intent": "CoverageQuestion"
    }  # no "active_slot" -- _elicit_slot never reads it (:383-431)
    assert "policy_number" not in _LEGAL_SLOTS_BY_INTENT["CoverageQuestion"]

    with pytest.raises(lex_codehook._UnroutableIntentError) as exc_info:
        lex_codehook._elicit_slot(event, result, "policy_number", "unused")

    message = str(exc_info.value)
    assert "policy_number" in message
    assert "CoverageQuestion" in message


def test_check_claim_status_own_internal_slot_name_is_legal_and_does_not_raise() -> None:
    """`D200`/`OI118`. `claim_or_policy_number` is `check_claim_status.py:19`'s own graph-internal
    disambiguation slot -- it names it as `active_slot` when neither `claim_number` nor `policy_number`
    is filled yet (`check_claim_status.py:28-31`), but it was never a Lex-declared slot name
    (`bot.yaml.tftpl`'s `CheckClaimStatus` block only ever declared `claim_number`, `:516`). Row 2's own
    guard, added for the OI80 stale-`active_slot` case, had no way to know this name existed -- it went
    live for the first time on the 2026-08-29 deploy and raised `_UnroutableIntentError` on the very
    first turn of a real `CheckClaimStatus` call, confirmed via CloudWatch. This is the correctness case
    row 2's own guard must NOT reject: a slot the graph legitimately elicits under the SAME intent it's
    asking about, not a stale leftover from a prior one.
    """
    event = _event(intent_name="CheckClaimStatus")
    result = {"intent": "CheckClaimStatus"}

    response = lex_codehook._elicit_slot(event, result, "claim_or_policy_number", "unused")

    assert response["sessionState"]["dialogAction"]["slotToElicit"] == "claim_or_policy_number"


def test_lex_slots_are_filtered_to_the_graph_intents_legal_set() -> None:
    """Row 1's own trigger: the router-drift shape (`OI80`'s live turn-1->2 observation) -- Lex still
    carries `UpdateContactInfo`'s slot keys from a prior turn while the graph has moved to
    `FileAutoClaim`. The response's `intent.slots` keys must be a subset of
    `_LEGAL_SLOTS_BY_INTENT["FileAutoClaim"]` -- asserted against the constant itself, never a literal
    slot name, so this test does not silently pass if the constant's own contents drift.
    """
    lex_slots = {
        "field": _slot("phone"),
        "new_value": _slot("555-0100"),
        "confirm_update_contact_info": _slot("Yes"),
        "policy_number": _slot("PY9001"),  # legal for FileAutoClaim too -- ambiguous by design
    }
    event = _event(intent_name="UpdateContactInfo", slots=lex_slots)
    result = {
        "intent": "FileAutoClaim"
    }  # no "active_slot" -- _elicit_slot never reads it (:383-431)

    response = lex_codehook._elicit_slot(event, result, "loss_datetime", "When did this happen?")

    returned_keys = set(response["sessionState"]["intent"]["slots"].keys())
    assert returned_keys <= _LEGAL_SLOTS_BY_INTENT["FileAutoClaim"]


def test_every_lex_slot_illegal_for_the_graph_intent_filters_to_an_empty_dict() -> None:
    """Shape-only assertion. Whether Lex's own dialog manager ACCEPTS an `ElicitSlot` response whose
    `intent.slots` is `{}` is a live question this unit test cannot answer -- it exercises this
    function's own return value, not a real Lex turn. Row 4's live 6-turn run is where that question
    gets an actual answer, not here.
    """
    lex_slots = {
        "field": _slot("phone"),
        "new_value": _slot("555-0100"),
        "confirm_update_contact_info": _slot("Yes"),
    }
    assert not (set(lex_slots) & _LEGAL_SLOTS_BY_INTENT["CoverageQuestion"])
    event = _event(intent_name="UpdateContactInfo", slots=lex_slots)
    result = {
        "intent": "CoverageQuestion"
    }  # no "active_slot" -- _elicit_slot never reads it (:383-431)

    response = lex_codehook._elicit_slot(event, result, "coverage_topic", "What coverage question?")

    assert response["sessionState"]["intent"]["slots"] == {}
    assert response["sessionState"]["dialogAction"]["type"] == "ElicitSlot"
    assert response["sessionState"]["dialogAction"]["slotToElicit"] == "coverage_topic"


def test_row2_layer0_branch_i_ceiling_reached_via_a_stale_active_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`D162`/`OI80` row 2's own closing condition, Layer 0 half: an in-process test proving the
    branch-(i) retry-ceiling chain end to end -- a stale `active_slot` surviving from
    `UpdateContactInfo` into two consecutive turns the graph freshly, validly classifies as
    `FileAutoClaim` at low confidence.

    Deliberately NOT the `Ambiguous`/low-confidence shape `test_graph_integration.py`'s own
    `test_retry_ceiling_reached_via_mixed_normal_and_barge_in_triggers` already covers -- that shape
    (`state["intent"] == "Ambiguous"`) trips `_elicit_slot`'s PRE-EXISTING check 3 ("declares no Lex
    slots"), never row 2's new check 4. `route_and_classify` (`agents/nodes/routing.py:52-57`) writes
    `intent` into state unconditionally, regardless of confidence -- a low-confidence turn that names a
    real, slot-bearing intent (`FileAutoClaim` @ 0.3) still routes to repair (`graph.py:145`,
    `confidence < LOW_CONFIDENCE_THRESHOLD`) while leaving `state["intent"] == "FileAutoClaim"`, which
    is exactly the shape check 4 exists for. Copying the `Ambiguous` precedent here would have passed
    while testing the wrong guard entirely -- the same `D126` shape (a check that exists, finds
    nothing, and reads as clean), one level up.

    Turn-by-turn, one session:
      1: fresh `UpdateContactInfo` turn -> elicits `policy_number`.
      2: answers `policy_number` -> elicits `field`; `active_slot="field"` checkpointed.
      3: drift turn 1, `FileAutoClaim` @ 0.3 -- the stale `active_slot="field"` is illegal under
         `FileAutoClaim` (check 4) -> `_elicit_slot` raises -> `handler` fails open -> silent
         `Delegate`. `retry_counts["field"]` reaches 1 (`repair.py:44` keys the ladder on the SAME
         stale slot the raise flags) and is checkpointed BEFORE the raise -- `graph.invoke()` commits
         internally; the raise happens one call up the stack, in `_respond_from_graph_result`.
      4: drift turn 2, same shape -- `retry_counts["field"]` reaches `RETRY_CEILING` (2) ->
         `ceiling_reached` fires -> repair returns an `escalation` record, route 3 -> `Close`,
         `escalated=True`, `escalation_reason="detection-graph"`. `_elicit_slot` is NEVER called this
         turn: `_respond_from_graph_result` checks `escalation` before the `active_slot` branch
         (`lex_codehook.py:670-671` precedes `:688-689`) -- the load-bearing assertion below.
    """
    real_elicit_slot = lex_codehook._elicit_slot
    elicit_slot_calls: list[Any] = []

    def _spy_elicit_slot(*args: Any, **kwargs: Any) -> dict[str, Any]:
        elicit_slot_calls.append((args, kwargs))
        return real_elicit_slot(*args, **kwargs)

    monkeypatch.setattr(lex_codehook, "_elicit_slot", _spy_elicit_slot)

    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={},  # unused: every call this test drives is scripted via `responses` below
            responses=[
                _classification("UpdateContactInfo"),
                _classification("UpdateContactInfo"),
                _classification("FileAutoClaim", confidence=0.3),
                _classification("FileAutoClaim", confidence=0.3),
            ],
            table_suffix="row2-layer0",
        )
        contact = {"contactId": "c-row2-layer0"}

        r1 = lex_codehook.handler(
            _event(intent_name="UpdateContactInfo", session_attributes=contact), None
        )
        assert r1["sessionState"]["dialogAction"]["slotToElicit"] == "policy_number"
        assert len(elicit_slot_calls) == 1

        r2 = lex_codehook.handler(
            _event(
                intent_name="UpdateContactInfo",
                session_attributes=contact,
                slots={"policy_number": _slot("PY1103")},
                transcript="PY1103",
            ),
            None,
        )
        assert r2["sessionState"]["dialogAction"]["slotToElicit"] == "field"
        assert len(elicit_slot_calls) == 2

        r3 = lex_codehook.handler(
            _event(
                intent_name="UpdateContactInfo",
                session_attributes=contact,
                transcript="actually, never mind, tell me about my rental coverage",
            ),
            None,
        )
        assert r3["sessionState"]["dialogAction"]["type"] == "Delegate"
        assert len(elicit_slot_calls) == 3  # called this turn, and it raised

        r4 = lex_codehook.handler(
            _event(
                intent_name="UpdateContactInfo",
                session_attributes=contact,
                transcript="hello? is anyone there",
            ),
            None,
        )

    assert r4["sessionState"]["dialogAction"]["type"] == "Close"
    assert r4["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert r4["sessionState"]["sessionAttributes"]["escalation_reason"] == "detection-graph"
    # The load-bearing assertion: unchanged from turn 3 -- `_elicit_slot` was never called this turn.
    assert len(elicit_slot_calls) == 3


# ---------------------------------------------------------------------------------------------------
# L1 -- deterministic, pre-graph, no AWS at all
# ---------------------------------------------------------------------------------------------------


def test_l1_fires_without_any_graph_installed() -> None:
    """No `_get_graph` override anywhere in this test -- if L1's raw-text match required the graph or the
    checkpointer, this would fail on the same missing env var `test_a_turn_that_cannot_reach_the_graph_
    fails_open_to_delegate` exercises deliberately. It must not: L1 is the one path in this handler with
    zero AWS dependency, by design."""
    response = lex_codehook.handler(
        _event(transcript="my passenger isn't moving", session_attributes={"contactId": "c-l1"}),
        None,
    )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert (
        response["sessionState"]["sessionAttributes"]["escalation_reason"] == "detection-pregraph"
    )
    assert "911" in response["messages"][0]["content"]


def test_l1_takes_priority_over_l3_when_both_language_forms_are_present() -> None:
    """`INTENT-TAXONOMY.md` §1's own canonical example carries both L1 and L3 language. `DIALOGUE-POLICIES.
    md` §8 lists route 1 (safety) above route 2 (caller request) -- this asserts the codehook actually
    honours that ordering rather than reporting whichever check happens to run first in the source.
    """
    response = lex_codehook.handler(
        _event(transcript="I want to talk to a real person, someone's hurt"), None
    )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert "911" in response["messages"][0]["content"]


# ---------------------------------------------------------------------------------------------------
# L3 -- the "agent"/"human" override, D74
# ---------------------------------------------------------------------------------------------------


def test_l3_escalates_on_a_bare_override_word(monkeypatch: pytest.MonkeyPatch) -> None:
    """`D74`: mid-slot-elicitation, "agent" is a Lex no-match against whatever slot type is active, not an
    intent switch -- this simulates exactly that shape, a `FileAutoClaim` DialogCodeHook turn whose
    transcript is the bare override word. A fake graph IS installed here (unlike the L1 test) because L3
    firing correctly does not depend on bypassing the graph the way L1 does -- it depends on firing before
    the graph is asked to classify anything, which this test would catch if it regressed: `_classification`
    below is scripted to return `FileAutoClaim` for anything, so a wrongly-reached graph call would not
    produce this escalation."""
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="l3-bare",
        )
        response = lex_codehook.handler(
            _event(transcript="agent", session_attributes={"contactId": "c-l3"}), None
        )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert (
        response["sessionState"]["sessionAttributes"]["escalation_reason"] == "detection-pregraph"
    )


def test_l3_does_not_fire_on_an_ordinary_mention_of_the_callers_own_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("CheckClaimStatus")},
            table_suffix="l3-non-override",
        )
        response = lex_codehook.handler(
            _event(
                intent_name="CheckClaimStatus",
                transcript="my agent told me to call this number",
                session_attributes={"contactId": "c-l3-non"},
            ),
            None,
        )

    assert response["sessionState"].get("sessionAttributes", {}).get("escalate") != "true"


# ---------------------------------------------------------------------------------------------------
# `D79` -- injuries_present confirmed True, no injury vocabulary in the raw text at all
# ---------------------------------------------------------------------------------------------------


def test_injuries_present_confirmed_true_escalates_even_with_no_injury_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact gap `D79` names: the caller's raw answer is a single word with no injury vocabulary at
    all, so `detect_safety_trigger` alone would never fire. Only the confirmed slot value tells the truth.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="d79",
        )
        response = lex_codehook.handler(
            _event(
                transcript="yes",
                slots={"injuries_present": _slot("Yes")},
                session_attributes={"contactId": "c-d79"},
            ),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert (
        response["sessionState"]["sessionAttributes"]["escalation_reason"] == "detection-pregraph"
    )
    assert "911" in response["messages"][0]["content"]


def test_injuries_present_confirmed_false_does_not_escalate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim")},
            table_suffix="d79-negative",
        )
        response = lex_codehook.handler(
            _event(
                transcript="no",
                slots={"injuries_present": _slot("No")},
                session_attributes={"contactId": "c-d79-neg"},
            ),
            None,
        )

    assert response["sessionState"].get("sessionAttributes", {}).get("escalate") != "true"


# ---------------------------------------------------------------------------------------------------
# `D81` item 4 — escalation provenance, including the path that used to have none at all
# ---------------------------------------------------------------------------------------------------


def test_the_graphs_own_in_band_escalation_carries_detection_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_respond_from_graph_result`'s escalation branch used to call `_close(..., escalated=True)`
    directly, with no log line and no reason code -- the least observable of the three escalation paths,
    per `D81`'s expanded entry. This drives an escalation through the GRAPH's own `L2` safety-flag route
    (`agents/nodes/routing.py` -> `injury_escalation`), not any of the pre-graph L1/L3/`D79` checks, which
    never reach this branch at all: the transcript below matches none of `agents/lexicon.py`'s or
    `agents/l3_lexicon.py`'s raw-text patterns, so only the classifier's own `safety_flag=True` can be
    what escalates this turn.
    """
    with mock_aws():
        _install_fake_graph(
            monkeypatch,
            by_model={_ROUTER_MODEL: _classification("FileAutoClaim", safety_flag=True)},
            table_suffix="graph-escalation",
        )
        response = lex_codehook.handler(
            _event(
                transcript="the airbags went off and everything is chaos",
                session_attributes={"contactId": "c-graph-escalation"},
            ),
            None,
        )

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["sessionAttributes"]["escalate"] == "true"
    assert response["sessionState"]["sessionAttributes"]["escalation_reason"] == "detection-graph"


def test_close_refuses_an_unattributed_escalation() -> None:
    """`D81` item 4's other half: `escalation_reason` is a required argument in substance, not just in
    name. A caller reaching `_close(escalated=True)` with no reason is a bug in this module -- exactly the
    shape that let fail-closed and a genuine detection collapse into the same `escalate="true"` before this
    fix -- so it must fail loudly here rather than silently emit an unattributed escalation."""
    with pytest.raises(ValueError):
        lex_codehook._close(_event(), "unused", escalated=True)


# ---------------------------------------------------------------------------------------------------
# `D162` diagnostic prerequisite -- unconditional per-turn observability logging
# ---------------------------------------------------------------------------------------------------
#
# `graph_intent` (`result["intent"]`, named by `route_and_classify`, `agents/nodes/routing.py:54`) has
# never been observable in CloudWatch for any turn this project has run: this module's only three log
# lines (`:507`/`:566`/`:687`) are each conditional on escalation or an unhandled exception, and neither
# `agents/nodes/routing.py` nor `agents/graph.py` logs anything at all (confirmed by grep, `RESULTS.md`'s
# live-log investigation of `D162`/`OI80`). These three tests drive `_respond_from_graph_result` directly
# -- the same already-established seam `test_close_carries_executed_node_intent_on_an_ordinary_fulfillment`
# and its neighbours use -- and assert a log record exists on the turn shapes that currently produce none.


def test_a_per_turn_log_line_is_emitted_when_graph_intent_agrees_with_lex_intent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The plain, non-escalating, non-crashing case that today logs nothing at all: Lex's echoed intent
    and the graph's own classification agree, the turn reaches `_close`'s default (non-escalated) branch.
    """
    event = _event(intent_name="CheckClaimStatus", slots={"policy_number": _slot("PY1234")})
    result = {
        "intent": "CheckClaimStatus",
        "response_text": "Your claim CLM-1103-00001-1 is currently Open.",
        "active_slot": None,
        "escalation": None,
    }

    with caplog.at_level("INFO", logger="fnol_voice_agent.api.lex_codehook"):
        lex_codehook._respond_from_graph_result(event, result)

    turn_records = [r for r in caplog.records if r.message.startswith("turn ")]
    assert len(turn_records) == 1, "expected exactly one unconditional per-turn log line"
    message = turn_records[0].message
    assert "lex_intent=CheckClaimStatus" in message
    assert "graph_intent=CheckClaimStatus" in message
    assert "outgoing_intent=CheckClaimStatus" in message
    assert "policy_number" in message  # a slot KEY, present on both sides
    assert "PY1234" not in message, "slot VALUES must never reach this log line"


def test_a_per_turn_log_line_is_emitted_and_names_both_intents_when_they_disagree(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The `D84` disagreement shape: Lex's own NLU landed on `CheckClaimStatus`, the graph classifies
    `FileAutoClaim` and asks for its own first slot. The log line must name BOTH values, not just one --
    that is the entire point of `D163`'s finding that `escalation_reason` alone cannot do this."""
    event = _event(intent_name="CheckClaimStatus", slots={"policy_number": _slot("PY9001")})
    result = {"intent": "FileAutoClaim", "active_slot": "loss_datetime", "escalation": None}

    with caplog.at_level("INFO", logger="fnol_voice_agent.api.lex_codehook"):
        lex_codehook._respond_from_graph_result(event, result)

    turn_records = [r for r in caplog.records if r.message.startswith("turn ")]
    assert len(turn_records) == 1
    message = turn_records[0].message
    assert "lex_intent=CheckClaimStatus" in message
    assert "graph_intent=FileAutoClaim" in message
    assert "outgoing_intent=FileAutoClaim" in message
    assert "PY9001" not in message


def test_an_escalating_turn_logs_both_its_own_escalation_line_and_the_per_turn_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The new unconditional line is additional to, not a replacement for, the existing `:566` escalation
    line -- an escalating turn must produce both, so a CloudWatch query over either one still finds it.
    """
    event = _event(intent_name="FileAutoClaim")
    result = {
        "escalation": {"contact_id": "c-d162-escalation", "triggering_layer": "L2", "route": 1},
        "response_text": "connecting you now",
        "intent": "FileAutoClaim",
        "active_slot": None,
    }

    with caplog.at_level("INFO", logger="fnol_voice_agent.api.lex_codehook"):
        lex_codehook._respond_from_graph_result(event, result)

    escalation_records = [r for r in caplog.records if r.message.startswith("escalating contact")]
    turn_records = [r for r in caplog.records if r.message.startswith("turn ")]
    assert len(escalation_records) == 1, "the existing :566 line must still fire, unchanged"
    assert len(turn_records) == 1, "the new unconditional line must ALSO fire on an escalating turn"
    assert "graph_intent=FileAutoClaim" in turn_records[0].message


def test_a_raising_observability_log_does_not_replace_an_escalation_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Row 9's no-accept-risk rule for escalation delivery, applied to the diagnostic added for `D162`:
    `_log_turn_observability` raising must never cost the caller an already-built `EscalationRecord`'s
    response. If this call site were unguarded, the exception would propagate out of
    `_respond_from_graph_result`, past `_dispatch`, into `handler`'s `except Exception` block, and the
    caller would get the fail-closed escalation instead of the one actually computed here -- silently
    replacing a real route/reason with a different one, for no reason connected to the escalation itself.
    """
    monkeypatch.setattr(
        lex_codehook,
        "_log_turn_observability",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    event = _event(intent_name="FileAutoClaim")
    result = {
        "escalation": {
            "contact_id": "c-observability-failure",
            "triggering_layer": "L2",
            "route": 1,
        },
        "response_text": "connecting you now",
        "intent": "FileAutoClaim",
        "active_slot": None,
    }

    response = lex_codehook._respond_from_graph_result(event, result)

    session_attributes = response["sessionState"]["sessionAttributes"]
    assert session_attributes["escalate"] == "true"
    assert session_attributes["escalation_reason"] == "detection-graph"


# ---------------------------------------------------------------------------------------------------
# `ADR-009` — the properties that make a cold start cheap, asserted rather than intended
# ---------------------------------------------------------------------------------------------------


def test_importing_the_module_constructs_no_boto3_client() -> None:
    """A module-level `boto3.client(...)` costs an SDK import plus credential resolution on every cold
    start and makes SnapStart restore a snapshot holding a stale credential."""
    source = Path(lex_codehook.__file__).read_text(encoding="utf-8")
    module_level = [
        line
        for line in source.splitlines()
        if line and not line[0].isspace() and "boto3." in line and not line.startswith("#")
    ]

    assert module_level == [], f"module-level boto3 usage: {module_level}"


def test_the_module_imports_without_botocore_being_loaded() -> None:
    """The check above reads the source; this one measures the outcome. Run in a subprocess because
    `botocore` is already imported in this test session by other modules."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fnol_voice_agent.api.lex_codehook; "
            "print('botocore' in sys.modules or 'boto3' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )

    assert result.stdout.strip() == "False", result.stdout + result.stderr


def test_the_handler_runs_with_no_aws_credentials_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """`CLAUDE.md`: everything runs locally without AWS. On a benign turn with no fake graph installed,
    the handler must still fail open rather than raise, even with every AWS env var cleared."""
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_REGION",
    ):
        monkeypatch.delenv(var, raising=False)

    importlib.reload(lex_codehook)

    assert (
        lex_codehook.handler(_event(), None)["sessionState"]["dialogAction"]["type"] == "Delegate"
    )
