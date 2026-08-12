"""`FileAutoClaim` -- `SLOT-DESIGN.md` §1's 11-slot elicitation, priority-ordered per §1.1.

**Scope boundary, stated rather than silently simplified**: this node decides *what to ask next* and
*when enough is known to file*, given whatever is already in `state["filled_slots"]` -- it does not parse
raw speech into slot values itself. That is Lex's own NLU job (`ADR-001`: "Lex V2 remains the
turn-manager"), not built until Phase 8; this graph receives already-interpreted values the way a real
Lex codehook would. `insured_vehicle_vin` is assumed already resolved to a VIN by the time it reaches
`filled_slots` (Lex's enum-disambiguation of "my Honda Civic" against the policy's vehicle list,
`SLOT-DESIGN.md` §1.2) -- not re-resolved here.

**Per-turn contract** (same as every intent node in this package): a falsy/missing `response_text` means
"no new information this turn for the slot we were waiting on" -- `agents/graph.py` routes that to the
shared repair node (`nodes/repair.py`). A truthy `response_text` means this turn produced a real response
for the caller.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState
from fnol_voice_agent.mcp.claims_server import (
    InvalidNewClaimError,
    PolicyNotFoundErrorForNewClaim,
    VehicleNotOnPolicyError,
    file_new_claim,
)

# SLOT-DESIGN.md §1.1's elicitation priority order. injuries_present is not here -- DIALOGUE-POLICIES.md
# §5's hard escalation preempts before this node is ever reached on an injury-flagged turn, so this node
# never asks it.
_SLOT_ORDER: tuple[str, ...] = (
    "policy_number",
    "insured_vehicle_vin",
    "loss_datetime",
    "loss_location",
    "loss_type",
    "damage_description",
    "other_party_involved",
    "police_report_filed",
    "police_report_number",
    "driver_name",
)
_CONDITIONAL_ON: dict[str, tuple[str, Any]] = {
    "police_report_number": ("police_report_filed", True)
}

_ELICITATION_PROMPTS: dict[str, str] = {
    "policy_number": "What's your policy number?",
    "insured_vehicle_vin": "Which of your vehicles is this about?",
    "loss_datetime": "When did this happen?",
    "loss_location": "Where did it happen?",
    "loss_type": "Was this a collision, a comprehensive-type loss like theft or weather, or something else?",
    "damage_description": "Can you describe the damage?",
    "other_party_involved": "Was another vehicle or driver involved?",
    "police_report_filed": "Was a police report filed?",
    "police_report_number": "What's the report number?",
    "driver_name": "Were you driving, or someone else?",
}

_CONFIRM_KEY = "confirm_file_claim"


def _next_missing_slot(filled: dict[str, Any]) -> str | None:
    for slot in _SLOT_ORDER:
        if slot in _CONDITIONAL_ON:
            dep_slot, dep_value = _CONDITIONAL_ON[slot]
            if filled.get(dep_slot) != dep_value:
                continue  # not applicable given the caller's other answers
        if filled.get(slot) is None:
            return slot
    return None


def _summarize(filled: dict[str, Any]) -> str:
    return (
        f"So that's a {filled['loss_type']} loss on {filled['loss_datetime']} "
        f"at {filled['loss_location']}."
    )


def file_auto_claim(state: AgentState) -> dict[str, Any]:
    filled = dict(state.get("filled_slots", {}))
    active_slot = state.get("active_slot")

    if active_slot is not None and active_slot != _CONFIRM_KEY and active_slot not in filled:
        # We asked for `active_slot` last turn and it's still missing -- a no-match on this specific slot.
        return {"active_slot": active_slot, "response_text": None}

    next_slot = _next_missing_slot(filled)
    if next_slot is not None:
        return {
            "active_slot": next_slot,
            "filled_slots": filled,
            "response_text": _ELICITATION_PROMPTS[next_slot],
        }

    if _CONFIRM_KEY not in filled:
        return {
            "active_slot": _CONFIRM_KEY,
            "filled_slots": filled,
            "response_text": f"{_summarize(filled)} Should I go ahead and file this claim?",
        }

    if filled[_CONFIRM_KEY] is not True:
        # Declined or ambiguous -- per SLOT-DESIGN.md's write-path discipline, no write happens; ask again
        # rather than silently proceeding or silently dropping the claim.
        filled.pop(_CONFIRM_KEY, None)
        return {
            "active_slot": _CONFIRM_KEY,
            "filled_slots": filled,
            "response_text": "Should I go ahead and file this claim?",
        }

    try:
        claim = file_new_claim(
            policy_number=filled["policy_number"],
            insured_vehicle_vin=filled["insured_vehicle_vin"],
            loss_datetime=filled["loss_datetime"],
            loss_location=filled["loss_location"],
            loss_type=filled["loss_type"],
            damage_description=filled["damage_description"],
            driver_name=filled["driver_name"],
            other_party_involved=filled["other_party_involved"],
            police_report_filed=filled["police_report_filed"],
            injuries_present=False,  # guaranteed by DIALOGUE-POLICIES.md §5's preemption
            police_report_number=filled.get("police_report_number"),
        )
    except (VehicleNotOnPolicyError, PolicyNotFoundErrorForNewClaim, InvalidNewClaimError) as exc:
        return {
            "response_text": (
                f"I ran into a problem filing that -- let me get you to someone who can help. ({exc})"
            )
        }

    return {
        "active_slot": None,
        "filled_slots": filled,
        "response_text": f"Your claim number is {claim.claim_number}. Is there anything else?",
    }
