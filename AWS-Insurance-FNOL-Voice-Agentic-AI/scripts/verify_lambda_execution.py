"""The permanent deploy-time execution gate — `D80`/`D81`, `docs/phase8/STAGE4-LAMBDA-LAYER-PLAN.md` §4.

WHY THIS EXISTS, AND WHY IT IS NOT THE D77-STYLE READ-BACK
    `D80`: a Lambda deploy was verified by reading back `LastUpdateStatus: Successful`, `State: Active`,
    and a bit-for-bit `CodeSha256` match — real checks, and none of them execute the function. The
    deployed code crashed on its own first `import` statement on 100% of its invocations the entire time
    it was live, and that read-back could not have caught it, structurally, because it never asked the
    function to run. This script asks it to run. `RESULTS.md` §11.1: *"a deployment-verification check
    that reads service-reported deploy status, however rigorously, is necessary and not sufficient... The
    sufficient check invokes the function and reads its output."* This is that check.

WHY IT DOES NOT TRUST A BARE `StatusCode: 200`
    `lambda:Invoke`'s synchronous response carries `StatusCode: 200` for both a normal return AND an
    unhandled exception in the function — `D80`'s own diagnostic call (`RecognizeText`, one layer up at
    the Lex boundary) never raised either, for the identical reason: a codehook that crashes at cold
    start still produces a normal-looking response at the boundary that invoked it. The real signal is a
    separate `FunctionError` field (`"Unhandled"`/`"Handled"`) plus a structured error object in the
    payload body. Every event below is checked in order: (a) `FunctionError` absent from the `Invoke`
    response, checked first and explicitly; (b) the payload parses as JSON and carries a legal
    `sessionState.dialogAction.type` (`Delegate`/`ElicitSlot`/`Close`) — a well-formed body with the
    wrong shape (Lambda's own `errorMessage`/`errorType` JSON, which *is* valid JSON) fails here; (c) a
    literal marker specific to the exercised path, proving the intended branch of `_dispatch()` ran, not
    merely that *some* branch returned *something*.

THE EVENT MATRIX — 9 EVENTS, NOT THE 10 THE FIRST DRAFT OF THIS PLAN NAMED
    Plan §4's first draft said "each of the six in-scope intents' first turn." That overcounts by one:
    `CLAUDE.md`'s sixth in-scope intent is "injury or fatality mentioned," and `aws/bedrock_router.py`
    deliberately has NO `InjuryEscalation` value in its classifier's intent enum (`ADR-010`'s dominance
    requirement — injury is never something the router classifies a turn INTO, it is a safety flag plus
    the separate pre-graph L1 check). There is no "InjuryEscalation intent's first turn via ordinary
    classification" event to construct, because that code path does not exist; the raw-text L1 trigger
    event below already exercises the intent's only two entry points structurally available (pre-graph
    L1 raw text, and the graph's own in-band `L2` safety-flag branch, exercised indirectly since a
    genuinely dangerous-sounding FIRST turn for any intent would hit one of the two). Nine, not ten:

    1-5. The five ORDINARY intents' first turn (`FileAutoClaim`, `CheckClaimStatus`, `CoverageQuestion`,
         `RentalTowingEntitlement`, `UpdateContactInfo`) — canonical opener utterances taken verbatim
         from `bot.yaml.tftpl`'s own declared sample utterances, to minimise live-router classification
         variance rather than inventing phrasing the bot was never tuned against. Marker: `ElicitSlot`
         targeting the specific first slot each graph node (`agents/nodes/*.py`) asks for on an empty
         `filled_slots` — read from the NODE's own priority order, not Lex's declared `SlotPriorities`,
         because `api/lex_codehook.py`'s own docstring states the response shape is a function of the
         GRAPH's state, never Lex's own slot walk (`D78`).
    6.   `FallbackIntent` — a deliberately unclassifiable utterance. Marker: `Close` (not `ElicitSlot` --
         `handle_no_match_or_barge_in` never sets `active_slot` on a first-attempt no-match) with the
         exact fixed `GENERIC_REPROMPT` string (`agents/nodes/repair.py`) and no `escalate` attribute.
    7.   Raw-text L1 trigger (pre-graph, bypasses the graph and the checkpointer entirely).
    8.   Raw-text L3 trigger (pre-graph, the `D74` agent-override lexicon).
    9.   `injuries_present` confirmed True with no injury vocabulary in the raw text (`D79`).

    Events 7-9 are genuinely Bedrock-free (pre-graph, deterministic pattern matching, at most one
    checkpointer read). **Events 1-6 are NOT** — every turn that reaches the graph passes through
    `guardrails_input_check` (`ApplyGuardrail`) and `route_and_classify` (`classify_turn`, a real
    Bedrock Converse call) unconditionally, regardless of which intent Lex's own NLU already guessed;
    `agents/nodes/routing.py`'s own docstring confirms this runs on every turn that reaches it. Plan
    §4's first draft claimed "no Bedrock reached by any synthetic event" — checked against the actual
    graph code while writing this script, and it does not hold for 6 of the 9 events. Real, small cost:
    ~$0.0003/call (guardrail, 2 units) plus a fraction of a cent (Nova Micro router, a short prompt) per
    event, roughly **$0.002 total** for this script's own run, not the $0.00 the plan first claimed.
    Genuinely negligible against the $25 ceiling, but the CLAIM was wrong and is corrected here rather
    than left standing, same discipline as `D80`'s own "comment-as-evidence" finding.

    **Consequence stated plainly: this is NOT a pure liveness check.** A pure liveness check asks one
    question -- did the function execute -- and every event would be free to construct because none would
    depend on model behavior. 6 of these 9 events are not that: a FAILURE on one of them is ambiguous
    between (1) a `D80`-shaped infra regression and (2) an ordinary model-classification miss that has
    nothing to do with whether the Lambda executes. Only the 3 pre-graph events (L1, L3, `D79`) are pure
    liveness checks in the strict sense. Check WHICH event failed before concluding `D80` recurred.

STANDING-APPROVAL SCOPE — FLAGGED, NOT RESOLVED, HERE
    `CLAUDE.md`'s Bedrock standing approval is worded *"for Phases 3-7, capped at $5 total."* This
    script's own Bedrock spend happens in Phase 8. Whether that approval's scope extends past the phase
    range in its own wording, or a fresh approval / an explicit extension is needed, is Marco's call, not
    assumed either way by this script. **For that reason this target is deliberately NOT chained into
    `make deploy`** in this pass, despite plan §4 proposing exactly that -- it is `make
    verify-lambda-execution`, invocable on its own, so running it (and incurring its small real Bedrock
    spend) is always a separate, visible decision until that scope question is settled.

`ADR-013`: no `mock_aws()` in this file. Every `Invoke` call is real; 6 of the 9 events also make real,
billed Bedrock calls one layer down (see above).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import boto3

REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_DIR = REPO_ROOT / "infra" / "terraform" / "stacks" / "main"
REGION = "us-west-2"

_MINIMUM_EVENTS = 9  # `--require-at-least 1`'s cousin, `check_flows.py`'s discipline: finding nothing
# must never read as passing. A matrix that silently shrank to zero entries would otherwise report
# "0/0 passed" and exit 0.

# Estimated, not exact -- printed before any call is made, same cost-gate discipline as every other
# script in this repo that spends real money. See the module docstring's cost section for the basis.
_ESTIMATED_GUARDRAIL_CALLS = 6
_GUARDRAIL_PER_CALL_USD = 2 * 0.15 / 1000
_ESTIMATED_COST_USD = round(_ESTIMATED_GUARDRAIL_CALLS * _GUARDRAIL_PER_CALL_USD, 6)


def terraform_outputs(stack_dir: Path = STACK_DIR) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", f"-chdir={stack_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def _event(
    *,
    intent_name: str,
    transcript: str,
    slots: dict[str, Any] | None = None,
    session_attributes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Same wire shape `tests/unit/test_lex_codehook.py::_event` builds and the real Lex V2 service
    sends -- a fresh `sessionId` per event, so no event's checkpoint state leaks into another's."""
    slots = slots if slots is not None else {}
    return {
        "messageVersion": "1.0",
        "invocationSource": "DialogCodeHook",
        "inputMode": "Speech",
        "responseContentType": "text/plain; charset=utf-8",
        "sessionId": f"verify-lambda-execution-{uuid.uuid4()}",
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
                    "slots": slots,
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
                "slots": slots,
                "state": "InProgress",
                "confirmationState": "None",
            },
            "originatingRequestId": "a1b2c3d4-0000-0000-0000-000000000000",
        },
    }


def _slot(value: str) -> dict[str, Any]:
    return {
        "shape": "Scalar",
        "value": {"originalValue": value, "interpretedValue": value, "resolvedValues": [value]},
    }


def _dialog_action(payload: dict[str, Any]) -> dict[str, Any]:
    session_state = payload.get("sessionState") or {}
    action = session_state.get("dialogAction")
    return action if isinstance(action, dict) else {}


def _session_attributes(payload: dict[str, Any]) -> dict[str, Any]:
    session_state = payload.get("sessionState") or {}
    attributes = session_state.get("sessionAttributes")
    return attributes if isinstance(attributes, dict) else {}


def _message(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    if messages and isinstance(messages[0], dict):
        return str(messages[0].get("content", ""))
    return ""


def _expect_elicit_slot(slot_name: str) -> Callable[[dict[str, Any]], str | None]:
    def check(payload: dict[str, Any]) -> str | None:
        action = _dialog_action(payload)
        if action.get("type") != "ElicitSlot":
            return f"expected ElicitSlot, got dialogAction={action!r}"
        if action.get("slotToElicit") != slot_name:
            return f"expected slotToElicit={slot_name!r}, got {action.get('slotToElicit')!r}"
        return None

    return check


def _expect_detection_escalation(*, must_contain_911: bool) -> Callable[[dict[str, Any]], str | None]:
    """All three events this is used for (L1, L3, `D79`) are pre-graph paths, so the expected reason is
    specifically `detection-pregraph`, not just any `detection-*` value -- a `detection-graph` reading
    here would mean the pre-graph check DIDN'T fire and the turn fell through to the graph, which is
    itself a real regression on a synthetic event engineered to hit the pre-graph path directly."""

    def check(payload: dict[str, Any]) -> str | None:
        action = _dialog_action(payload)
        if action.get("type") != "Close":
            return f"expected Close, got dialogAction={action!r}"
        attributes = _session_attributes(payload)
        if attributes.get("escalate") != "true":
            return f"expected escalate=true, got sessionAttributes={attributes!r}"
        # `D81` item 4: the deploy gate checks provenance too, not only the raw wire flag -- a
        # fail-closed (or graph-provenance) escalation on one of these deliberately pre-graph synthetic
        # events would itself be a real finding, not a pass.
        if attributes.get("escalation_reason") != "detection-pregraph":
            return (
                f"expected escalation_reason=detection-pregraph, got "
                f"{attributes.get('escalation_reason')!r}"
            )
        message = _message(payload)
        has_911 = "911" in message
        if has_911 != must_contain_911:
            return f"expected 911-in-message={must_contain_911}, got message={message!r}"
        return None

    return check


def _expect_fallback_reprompt(payload: dict[str, Any]) -> str | None:
    action = _dialog_action(payload)
    if action.get("type") != "Close":
        return f"expected Close, got dialogAction={action!r}"
    attributes = _session_attributes(payload)
    if "escalate" in attributes:
        return f"expected no escalate attribute on an ordinary no-match, got {attributes!r}"
    message = _message(payload)
    if message != "I didn't quite catch that -- could you say that again?":
        return f"expected the fixed GENERIC_REPROMPT string, got message={message!r}"
    return None


@dataclass
class EventCase:
    name: str
    event: dict[str, Any]
    check: Callable[[dict[str, Any]], str | None]
    reaches_bedrock: bool = field(default=True)


def _build_event_matrix() -> list[EventCase]:
    return [
        EventCase(
            "FileAutoClaim first turn",
            _event(intent_name="FileAutoClaim", transcript="I need to file a claim"),
            _expect_elicit_slot("policy_number"),
        ),
        EventCase(
            "CheckClaimStatus first turn",
            _event(intent_name="CheckClaimStatus", transcript="what's the status of my claim"),
            _expect_elicit_slot("claim_or_policy_number"),
        ),
        EventCase(
            "CoverageQuestion first turn",
            _event(intent_name="CoverageQuestion", transcript="am I covered for a rental car"),
            _expect_elicit_slot("coverage_topic"),
        ),
        EventCase(
            "RentalTowingEntitlement first turn",
            _event(
                intent_name="RentalTowingEntitlement",
                transcript="can I get a rental car while mine is being fixed",
            ),
            _expect_elicit_slot("entitlement_type"),
        ),
        EventCase(
            "UpdateContactInfo first turn",
            _event(intent_name="UpdateContactInfo", transcript="I need to update my phone number"),
            _expect_elicit_slot("policy_number"),
        ),
        EventCase(
            "FallbackIntent (unclassifiable turn)",
            _event(intent_name="FallbackIntent", transcript="xyzzy plugh mumble"),
            _expect_fallback_reprompt,
        ),
        EventCase(
            "Raw-text L1 trigger (pre-graph, injury)",
            _event(intent_name="FileAutoClaim", transcript="my passenger isn't moving"),
            _expect_detection_escalation(must_contain_911=True),
            reaches_bedrock=False,
        ),
        EventCase(
            "Raw-text L3 trigger (pre-graph, agent override, D74)",
            _event(intent_name="FileAutoClaim", transcript="agent"),
            _expect_detection_escalation(must_contain_911=False),
            reaches_bedrock=False,
        ),
        EventCase(
            "injuries_present confirmed True, no injury vocabulary (D79)",
            _event(
                intent_name="FileAutoClaim",
                transcript="yes",
                slots={"injuries_present": _slot("Yes")},
            ),
            _expect_detection_escalation(must_contain_911=True),
            reaches_bedrock=False,
        ),
    ]


def invoke(
    lambda_client: Any, function_name: str, event: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Returns `(payload, error_detail)`. `error_detail` is set, and `payload` is `None` or best-effort,
    on any of: a transport-level exception, a non-empty `FunctionError`, or a payload that does not parse
    as JSON. Never trusts a bare `StatusCode: 200` -- see the module docstring."""
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(event).encode("utf-8"),
        )
    except Exception as exc:  # noqa: BLE001 - the failure itself is the finding
        return None, f"Invoke raised: {type(exc).__name__}: {exc}"

    raw = response["Payload"].read()
    function_error = response.get("FunctionError")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"payload did not parse as JSON ({exc}); FunctionError={function_error!r}; raw={raw[:500]!r}"

    if function_error:
        return payload, f"FunctionError={function_error!r} payload={payload}"

    dialog_type = _dialog_action(payload).get("type")
    if dialog_type not in ("Delegate", "ElicitSlot", "Close"):
        return payload, f"illegal sessionState.dialogAction.type: {dialog_type!r}"

    return payload, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    matrix = _build_event_matrix()
    if len(matrix) < _MINIMUM_EVENTS:
        print(
            f"=== verify-lambda-execution: event matrix has only {len(matrix)} case(s), "
            f"expected at least {_MINIMUM_EVENTS} -- refusing to report a pass from a shrunk matrix ==="
        )
        return 1

    outputs = terraform_outputs()
    function_name = str(outputs["codehook_function_name"])
    bedrock_events = sum(1 for c in matrix if c.reaches_bedrock)

    print(f"=== verify-lambda-execution: {function_name}, {len(matrix)} events ===")
    print(
        f"    estimated cost: {bedrock_events} events reach Bedrock (guardrail+router) at roughly "
        f"${_GUARDRAIL_PER_CALL_USD:.6f}/event -> ~${_ESTIMATED_COST_USD} total; the other "
        f"{len(matrix) - bedrock_events} are pre-graph and Bedrock-free. lambda:Invoke itself is inside "
        f"the always-free tier at this volume."
    )
    print(
        f"    NOT a pure liveness check: {bedrock_events} of {len(matrix)} events route through the "
        f"real router+guardrail. A failure there is ambiguous between an infra regression (D80-shaped) "
        f"and an ordinary model-classification miss -- check WHICH event failed before concluding D80 "
        f"recurred."
    )

    lambda_client = boto3.client("lambda", region_name=REGION)
    failures: list[str] = []
    for case in matrix:
        payload, error_detail = invoke(lambda_client, function_name, case.event)
        if error_detail:
            failures.append(f"{case.name}: {error_detail}")
            print(f"  FAIL {case.name}: {error_detail}")
            continue
        assert payload is not None  # invoke() only returns error_detail=None with a real payload
        marker_problem = case.check(payload)
        if marker_problem:
            failures.append(f"{case.name}: {marker_problem}")
            print(f"  FAIL {case.name}: {marker_problem}")
        else:
            print(f"  ok   {case.name}")

    if failures:
        print(f"\n=== verify-lambda-execution FAILED: {len(failures)}/{len(matrix)} event(s) ===")
        return 1

    print(f"\n=== verify-lambda-execution passed: {len(matrix)}/{len(matrix)} events ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
