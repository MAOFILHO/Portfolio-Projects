"""Call outcome (`CONTEXT.md`): how a call ended, one of exactly five values (Phase 8 D10).

`session.py` classifies a call with a raw `end_reason` -- eight values today -- and D17 fixes how
those collapse onto D10's five. The raw value is kept beside the outcome by the writer, so nothing
is lost by collapsing. Only the four clean endings get a named outcome; anything else, including a
value nobody has invented yet, is `error` -- never left unclassified (exit criterion 3).
"""
from ..dispatch import gate

AUTHENTICATED_SERVED = "authenticated_served"
ESCALATED = "escalated"
CALLER_HANGUP = "caller_hangup"
CLOSED_PATH = "closed_path"
ERROR = "error"

CALL_OUTCOMES = frozenset(
    {AUTHENTICATED_SERVED, ESCALATED, CALLER_HANGUP, CLOSED_PATH, ERROR}
)

#: Every `end_reason` session.py can emit. A drift test scans session.py and fails when it emits one
#: that is not listed here, so a new value gets a decision instead of silently becoming `error`.
KNOWN_END_REASONS = frozenset({
    "closed", "escalated", "caller_hangup", "model_ended",
    "cost_cap", "timeout", "attempts_exhausted", "error",
})


def call_outcome(end_reason, auth_state):
    if end_reason == "closed":
        return CLOSED_PATH
    if end_reason == "escalated":
        return ESCALATED
    if end_reason == "caller_hangup":
        return CALLER_HANGUP
    if end_reason == "model_ended" and auth_state == gate.AUTHENTICATED:
        return AUTHENTICATED_SERVED
    return ERROR
