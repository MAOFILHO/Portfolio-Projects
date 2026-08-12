"""`CheckClaimStatus` -- `SLOT-DESIGN.md` §3. Templated status summary, not generated (`PROMPT-REGISTRY.md`
D17) -- a status string substituted into a fixed template needs no model call.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState
from fnol_voice_agent.mcp.claims_server import (
    ClaimNotFoundError,
    NoOpenClaimError,
    get_claim_status,
)

_MISSING_IDENTIFIER_PROMPT = (
    "What's your claim number, or if you don't have it handy, your policy number?"
)
_IDENTIFIER_SLOT = "claim_or_policy_number"


def check_claim_status(state: AgentState) -> dict[str, Any]:
    filled = state.get("filled_slots", {})
    claim_number = filled.get("claim_number")
    policy_number = filled.get("policy_number")

    if not claim_number and not policy_number:
        if state.get("active_slot") == _IDENTIFIER_SLOT:
            # asked last turn, still nothing -- a no-match, defer to the shared repair path.
            return {"active_slot": _IDENTIFIER_SLOT, "response_text": None}
        return {"active_slot": _IDENTIFIER_SLOT, "response_text": _MISSING_IDENTIFIER_PROMPT}

    try:
        claim = get_claim_status(claim_number=claim_number, policy_number=policy_number)
    except NoOpenClaimError:
        return {
            "active_slot": None,
            "response_text": "I don't see an open claim on that policy right now.",
        }
    except ClaimNotFoundError:
        return {
            "active_slot": None,
            "response_text": "I couldn't find a claim with that number -- could you double check it?",
        }

    return {
        "active_slot": None,
        "response_text": f"Your claim {claim.claim_number} is currently {claim.status}.",
    }
