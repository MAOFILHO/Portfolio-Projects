"""Row 9 (`D140`/`OI58`) Layer 1 harness — the deployed Lambda's real Lex wire signal, not local graph
state. `PROJECT_STATE.md` row 9, `RESULTS.md` §100: Layer 0 (local graph state, the three sites fixed
directly calling `initiate_escalation()`) is DONE; Layer 1 (this file) is the row's remaining bar —
reading `sessionAttributes.escalate`/`escalation_reason` back off a real `RecognizeText` response for
those same three sites, not the injury-lexicon trigger surface `measure_composed_pipeline_deployed.py`
already covers.

DESIGN: ASSERTION SEPARATE FROM TRANSPORT
    Everything below `classify_escalation_wire` is pure — a dict in, a `WireClassification` out, no I/O,
    no `boto3` import at module scope, fully exercised by `tests/unit/test_verify_row9_layer1_escalation_wire.py`
    against fixtures at zero spend. `recognize_live`, at the bottom of this file, is the one thing that
    actually calls AWS — it is a thin shim taking bot/alias/region + an utterance and returning the raw
    `RecognizeText` response dict UNMODIFIED, with no parsing inside it. No test in this repo calls it;
    it exists to be wired up later (a `make verify-row9-layer1` target, run only after a `stacks/main`
    deploy and `APPROVED: Phase 12`), not exercised here.

WHAT COUNTS AS `malformed`, AND WHY IT IS ITS OWN STATE
    A response with no `sessionState`, a `sessionState` with no `sessionAttributes`, or a
    `sessionAttributes` that isn't a `dict` is NOT the same thing as "the system decided not to
    escalate" — it's evidence the wire shape itself is broken (a stale deploy, a bot-alias mismatch, a
    Lex-native fallback). Folding it into `not_escalated` would let a cold-start crash or a schema drift
    read as a clean negative, the same silent-collapse `D81` item 1 named and fixed one level up in
    `measure_composed_pipeline_deployed.py::_classify_invocation`. `classify_escalation_wire` keeps
    `malformed` as a third, distinct status instead.

WHAT "ESCALATED" MEANS ON THE WIRE, TRACED NOT ASSUMED
    `api/lex_codehook.py::_close()` sets `session_attributes["escalate"] = "true"` (`:326`) — the literal
    string `"true"`, not a boolean — inside its `if escalated:` branch, and returns it at
    `sessionState.sessionAttributes` (`:344-348`). That exact attribute and exact string are what
    `infra/terraform/stacks/main/flows/fnol-inbound.json.tftpl`'s `CheckEscalation` action (`:90-104`)
    compares against (`Operator: Equals, Operands: ["true"]`) to decide whether to transfer the call — so
    reading `escalate == "true"` back off `RecognizeText` is reading the exact production signal, not a
    proxy for it. `escalation_reason` (`:328`) is one of `EscalationReason`'s four values
    (`lex_codehook.py:164`); this module's own `WireClassification.escalation_reason` is read through
    verbatim, unvalidated against that literal set — an unrecognized or missing value is reported exactly
    as seen, not coerced to a default, so a future rename or a stale deploy shows up as itself rather than
    disappearing into a known-good bucket.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

WireStatus = Literal["escalated", "not_escalated", "malformed"]


@dataclass(frozen=True, slots=True)
class WireClassification:
    """The result of classifying one raw `RecognizeText`-shaped response.

    `escalate_raw` is the literal value found at `sessionAttributes.escalate`, or `None` if the key was
    absent — kept distinct from a `"false"`-shaped value on purpose, so a caller can tell "no signal was
    ever written" apart from "a signal was written and it was negative," even though both currently
    classify as `not_escalated`.
    """

    status: WireStatus
    escalate_raw: Any | None
    escalation_reason: str | None
    detail: str | None


def _malformed(detail: str) -> WireClassification:
    return WireClassification(
        status="malformed", escalate_raw=None, escalation_reason=None, detail=detail
    )


def classify_escalation_wire(response: dict[str, Any]) -> WireClassification:
    """Classify one raw `RecognizeText` response dict. Pure function, no I/O — see module docstring."""
    if not isinstance(response, dict):
        return _malformed(f"response is not a dict (got {type(response).__name__})")

    session_state = response.get("sessionState")
    if not isinstance(session_state, dict):
        return _malformed(
            f"sessionState missing or not an object (got {type(session_state).__name__})"
        )

    session_attributes = session_state.get("sessionAttributes")
    if not isinstance(session_attributes, dict):
        return _malformed(
            f"sessionAttributes missing or not an object (got {type(session_attributes).__name__})"
        )

    escalate_raw = session_attributes.get("escalate")
    escalation_reason = session_attributes.get("escalation_reason")

    if escalate_raw == "true":
        return WireClassification(
            status="escalated",
            escalate_raw=escalate_raw,
            escalation_reason=escalation_reason,
            detail=None,
        )

    return WireClassification(
        status="not_escalated",
        escalate_raw=escalate_raw,
        escalation_reason=escalation_reason,
        detail=None,
    )


def recognize_live(
    *,
    bot_id: str,
    bot_alias_id: str,
    region: str,
    text: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Live transport shim — the ONLY function in this file that touches AWS. Not called by any test in
    this repo (`ADR-013`: every real `RecognizeText` call is billed, however negligibly). Returns the raw
    response dict unmodified; no parsing happens here — that's `classify_escalation_wire`'s job, run by
    the caller on this function's return value.
    """
    import boto3  # local import: this module must stay importable, and its assertion logic testable, with

    # no AWS SDK dependency at collection time — the same reason `ADR-009` keeps `boto3` out of
    # `lex_codehook.py`'s module scope.

    runtime = boto3.client("lexv2-runtime", region_name=region)
    resolved_session_id = session_id or f"row9-layer1-{uuid.uuid4()}"
    return runtime.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId="en_US",
        sessionId=resolved_session_id,
        text=text,
    )
