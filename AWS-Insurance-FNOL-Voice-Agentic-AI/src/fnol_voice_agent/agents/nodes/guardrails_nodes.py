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
from fnol_voice_agent.observability.guardrail_metrics import emit_guardrail_usage

_OUTPUT_BLOCKED_FALLBACK = (
    "I'm sorry, I'm not able to share that -- let me connect you with someone who can help."
)


def make_guardrails_input_node(*, client: GuardrailClient | None = None) -> NodeFn:
    guardrail = client or MockGuardrailClient()

    def guardrails_input_check(state: AgentState) -> dict[str, Any]:
        result = guardrail.apply_guardrail("INPUT", state.get("turn_input", ""))
        # Phase 11 Stage B1: emitted before the discard below, so `.usage` has a consumer. See
        # `observability/guardrail_metrics.py` for why this is a log line and not a custom metric, and
        # why it fires even when `.usage` is empty (every call today, via `MockGuardrailClient`).
        emit_guardrail_usage("INPUT", result.usage, blocked=result.blocked, masked=result.masked)
        # `result.output_text` is deliberately NOT written back to `turn_input`, and the reason is a
        # `C1` decision rather than an oversight. If Bedrock ever masks on the input path, forwarding
        # the masked text would send L2 a turn with spans replaced by `{PLACEHOLDER}` -- and L2 is the
        # only detector for 73% of indirect injury phrasing. Recall is non-tradeable (`C1`), so the
        # detector sees the raw turn and the residual exposure is carried in `NOT-FIXED.md`.
        #
        # Currently moot, measured rather than assumed: Bedrock does not evaluate the
        # sensitive-information policy on `source="INPUT"` at all. Verified live against `zl5ppnyorwd2`
        # v2 at Stage 8 -- an email, a phone number and a `PY####` policy number all returned
        # `sensitiveInformationPolicyUnits: 0` and `action: NONE` on INPUT while masking correctly on
        # OUTPUT. So the input-side PII anonymisation `main.tf` describes does not run, and this line
        # is the coupling that will matter if AWS ever makes it run.
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
        # Phase 11 Stage B1: emitted once per real call, after the authority short-circuit above (which
        # never calls the guardrail at all -- `test_the_authority_check_runs_before_the_guardrail_and_wins`
        # asserts zero guardrail calls in that branch, so zero emissions there is the correct behaviour,
        # not a gap).
        emit_guardrail_usage(
            "OUTPUT", result_gr.usage, blocked=result_gr.blocked, masked=result_gr.masked
        )
        if result_gr.blocked:
            return {"guardrail_output_blocked": True, "response_text": _OUTPUT_BLOCKED_FALLBACK}
        if result_gr.masked:
            # A mask is not a refusal. Until Stage 8 this branch did not exist and `blocked` was true
            # for any intervention, so a masked line became `_OUTPUT_BLOCKED_FALLBACK` -- the agent
            # refusing to say a claim number it had just correctly looked up, and promising a handoff
            # on the way out. Forwarding the masked text is strictly better than that in every case.
            #
            # It is still not RIGHT, and the remaining half is not a code fix: the guardrail masks the
            # caller's own claim number, policy number and plate back to them, so this branch yields
            # "Your claim number is {claim_number}". Removing those four regexes is a change to a
            # provisioned, individually-gated resource. Carried to `docs/phase7/NOT-FIXED.md`.
            return {"guardrail_output_blocked": False, "response_text": result_gr.output_text}
        return {"guardrail_output_blocked": False}

    return guardrails_output_check
