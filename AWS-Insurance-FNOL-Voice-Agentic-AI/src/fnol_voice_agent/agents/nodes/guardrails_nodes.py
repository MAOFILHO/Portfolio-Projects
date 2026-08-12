"""Guardrails input/output nodes -- `ADR-010`'s decoupled `ApplyGuardrail` steps 2 and 4, as their own
explicit graph nodes, never bolted onto a model call.

The output node runs **two** checks, in this order (`ADR-015`):

1. `agents/authority.check_authority` -- deterministic, free, no I/O. Rejects a line asserting an
   adjudication, a settlement sum, or a waiver of this caller's deductible, per
   `DIALOGUE-POLICIES.md` §2 step 4.
2. The Bedrock guardrail's `ApplyGuardrail` on `OUTPUT`.

Deterministic first, because it costs nothing and a hit means the billable call never has to be made.
The two are not redundant: the guardrail evaluates content policy (violence, PII, denied topics) and has
no notion of what this agent is *authorised* to say -- *"your claim has been approved for $18,000"*
violates no content policy and passed the real guardrail in Phase 7's red-team run.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.authority import ELIGIBILITY_DEFLECTION, check_authority
from fnol_voice_agent.agents.state import AgentState, EscalationRecord, NodeFn
from fnol_voice_agent.guardrails.client import GuardrailClient, MockGuardrailClient
from fnol_voice_agent.mcp.escalation_server import initiate_escalation

_OUTPUT_BLOCKED_FALLBACK = (
    "I'm sorry, I'm not able to share that -- let me connect you with someone who can help."
)


def make_guardrails_input_node(*, client: GuardrailClient | None = None) -> NodeFn:
    guardrail = client or MockGuardrailClient()

    def guardrails_input_check(state: AgentState) -> dict[str, Any]:
        result = guardrail.apply_guardrail("INPUT", state.get("turn_input", ""))
        return {"guardrail_input_blocked": result.blocked}

    return guardrails_input_check


def make_guardrails_output_node(*, client: GuardrailClient | None = None) -> NodeFn:
    guardrail = client or MockGuardrailClient()

    def guardrails_output_check(state: AgentState) -> dict[str, Any]:
        candidate = state.get("response_text") or ""

        violation = check_authority(candidate)
        if violation:
            # A real escalation record, not just a replacement string. The deflection promises a
            # handoff, and `docs/phase7/NOT-FIXED.md`'s `D43` is this project's own instance of a
            # blocked turn promising a transfer that never happens -- reproducing that here would be
            # making the same mistake with the fix for a different one.
            #
            # Route 3 / "capability", matching `DIALOGUE-POLICIES.md` §8's existing row for the
            # eligibility-amount sub-question: this is the same policy, enforced at a second point,
            # so it is emphatically not a new escalation route.
            result = initiate_escalation(
                contact_id=state.get("contact_id", "unknown"),
                triggering_layer="capability",
                context={
                    "filled_slots": state.get("filled_slots", {}),
                    "suppressed_response": candidate,
                    "authority_category": violation.category.value,
                    "matched": violation.matched,
                },
            )
            escalation: EscalationRecord = {
                "contact_id": result.contact_id,
                "triggering_layer": result.triggering_layer,
                "route": 3,
                "reason": f"authority:{violation.category.value}",
                "context": result.context,
            }
            return {
                "authority_violation": violation.category.value,
                "guardrail_output_blocked": False,
                "response_text": ELIGIBILITY_DEFLECTION,
                "escalation": escalation,
            }

        result_gr = guardrail.apply_guardrail("OUTPUT", candidate)
        if result_gr.blocked:
            return {"guardrail_output_blocked": True, "response_text": _OUTPUT_BLOCKED_FALLBACK}
        return {"guardrail_output_blocked": False}

    return guardrails_output_check
