"""The shared no-input/no-match AND barge-in-inconclusive repair node -- `DIALOGUE-POLICIES.md` §7, §6.2.

**This is the single code path both trigger types go through.** Marco's integration requirement, restated
as the design it produces: a normal no-match on a slot and an inconclusive barge-in (no safety trigger
detected, per §6.2) are not two different handlers sharing a counter -- they are the same function call.
`agents/graph.py`'s conditional routing decides *when* this node is entered (on a no-match classification,
or on `state["is_barge_in"]` with no safety flag and low/ambiguous intent confidence); once entered, this
node does not branch on which of those conditions applied except to choose which line to speak -- the
counter increment and ceiling check (`agents/retry_ladder.py`) are identical either way.

Only two outcomes exist, matching §7's stated design: another attempt (with a response the caller hears),
or escalation. There is no third branch and no loop back into this node from itself within one graph
invocation -- the *next* turn re-enters fresh at L1, with `retry_counts` carried forward by the
checkpointer (`ADR-005`).
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.retry_ladder import ceiling_reached, record_attempt
from fnol_voice_agent.agents.state import AgentState, EscalationRecord
from fnol_voice_agent.mcp.escalation_server import initiate_escalation

# DIALOGUE-POLICIES.md §6.2: the open re-prompt for an inconclusive barge-in -- never a silent resumption
# of the original script.
BARGE_IN_OPEN_REPROMPT = "Sorry -- go ahead, what were you saying?"

# A generic rephrased reprompt for a normal no-match. The exact per-slot rephrasing catalog is
# SLOT-DESIGN.md's content, consumed by Phase 8's Lex configuration -- this graph's job is the retry
# *control flow* (count, ceiling, escalate), not the full prompt library, so a single honest generic line
# stands in here rather than a fabricated per-slot catalog this stage doesn't own.
GENERIC_REPROMPT = "I didn't quite catch that -- could you say that again?"

# DIALOGUE-POLICIES.md §7: the ceiling's terminal state is always escalation, never a hang-up.
CAPABILITY_ESCALATION_SCRIPT = (
    "I'm having trouble catching that -- let me connect you with someone who can help."
)

_UNKEYED_TURN = "__turn__"  # retry-ladder key for turn-level ambiguity with no specific active slot


def handle_no_match_or_barge_in(state: AgentState) -> dict[str, Any]:
    key = state.get("active_slot") or _UNKEYED_TURN
    retry_counts = record_attempt(state.get("retry_counts", {}), key)

    if ceiling_reached(retry_counts, key):
        result = initiate_escalation(
            contact_id=state.get("contact_id", "unknown"),
            triggering_layer="capability",
            context={
                "filled_slots": state.get("filled_slots", {}),
                "active_slot": key,
                "reason": "retry_ceiling_reached",
                "attempts": retry_counts[key],
            },
        )
        escalation: EscalationRecord = {
            "contact_id": result.contact_id,
            "triggering_layer": result.triggering_layer,
            "route": 3,  # DIALOGUE-POLICIES.md §8: capability
            "reason": "retry_ceiling_reached",
            "context": result.context,
        }
        return {
            "retry_counts": retry_counts,
            "response_text": CAPABILITY_ESCALATION_SCRIPT,
            "escalation": escalation,
        }

    response_text = BARGE_IN_OPEN_REPROMPT if state.get("is_barge_in") else GENERIC_REPROMPT
    return {"retry_counts": retry_counts, "response_text": response_text}
