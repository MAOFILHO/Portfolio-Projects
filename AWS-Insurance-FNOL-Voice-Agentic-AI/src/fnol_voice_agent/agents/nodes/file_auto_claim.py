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


def _recap_for_success(filled: dict[str, Any]) -> str:
    """Narrower than `_summarize` -- 2 facts (type, date), not 3 (type/date/location), and deliberately
    not a call to `_summarize` itself. Two reasons, not one: (1) the caller already heard the full
    3-fact recap one turn ago at confirmation (`:114`'s `_summarize(filled)` call) -- repeating it
    verbatim here is redundant and, combined with the claim number and next-steps text this response
    also carries, risks the ~40-word voice budget the success response is held to; (2) this is the
    fact set the success response actually needs to name, not every fact `_summarize` happens to carry.
    Same `"That's a..."` phrasing convention as `_summarize`, not a new one invented for this call site.
    """
    return f"That's a {filled['loss_type']} loss on {filled['loss_datetime']}."


# `D89`/`OI6`: no invented business commitment exists anywhere in this system (`Claim`/`claims_server.py`
# checked -- neither carries an adjuster-SLA field), so "2 business days" here is illustrative flavor
# text, not a real system guarantee -- flagged rather than silently presented as measured. The
# status-check half IS grounded: `CheckClaimStatus` is a real intent a caller can reach by calling back.
_NEXT_STEPS = "An adjuster will contact you within 2 business days. Call back anytime to check your claim status."


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
        # `D89`/`OI6`: "...go ahead and file this claim?" collides with the `legal_and_medical_advice`
        # guardrail's "settlement negotiations" wording under this exact affirmation/interrogative
        # confirmation shape -- confirmed live, both directions (the agent's own prompt AND the caller's
        # natural "yes, go ahead and file it" reply), across five investigation rounds and two failed
        # guardrail-definition apply attempts (`RESULTS.md` §41-§49, `PROJECT_STATE.md` OI6). "submit" is
        # the evidenced-safe substitute -- `RESULTS.md` §41's own probe: "should I go ahead and submit
        # this claim" -> `NONE`. This is an application-side reword (Option B), not a guardrail change --
        # deliberately, since both guardrail-side attempts (an exclusion-clause carve-out and a positive
        # re-scoping) already failed, one at `apply` (200-char cap) and one at verification (0/4 fixed,
        # plus a regression). Residual, not eliminated by this fix: a caller who says "file" unprompted in
        # their own reply is still exposed -- this removes the agent's own prompt as the trigger, which is
        # the half within this system's control.
        return {
            "active_slot": _CONFIRM_KEY,
            "filled_slots": filled,
            "response_text": f"{_summarize(filled)} Should I go ahead and submit this claim?",
        }

    if filled[_CONFIRM_KEY] is not True:
        # Declined or ambiguous -- per SLOT-DESIGN.md's write-path discipline, no write happens; ask again
        # rather than silently proceeding or silently dropping the claim.
        filled.pop(_CONFIRM_KEY, None)
        return {
            "active_slot": _CONFIRM_KEY,
            "filled_slots": filled,
            "response_text": "Should I go ahead and submit this claim?",
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

    # Success response: recap (2 facts) + claim number + next steps, one turn, templated -- not
    # generated. This system has exactly two generation paths (`CoverageQuestion`,
    # `RentalTowingEntitlement`); every other response, this one included, is fixed text built from
    # already-validated slot values, so it cannot hallucinate a fact about the caller's own claim.
    # Deliberately drops the prior "Is there anything else?" tail (word-budget discipline, and
    # `check_claim_status.py`'s own terminal response carries no such tail either -- consistent with
    # that sibling intent's convention, not a new one invented here).
    return {
        "active_slot": None,
        "filled_slots": filled,
        "response_text": (
            f"{_recap_for_success(filled)} Your claim number is {claim.claim_number}. {_NEXT_STEPS}"
        ),
    }
