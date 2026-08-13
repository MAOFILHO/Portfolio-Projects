"""`scripts/verify_lambda_execution.py`'s pure logic -- marker checks and `invoke()`'s response
parsing -- unit-tested against constructed payloads. No real AWS call anywhere in this file; the fake
Lambda client below stands in for `boto3.client("lambda")`, matching the style of
`test_measure_composed_pipeline_deployed.py`'s fake `lexv2-runtime` client.
"""

from __future__ import annotations

import json
from typing import Any

from scripts.verify_lambda_execution import (
    _build_event_matrix,
    _expect_detection_escalation,
    _expect_elicit_slot,
    _expect_fallback_reprompt,
    invoke,
)


def _payload(
    *,
    dialog_type: str = "Close",
    slot_to_elicit: str | None = None,
    session_attributes: dict[str, str] | None = None,
    message: str = "",
) -> dict[str, Any]:
    action: dict[str, Any] = {"type": dialog_type}
    if slot_to_elicit is not None:
        action["slotToElicit"] = slot_to_elicit
    return {
        "sessionState": {
            "dialogAction": action,
            "sessionAttributes": session_attributes if session_attributes is not None else {},
        },
        "messages": [{"contentType": "PlainText", "content": message}] if message else [],
    }


# ---------------------------------------------------------------------------------------------------
# The event matrix itself -- the `--require-at-least`-style guard depends on this staying true
# ---------------------------------------------------------------------------------------------------


def test_the_event_matrix_has_at_least_nine_cases() -> None:
    """Mirrors `check_flows.py`'s discipline: a matrix that silently shrank to zero would otherwise let
    `main()` report a vacuous pass. This test is the local, fast version of that guard."""
    assert len(_build_event_matrix()) >= 9


def test_every_case_name_is_unique() -> None:
    names = [case.name for case in _build_event_matrix()]
    assert len(names) == len(set(names))


# ---------------------------------------------------------------------------------------------------
# Marker checks
# ---------------------------------------------------------------------------------------------------


def test_expect_elicit_slot_passes_on_the_named_slot() -> None:
    check = _expect_elicit_slot("policy_number")
    assert check(_payload(dialog_type="ElicitSlot", slot_to_elicit="policy_number")) is None


def test_expect_elicit_slot_fails_on_a_different_slot() -> None:
    check = _expect_elicit_slot("policy_number")
    problem = check(_payload(dialog_type="ElicitSlot", slot_to_elicit="loss_datetime"))
    assert problem is not None
    assert "loss_datetime" in problem


def test_expect_elicit_slot_fails_on_the_wrong_dialog_action() -> None:
    check = _expect_elicit_slot("policy_number")
    problem = check(_payload(dialog_type="Delegate"))
    assert problem is not None


def test_expect_detection_escalation_passes_on_a_genuine_pregraph_detection() -> None:
    check = _expect_detection_escalation(must_contain_911=True)
    payload = _payload(
        dialog_type="Close",
        session_attributes={"escalate": "true", "escalation_reason": "detection-pregraph"},
        message="If anyone needs medical help, please hang up and call 911.",
    )
    assert check(payload) is None


def test_expect_detection_escalation_fails_on_fail_closed_provenance() -> None:
    """The deploy gate must not accept a fail-closed escalation on a deliberately-clean synthetic event
    as a pass -- that would mean the pre-graph path itself is degraded, not merely differently-provenanced."""
    check = _expect_detection_escalation(must_contain_911=True)
    payload = _payload(
        dialog_type="Close",
        session_attributes={"escalate": "true", "escalation_reason": "fail-closed"},
        message="If anyone needs medical help, please hang up and call 911.",
    )
    problem = check(payload)
    assert problem is not None
    assert "fail-closed" in problem


def test_expect_detection_escalation_fails_on_graph_provenance() -> None:
    """These three events (L1/L3/D79) are engineered to hit the PRE-GRAPH path directly. A
    `detection-graph` reading means the pre-graph check didn't fire and the turn fell through to the
    graph instead -- a real regression on this synthetic event, not an acceptable alternate provenance."""
    check = _expect_detection_escalation(must_contain_911=True)
    payload = _payload(
        dialog_type="Close",
        session_attributes={"escalate": "true", "escalation_reason": "detection-graph"},
        message="If anyone needs medical help, please hang up and call 911.",
    )
    problem = check(payload)
    assert problem is not None
    assert "detection-pregraph" in problem


def test_expect_detection_escalation_fails_when_escalate_is_missing() -> None:
    check = _expect_detection_escalation(must_contain_911=True)
    problem = check(_payload(dialog_type="Close"))
    assert problem is not None


def test_expect_detection_escalation_checks_911_presence_both_ways() -> None:
    must_have = _expect_detection_escalation(must_contain_911=True)
    no_911_payload = _payload(
        dialog_type="Close",
        session_attributes={"escalate": "true", "escalation_reason": "detection-pregraph"},
        message="connecting you now",
    )
    assert must_have(no_911_payload) is not None

    must_not_have = _expect_detection_escalation(must_contain_911=False)
    has_911_payload = _payload(
        dialog_type="Close",
        session_attributes={"escalate": "true", "escalation_reason": "detection-pregraph"},
        message="please call 911",
    )
    assert must_not_have(has_911_payload) is not None


def test_expect_fallback_reprompt_passes_on_the_fixed_generic_reprompt() -> None:
    payload = _payload(
        dialog_type="Close",
        message="I didn't quite catch that -- could you say that again?",
    )
    assert _expect_fallback_reprompt(payload) is None


def test_expect_fallback_reprompt_fails_if_escalate_is_present() -> None:
    """A `FallbackIntent` turn escalating at all is itself a real finding on this deliberately benign
    synthetic event -- the marker check must not accept it."""
    payload = _payload(
        dialog_type="Close",
        session_attributes={"escalate": "true", "escalation_reason": "detection-pregraph"},
        message="I didn't quite catch that -- could you say that again?",
    )
    problem = _expect_fallback_reprompt(payload)
    assert problem is not None
    assert "escalate" in problem


def test_expect_fallback_reprompt_fails_on_a_different_message() -> None:
    payload = _payload(dialog_type="Close", message="something else entirely")
    assert _expect_fallback_reprompt(payload) is not None


# ---------------------------------------------------------------------------------------------------
# `invoke()` -- never trusts a bare `StatusCode: 200`
# ---------------------------------------------------------------------------------------------------


class _FakeStreamingBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeLambdaClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response

    def invoke(self, **_: Any) -> dict[str, Any]:
        return self._response


def test_invoke_fails_on_a_present_function_error_even_with_statuscode_200() -> None:
    """`D80`'s own lesson, one layer down: `StatusCode: 200` is returned for both success and an
    unhandled exception. `FunctionError` is the real signal, checked first."""
    body = json.dumps({"errorMessage": "No module named 'pydantic'", "errorType": "Runtime.ImportModuleError"})
    response = {
        "StatusCode": 200,
        "FunctionError": "Unhandled",
        "Payload": _FakeStreamingBody(body.encode()),
    }
    payload, error_detail = invoke(_FakeLambdaClient(response), "fnol-codehook", {})
    assert error_detail is not None
    assert "FunctionError" in error_detail


def test_invoke_fails_on_a_payload_that_does_not_parse_as_json() -> None:
    response = {"StatusCode": 200, "Payload": _FakeStreamingBody(b"not json")}
    payload, error_detail = invoke(_FakeLambdaClient(response), "fnol-codehook", {})
    assert payload is None
    assert error_detail is not None
    assert "did not parse" in error_detail


def test_invoke_fails_on_an_illegal_dialog_action_type() -> None:
    """A well-formed JSON body with the wrong shape -- Lambda's own error JSON *is* valid JSON -- must
    not be accepted just because it parsed."""
    body = json.dumps({"sessionState": {"dialogAction": {"type": "SomethingElse"}}})
    response = {"StatusCode": 200, "Payload": _FakeStreamingBody(body.encode())}
    payload, error_detail = invoke(_FakeLambdaClient(response), "fnol-codehook", {})
    assert error_detail is not None
    assert "illegal" in error_detail


def test_invoke_passes_a_well_formed_legal_payload() -> None:
    body = json.dumps(
        {
            "sessionState": {
                "dialogAction": {"type": "ElicitSlot", "slotToElicit": "policy_number"},
                "sessionAttributes": {},
            },
            "messages": [{"contentType": "PlainText", "content": "What's your policy number?"}],
        }
    )
    response = {"StatusCode": 200, "Payload": _FakeStreamingBody(body.encode())}
    payload, error_detail = invoke(_FakeLambdaClient(response), "fnol-codehook", {})
    assert error_detail is None
    assert payload is not None
    assert payload["sessionState"]["dialogAction"]["slotToElicit"] == "policy_number"


class _RaisingLambdaClient:
    def invoke(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("simulated transport failure")


def test_invoke_handles_a_transport_level_exception() -> None:
    payload, error_detail = invoke(_RaisingLambdaClient(), "fnol-codehook", {})
    assert payload is None
    assert error_detail is not None
    assert "Invoke raised" in error_detail
