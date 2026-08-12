"""`UpdateContactInfo` -- the only write path besides `FileAutoClaim`. `DIALOGUE-POLICIES.md` §4: writes
only on unambiguous affirmative confirmation, with exactly **one** retry on a failed/ambiguous
confirmation -- tighter than the shared two-attempt retry ladder (`agents/retry_ladder.py`'s
`RETRY_CEILING`), by design, because a silent partial write is a critical defect, not a missed target.
Still reuses `retry_ladder.record_attempt` for the counting primitive -- same mechanism, a stricter
threshold checked locally, not a second counting implementation.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.retry_ladder import record_attempt
from fnol_voice_agent.agents.state import AgentState
from fnol_voice_agent.mcp.contact_server import (
    InvalidUpdateContactInfoError,
    PolicyNotFoundError,
    update_contact_info,
)
from fnol_voice_agent.models.enums import ContactField

_CONFIRM_CEILING = 1  # DIALOGUE-POLICIES.md §4: one retry, not the shared ladder's two.
_CONFIRM_KEY = "confirm_update_contact_info"

_SLOT_PROMPTS = {
    "policy_number": "What's your policy number?",
    "field": "Is this your phone number, email, or mailing address?",
    "new_value": "What should I update it to?",
}
_ESCALATION_SCRIPT = (
    "I want to make sure I get this exactly right -- let me connect you with someone who can update that "
    "for you."
)


def update_contact_info_node(state: AgentState) -> dict[str, Any]:
    filled = dict(state.get("filled_slots", {}))
    active_slot = state.get("active_slot")

    for slot in ("policy_number", "field", "new_value"):
        if filled.get(slot) is None:
            if active_slot == slot:
                return {"active_slot": slot, "response_text": None}
            return {
                "active_slot": slot,
                "filled_slots": filled,
                "response_text": _SLOT_PROMPTS[slot],
            }

    if _CONFIRM_KEY not in filled:
        return {
            "active_slot": _CONFIRM_KEY,
            "filled_slots": filled,
            "response_text": f"That's {filled['new_value']} -- is that right?",
        }

    if filled[_CONFIRM_KEY] is not True:
        retry_counts = record_attempt(state.get("retry_counts", {}), _CONFIRM_KEY)
        if retry_counts[_CONFIRM_KEY] > _CONFIRM_CEILING:
            return {
                "retry_counts": retry_counts,
                "response_text": _ESCALATION_SCRIPT,
            }
        filled.pop(_CONFIRM_KEY, None)
        return {
            "active_slot": _CONFIRM_KEY,
            "filled_slots": filled,
            "retry_counts": retry_counts,
            "response_text": f"That's {filled['new_value']} -- is that right?",
        }

    try:
        result = update_contact_info(
            policy_number=filled["policy_number"],
            field=ContactField(filled["field"]),
            new_value=filled["new_value"],
        )
    except (InvalidUpdateContactInfoError, PolicyNotFoundError) as exc:
        return {"response_text": f"I ran into a problem making that update. ({exc})"}

    return {
        "active_slot": None,
        "filled_slots": filled,
        "response_text": f"Done -- your {result.field} is updated.",
    }
