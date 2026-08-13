"""Lex V2 codehook contract — Phase 8 Stage 3.

Written before the handler, per `CLAUDE.md`'s TDD rule for the tool layer.

**What this handler is at Stage 3, stated plainly so it is not over-read.** It implements the Lex V2
`sessionState` contract and nothing above it: `Delegate` on a dialog hook, `Close` on fulfilment. It does
not call the graph, and it does not run L1/L2. Stage 4 replaces `_dispatch()` with the graph invocation
keyed on the Connect `contactId` per `ADR-005`; every test in this file describes the wire contract, which
Stage 4 does not change, so these tests stay valid across that replacement rather than being deleted with
it.

Two of the tests here are about `ADR-009` rather than about dialogue: the module must import without
constructing a boto3 client, and the handler must be reachable without any AWS credential. Those are the
properties that make SnapStart possible later, and they are cheap to assert now and expensive to retrofit.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from fnol_voice_agent.api import lex_codehook


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
# The wire contract
# ---------------------------------------------------------------------------------------------------


def test_a_dialog_hook_delegates_back_to_lex() -> None:
    response = lex_codehook.handler(_event(), None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"


def test_a_dialog_hook_response_carries_the_intent_back() -> None:
    """Lex rejects a `Delegate` that does not name the intent it is delegating."""
    response = lex_codehook.handler(_event(intent_name="CheckClaimStatus"), None)

    assert response["sessionState"]["intent"]["name"] == "CheckClaimStatus"


def test_slot_values_survive_the_round_trip() -> None:
    """A codehook that returns an intent without its slots erases every value collected so far.

    This is the single most expensive mistake available in this contract: it is silent, and it presents
    to the caller as being asked the same question twice.
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


def test_a_fulfilment_hook_closes_the_intent() -> None:
    response = lex_codehook.handler(_event(invocation_source="FulfillmentCodeHook"), None)

    assert response["sessionState"]["dialogAction"]["type"] == "Close"
    assert response["sessionState"]["intent"]["state"] == "Fulfilled"


def test_a_fulfilment_hook_speaks_a_line() -> None:
    """A `Close` with no `messages` ends the call in silence, which reads to a caller as a dropped line."""
    response = lex_codehook.handler(_event(invocation_source="FulfillmentCodeHook"), None)

    messages = response["messages"]
    assert len(messages) >= 1
    assert messages[0]["contentType"] == "PlainText"
    assert messages[0]["content"].strip() != ""


def test_an_unknown_invocation_source_delegates_rather_than_raising() -> None:
    """Fail-open on the *dialogue* path only.

    An exception here is not a caught error — it is dead air on a live call, and Lex's own fallback is a
    generic failure message. Delegating hands the turn back to a bot that knows how to run it. This is
    the opposite of the fail-CLOSED posture used for safety and for the telephony import guard, and the
    asymmetry is deliberate: the expensive failure there is proceeding, the expensive failure here is
    stopping.
    """
    response = lex_codehook.handler(_event(invocation_source="SomethingNew"), None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"


def test_a_malformed_event_still_returns_a_valid_delegate() -> None:
    response = lex_codehook.handler({"invocationSource": "DialogCodeHook"}, None)

    assert response["sessionState"]["dialogAction"]["type"] == "Delegate"
    assert "intent" in response["sessionState"]


def test_the_response_is_json_serialisable() -> None:
    """The runtime serialises the return value; a non-serialisable value fails after the handler returns,
    where the traceback names the runtime rather than the line that built the object."""
    json.dumps(lex_codehook.handler(_event(), None))


# ---------------------------------------------------------------------------------------------------
# `ADR-009` — the properties that make a cold start cheap, asserted rather than intended
# ---------------------------------------------------------------------------------------------------


def test_importing_the_module_constructs_no_boto3_client() -> None:
    """`ADR-009`: no client at module load, lazily created and cached per instance.

    A module-level `boto3.client(...)` costs an SDK import plus credential resolution on every cold start
    and makes SnapStart restore a snapshot holding a stale credential. Asserted here because it is the
    kind of line that gets added later, by someone reasonably thinking one client is free.
    """
    source = Path(lex_codehook.__file__).read_text(encoding="utf-8")
    module_level = [
        line
        for line in source.splitlines()
        if line and not line[0].isspace() and "boto3." in line and not line.startswith("#")
    ]

    assert module_level == [], f"module-level boto3 usage: {module_level}"


def test_the_module_imports_without_botocore_being_loaded() -> None:
    """The check above reads the source; this one measures the outcome. §3.5 — an artifact check is at
    most a fast pre-filter for a behavioural property, so both are here and only this one is the guard.

    Run in a subprocess because `botocore` is already imported in this test session by other modules.
    """
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
    """`CLAUDE.md`: everything runs locally without AWS. The Stage 3 handler makes no AWS call at all, and
    this test is what will fail loudly at Stage 4 if the graph invocation is wired in without a local path.
    """
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
