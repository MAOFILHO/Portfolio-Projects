"""`InjuryEscalation` -- `DIALOGUE-POLICIES.md` §5. Fixed, scripted, no LLM discretion: the words
themselves are constants, not generated (`PROMPT-REGISTRY.md`'s D17 -- this is one of the fixed-string
turns that make up the majority of this system's non-generative surface area).
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState, EscalationRecord
from fnol_voice_agent.mcp.escalation_server import initiate_escalation

# DIALOGUE-POLICIES.md §5 step 1: safety guidance first, verbatim, before anything else including the
# transfer announcement itself.
SAFETY_SCRIPT = (
    "If anyone needs medical help, please hang up and call 911. "
    "I'm connecting you with someone who can help right away."
)


def injury_escalation(state: AgentState) -> dict[str, Any]:
    triggering_layer = "L1" if state.get("l1_safety_flag") else "L2"
    result = initiate_escalation(
        contact_id=state.get("contact_id", "unknown"),
        triggering_layer=triggering_layer,
        context={
            "filled_slots": state.get("filled_slots", {}),
            "triggering_utterance": state.get("turn_input", ""),
            "matched_term": state.get("l1_matched_term"),
        },
    )
    escalation: EscalationRecord = {
        "contact_id": result.contact_id,
        "triggering_layer": result.triggering_layer,
        "route": 1,  # DIALOGUE-POLICIES.md §8: safety is always route 1
        "reason": "safety",
        "context": result.context,
    }
    return {"response_text": SAFETY_SCRIPT, "escalation": escalation}
