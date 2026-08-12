"""`RentalTowingEntitlement` -- the compound RAG+tool case, `DIALOGUE-POLICIES.md` §3. Both the retrieved
policy terms and the claim-status tool result are required in context before generation runs (§3 step 3) --
this node never calls `generate_response` with only one of them present.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState, NodeFn
from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller, generate_response
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, Embedder
from fnol_voice_agent.knowledge.retrieve import search
from fnol_voice_agent.mcp.claims_server import (
    ClaimNotFoundError,
    NoOpenClaimError,
    RentalStatusUnavailableError,
    get_claim_status,
    get_rental_status,
)

_MISSING_TYPE_PROMPT = "Is this about rental, or towing?"
_TYPE_SLOT = "entitlement_type"
_ABSTENTION = "I don't have that in your policy -- let me get you to someone who does."

# PROMPT-REGISTRY.md §3.2, verbatim (including the redundancy fix from the real Phase 4 verification).
_RENTAL_SYSTEM_PROMPT = (
    "Answer using both the policy terms and the claim status below -- both are required, and an answer "
    "that uses only one of them is wrong even if it sounds correct. State whether the entitlement "
    "applies, then state the concrete number that matters to the caller right now (days/dollars "
    "remaining for rental; covered or not for towing). Two to three sentences. Do not explain the "
    "endorsement's general mechanics beyond what answers this caller's situation -- they asked about "
    "their claim, not the product in the abstract. Do not restate the same fact in a second sentence "
    "using different words -- each sentence must add new information. If the claim status tool call did "
    "not return a resolvable claim, say so plainly and state the policy terms only, without implying the "
    "entitlement is currently active."
)


def make_rental_towing_node(
    *,
    store: DynamoVectorStore,
    embedder: Embedder,
    bedrock_caller: BedrockConverseCaller | None = None,
) -> NodeFn:
    def rental_towing_entitlement(state: AgentState) -> dict[str, Any]:
        filled = state.get("filled_slots", {})
        entitlement_type = filled.get(_TYPE_SLOT)
        policy_number = filled.get("policy_number")
        claim_number = filled.get("claim_number")

        if not entitlement_type:
            if state.get("active_slot") == _TYPE_SLOT:
                return {"active_slot": _TYPE_SLOT, "response_text": None}
            return {"active_slot": _TYPE_SLOT, "response_text": _MISSING_TYPE_PROMPT}

        results = search(f"{entitlement_type} entitlement", store, embedder, top_k=3)
        if not results:
            return {"active_slot": None, "response_text": _ABSTENTION}
        retrieved_text = "\n".join(r.text for r in results)

        claim_status_text: str
        try:
            claim = get_claim_status(claim_number=claim_number, policy_number=policy_number)
            if entitlement_type == "rental":
                try:
                    rental = get_rental_status(claim.claim_number)
                    claim_status_text = (
                        f"claim {claim.claim_number}: days_used={rental.days_used}, "
                        f"days_remaining={rental.days_remaining}, "
                        f"amount_remaining_cad={rental.amount_remaining_cad}"
                    )
                except RentalStatusUnavailableError:
                    claim_status_text = f"claim {claim.claim_number}: no rental status recorded"
            else:
                claim_status_text = f"claim {claim.claim_number}: status={claim.status}"
        except (ClaimNotFoundError, NoOpenClaimError):
            claim_status_text = "no resolvable claim found for this caller"

        user_message = (
            f"Retrieved policy text:\n{retrieved_text}\n\n"
            f"Claim status tool result: {claim_status_text}\n\n"
            f"Caller's question: \"Is {entitlement_type} covered, and what's the status on my claim?\""
        )
        answer = generate_response(_RENTAL_SYSTEM_PROMPT, user_message, caller=bedrock_caller)
        return {"active_slot": None, "response_text": answer}

    return rental_towing_entitlement
