"""Guardrails input/output nodes -- `ADR-010`'s decoupled `ApplyGuardrail` steps 2 and 4, as their own
explicit graph nodes, never bolted onto a model call.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState, NodeFn
from fnol_voice_agent.guardrails.client import GuardrailClient, MockGuardrailClient

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
        result = guardrail.apply_guardrail("OUTPUT", state.get("response_text", ""))
        if result.blocked:
            return {"guardrail_output_blocked": True, "response_text": _OUTPUT_BLOCKED_FALLBACK}
        return {"guardrail_output_blocked": False}

    return guardrails_output_check
