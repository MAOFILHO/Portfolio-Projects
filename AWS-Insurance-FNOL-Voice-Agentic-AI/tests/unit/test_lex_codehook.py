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
from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_tool_use_response,
)
from fnol_voice_agent.api import lex_codehook
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
    table_suffix: str = "default",
) -> Any:
    """Builds a real, locally-backed graph and patches `_get_graph` to return it -- the seam
    `lex_codehook.py` was written with exactly this purpose. Must be called inside a `mock_aws()` block
    that stays open for the duration of the test, since `graph.get_state`/`graph.invoke` make real boto3
    calls against the moto-mocked DynamoDB, not just at construction.
    """
    store = DynamoVectorStore(
        table_name=f"fnol-codehook-test-kb-{table_suffix}", region="us-west-2"
    )
    store.ensure_table()
    embedder = MockEmbedder()
    checkpointer = build_test_checkpointer(f"fnol-codehook-test-checkpoints-{table_suffix}")
    caller = FakeBedrockConverseClient(by_model=by_model)
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
    assert "911" in response["messages"][0]["content"]


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
