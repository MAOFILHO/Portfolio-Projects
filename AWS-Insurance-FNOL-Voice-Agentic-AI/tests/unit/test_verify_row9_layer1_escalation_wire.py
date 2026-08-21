"""Row 9 (`D140`/`OI58`) Layer 1 harness — assertion logic only, unit-tested against constructed
`RecognizeText`-shaped fixtures. No real AWS call anywhere in this file, and no `boto3` import: the
live transport (`recognize_live`) is a separate, untested-here shim per the module's own docstring.

Four fixture shapes, matching the wire contract traced in `api/lex_codehook.py::_close` (`:326-328`,
`:344-351`) and confirmed against the downstream consumer
(`infra/terraform/stacks/main/flows/fnol-inbound.json.tftpl:90-104`, which compares
`$.Attributes.escalate` to the literal string `"true"`):

  (a) `sessionAttributes.escalate` present and `"true"`             -> escalated
  (b) `sessionAttributes` present, `escalate` key absent             -> not_escalated, escalate_raw=None
  (c) `sessionAttributes.escalate` present but falsy (e.g. `"false"`) -> not_escalated, escalate_raw="false"
  (d) `sessionAttributes` missing, `None`, or not a `dict`            -> malformed (its own state, never
      silently folded into not_escalated -- same reasoning as `D81` item 1's
      `invalid`/`not-escalated` split in `measure_composed_pipeline_deployed.py`: an absent or broken
      wire shape is not evidence the system correctly decided not to escalate).
"""

from __future__ import annotations

from typing import Any

from scripts.verify_row9_layer1_escalation_wire import classify_escalation_wire


def _response(session_state: dict[str, Any] | None) -> dict[str, Any]:
    body: dict[str, Any] = {"messages": []}
    if session_state is not None:
        body["sessionState"] = session_state
    return body


def test_escalate_true_is_classified_escalated() -> None:
    response = _response(
        {
            "dialogAction": {"type": "Close"},
            "intent": {"name": "FileAutoClaim", "state": "Fulfilled"},
            "sessionAttributes": {"escalate": "true", "escalation_reason": "detection-pregraph"},
        }
    )

    result = classify_escalation_wire(response)

    assert result.status == "escalated"
    assert result.escalate_raw == "true"
    assert result.escalation_reason == "detection-pregraph"
    assert result.detail is None


def test_escalate_key_absent_is_classified_not_escalated() -> None:
    response = _response(
        {
            "dialogAction": {"type": "Close"},
            "intent": {"name": "FileAutoClaim", "state": "Fulfilled"},
            "sessionAttributes": {"contactId": "abc-123"},
        }
    )

    result = classify_escalation_wire(response)

    assert result.status == "not_escalated"
    assert result.escalate_raw is None
    assert result.escalation_reason is None


def test_escalate_present_but_falsy_is_classified_not_escalated_and_distinguished_from_absent() -> None:
    response = _response(
        {
            "dialogAction": {"type": "Close"},
            "intent": {"name": "FileAutoClaim", "state": "Fulfilled"},
            "sessionAttributes": {"escalate": "false"},
        }
    )

    result = classify_escalation_wire(response)

    assert result.status == "not_escalated"
    # Distinguished from the absent-key case: the raw value was actually present and falsy, not missing.
    assert result.escalate_raw == "false"
    assert result.escalate_raw is not None


def test_sessionattributes_missing_is_malformed_not_silently_not_escalated() -> None:
    response = _response(
        {
            "dialogAction": {"type": "Close"},
            "intent": {"name": "FileAutoClaim", "state": "Fulfilled"},
            # no "sessionAttributes" key at all
        }
    )

    result = classify_escalation_wire(response)

    assert result.status == "malformed"
    assert result.detail is not None
    assert "sessionAttributes" in result.detail


def test_sessionattributes_none_is_malformed() -> None:
    response = _response(
        {
            "dialogAction": {"type": "Close"},
            "intent": {"name": "FileAutoClaim", "state": "Fulfilled"},
            "sessionAttributes": None,
        }
    )

    result = classify_escalation_wire(response)

    assert result.status == "malformed"
    assert result.detail is not None


def test_sessionattributes_wrong_type_is_malformed() -> None:
    response = _response(
        {
            "dialogAction": {"type": "Close"},
            "intent": {"name": "FileAutoClaim", "state": "Fulfilled"},
            "sessionAttributes": "not-a-dict",
        }
    )

    result = classify_escalation_wire(response)

    assert result.status == "malformed"
    assert result.detail is not None


def test_sessionstate_itself_missing_is_malformed() -> None:
    response = _response(None)

    result = classify_escalation_wire(response)

    assert result.status == "malformed"
    assert result.detail is not None
    assert "sessionState" in result.detail
