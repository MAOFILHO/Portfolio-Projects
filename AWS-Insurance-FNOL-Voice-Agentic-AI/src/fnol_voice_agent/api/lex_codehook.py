"""Lex V2 codehook — the Lambda entry point Amazon Lex calls on every turn.

Phase 8 Stage 3.

WHAT THIS IS TODAY, AND WHAT IT IS NOT
    This module implements the Lex V2 `sessionState` wire contract and nothing above it. On a
    `DialogCodeHook` it returns `Delegate`, which hands the turn back to the bot's own slot-elicitation
    state machine; on a `FulfillmentCodeHook` it returns `Close` with a spoken line.

    **The graph is not called yet, and neither is L1/L2.** Stage 4 replaces `_dispatch()` with the
    LangGraph invocation keyed on the Connect `contactId` per `ADR-005`, and the safety pre-node runs
    there. `CLAUDE.md` forbids shipping something stubbed and labelled "production would do X here" —
    this is not that. It is an incomplete implementation with the incomplete part named, deployed in the
    stage that owns the infrastructure and completed in the stage that owns the code. What is here runs;
    what is not here is not claimed.

    The consequence is recorded in `docs/phase8/BUILD-PLAN.md` and acted on rather than noted: **the DID
    is deliberately NOT associated with a contact flow in Stage 3.** A number that answers is a number a
    stranger can dial, and an FNOL bot that collects claim data without an injury-detection path is worse
    than a number that rings out. The association lands in Stage 4, behind a working safety path.

`ADR-009`
    No client at module load. No import of `boto3` at module scope. Any client Stage 4 needs is created
    lazily and cached on first use, so the init phase — which AWS has billed on on-demand ZIP functions
    since 2025 — stays as short as the runtime allows and a SnapStart snapshot cannot capture a stale
    credential. `tests/unit/test_lex_codehook.py` asserts both the source-level and the observed form of
    this, because the source-level one alone is a §3.5 artifact check.

FAILING OPEN, DELIBERATELY
    Every error path here ends in `Delegate`. On a live call an unhandled exception is not a logged
    error, it is dead air followed by Lex's generic failure message. This is the opposite posture to the
    telephony import guard and to the safety detector, both of which fail closed, and the asymmetry is
    the point: there the expensive failure is proceeding, here the expensive failure is stopping.

    That posture is scoped to the *dialogue* path and does not survive Stage 4 unexamined. Once the graph
    runs behind this handler, an exception swallowed on a turn that contained an injury disclosure would
    be a `C1` breach wearing a resilience argument, so Stage 4 owns splitting these two cases.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Spoken on fulfilment. A `Close` with no message ends the call in silence, which a caller hears as a
#: dropped line rather than as a completed one. Replaced by the graph's own close-out — the full claim
#: read-back of `SLOT-DESIGN.md` §1.3 — at Stage 4.
FULFILMENT_MESSAGE = (
    "Thank you. I have what I need for now. A claims specialist will follow up with you."
)


def _intent_from(event: dict[str, Any]) -> dict[str, Any]:
    """The intent to echo back, taken from `sessionState` and never rebuilt.

    Rebuilding it is how slot values get dropped: an intent returned without its `slots` map erases every
    value collected so far, and the caller experiences that as being asked the same question again. Lex
    reports no error for it. So the whole object round-trips and the handler mutates only what it means
    to change.
    """
    session_state = event.get("sessionState") or {}
    intent = session_state.get("intent")

    if isinstance(intent, dict):
        return dict(intent)

    # A malformed event still has to produce a response Lex accepts. `Delegate` without an intent name
    # is rejected, so fall back to the first interpretation, then to a bare shape.
    interpretations = event.get("interpretations") or []
    if interpretations and isinstance(interpretations[0], dict):
        candidate = interpretations[0].get("intent")
        if isinstance(candidate, dict):
            return dict(candidate)

    return {"name": "FallbackIntent", "slots": {}, "state": "InProgress"}


def _session_attributes_from(event: dict[str, Any]) -> dict[str, str]:
    """Session attributes round-trip untouched.

    `ADR-005` keys the checkpointer on the Connect `contactId`, which reaches Lex as a session attribute
    set by the contact flow. Dropping it silently starts a new conversation thread mid-call.
    """
    session_state = event.get("sessionState") or {}
    attributes = session_state.get("sessionAttributes")
    return dict(attributes) if isinstance(attributes, dict) else {}


def _delegate(event: dict[str, Any]) -> dict[str, Any]:
    """Hand the turn back to Lex's elicitation state machine."""
    return {
        "sessionState": {
            "dialogAction": {"type": "Delegate"},
            "intent": _intent_from(event),
            "sessionAttributes": _session_attributes_from(event),
        }
    }


def _close(event: dict[str, Any], message: str) -> dict[str, Any]:
    intent = _intent_from(event)
    intent["state"] = "Fulfilled"

    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": intent,
            "sessionAttributes": _session_attributes_from(event),
        },
        "messages": [{"contentType": "PlainText", "content": message}],
    }


def _dispatch(event: dict[str, Any]) -> dict[str, Any]:
    """The one function Stage 4 replaces.

    Everything above it is the wire contract and does not change; everything below it is the agent. The
    seam is here so that Stage 4 is a change to what the handler decides, not to how it speaks.
    """
    invocation_source = event.get("invocationSource")

    if invocation_source == "FulfillmentCodeHook":
        return _close(event, FULFILMENT_MESSAGE)

    return _delegate(event)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point. `fnol_voice_agent.api.lex_codehook.handler`."""
    try:
        return _dispatch(event)
    except Exception:  # noqa: BLE001 - see the module docstring on failing open
        logger.exception("codehook failed; delegating the turn back to Lex")
        return _delegate(event if isinstance(event, dict) else {})
