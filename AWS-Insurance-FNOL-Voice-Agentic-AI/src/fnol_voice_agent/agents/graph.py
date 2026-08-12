"""Graph assembly (Stage 7, `docs/phase5/BUILD-PLAN.md`) -- wires Stage 6's nodes into the full per-turn
pipeline `DIALOGUE-POLICIES.md` §1 specifies, with `graph_structure.assert_dominates` enforcing §1/`ADR-010`'s
ordering **at construction time**: `build_graph()` raises `GraphStructureError` and never returns a usable
graph if any node is reachable from `START` without passing through `l1_safety_check` first. This is checked
again, independently, by `tests/unit/test_graph_integration.py`'s own call to `build_graph()` -- if a future
edit to this file broke dominance, both the import (via this module's own assertion) and that test fail, not
one silently.

**Pipeline, as edges (matches `DIALOGUE-POLICIES.md` §1 exactly):**

```
START -> l1_safety_check -[safety]-> injury_escalation -> END
                          -[clear]-> guardrails_input_check -[blocked]-> guardrail_blocked_response -> END
                                                             -[clear]--> route_and_classify
route_and_classify -[safety_flag]-------------------------> injury_escalation -> END
                    -[ambiguous/out-of-scope/low-confidence]-> handle_no_match_or_barge_in -> END
                    -[FileAutoClaim]----------------------> file_auto_claim -+
                    -[CheckClaimStatus]--------------------> check_claim_status -+
                    -[CoverageQuestion]--------------------> coverage_question -+-[response_text]--> guardrails_output_check -> END
                    -[RentalTowingEntitlement]--------------> rental_towing_entitlement -+           -[no response_text]--> handle_no_match_or_barge_in -> END
                    -[UpdateContactInfo]--------------------> update_contact_info -+
```
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph

from fnol_voice_agent.agents.graph_structure import assert_dominates
from fnol_voice_agent.agents.nodes.check_claim_status import check_claim_status
from fnol_voice_agent.agents.nodes.coverage_question import make_coverage_question_node
from fnol_voice_agent.agents.nodes.file_auto_claim import file_auto_claim
from fnol_voice_agent.agents.nodes.guardrails_nodes import (
    make_guardrails_input_node,
    make_guardrails_output_node,
)
from fnol_voice_agent.agents.nodes.injury_escalation import injury_escalation
from fnol_voice_agent.agents.nodes.rental_towing import make_rental_towing_node
from fnol_voice_agent.agents.nodes.repair import handle_no_match_or_barge_in
from fnol_voice_agent.agents.nodes.routing import make_route_and_classify_node
from fnol_voice_agent.agents.nodes.safety import l1_safety_check
from fnol_voice_agent.agents.nodes.update_contact_info import update_contact_info_node
from fnol_voice_agent.agents.state import AgentState
from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller
from fnol_voice_agent.guardrails.client import GuardrailClient
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, Embedder

# Engineering default, not a tuned value (Phase 6 owns tuning against real evals) -- below this, the
# merged router's intent classification is treated as inconclusive, same as an Ambiguous/OutOfScope
# result, and routed to the shared repair path (INTENT-TAXONOMY.md §3's disambiguation policy).
LOW_CONFIDENCE_THRESHOLD = 0.5

_INCONCLUSIVE_INTENTS = {"Ambiguous", "OutOfScope"}

_INTENT_TO_NODE = {
    "FileAutoClaim": "file_auto_claim",
    "CheckClaimStatus": "check_claim_status",
    "CoverageQuestion": "coverage_question",
    "RentalTowingEntitlement": "rental_towing_entitlement",
    "UpdateContactInfo": "update_contact_info",
    "InjuryEscalation": "injury_escalation",
}

_GUARDRAIL_INPUT_BLOCKED_RESPONSE = (
    "I'm not able to help with that -- let me connect you with someone who can."
)


def _guardrail_blocked_response(_state: AgentState) -> dict[str, Any]:
    return {"response_text": _GUARDRAIL_INPUT_BLOCKED_RESPONSE}


def _after_l1(state: AgentState) -> str:
    return "injury_escalation" if state.get("l1_safety_flag") else "guardrails_input_check"


def _after_guardrails_input(state: AgentState) -> str:
    return (
        "guardrail_blocked_response"
        if state.get("guardrail_input_blocked")
        else "route_and_classify"
    )


def _after_routing(state: AgentState) -> str:
    if state.get("safety_flag"):  # D15 union: L2 catching what L1 missed
        return "injury_escalation"
    intent = state.get("intent")
    confidence = state.get("intent_confidence", 0.0)
    inconclusive = intent in _INCONCLUSIVE_INTENTS or confidence < LOW_CONFIDENCE_THRESHOLD
    if inconclusive:
        # Covers both a normal low-confidence/ambiguous classification AND an inconclusive barge-in
        # (DIALOGUE-POLICIES.md §6.2) -- the routing decision is identical either way; repair.py itself
        # reads state["is_barge_in"] only to choose which line to speak, never to change where it's routed.
        return "handle_no_match_or_barge_in"
    return _INTENT_TO_NODE.get(intent or "", "handle_no_match_or_barge_in")


def _after_intent_node(state: AgentState) -> str:
    return (
        "guardrails_output_check" if state.get("response_text") else "handle_no_match_or_barge_in"
    )


def build_graph(
    *,
    vector_store: DynamoVectorStore,
    embedder: Embedder,
    bedrock_caller: BedrockConverseCaller | None = None,
    guardrail_client: GuardrailClient | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[AgentState, Any, Any, Any]:
    """Builds and compiles the full agent graph. `vector_store`/`embedder` are required, not defaulted --
    `nodes/coverage_question.py`'s docstring explains why (no real DynamoDB table exists in Phase 5, so a
    silent default would return "nothing found" for every real query once one does). `bedrock_caller`/
    `guardrail_client` default to `None`, matching Stage 4/5's own postures: `None` for `bedrock_caller`
    means a real Bedrock client is constructed lazily on first real call (fine -- Bedrock inference is
    covered by the standing cost cap); `None` for `guardrail_client` means `MockGuardrailClient` (fine --
    no real Guardrail resource exists yet regardless, per `docs/phase5/BUILD-PLAN.md` §2).

    Raises `GraphStructureError` if `l1_safety_check` does not dominate the resulting graph -- this can
    only happen from a bug introduced in this function's own edges, since every node factory above is a
    plain function/closure with no way to add an edge itself.
    """
    builder: StateGraph[AgentState, Any, Any, Any] = StateGraph(AgentState)

    # mypy note: LangGraph's `add_node` overloads resolve cleanly against a plain top-level `def`, but not
    # against a value typed through the `NodeFn` Callable alias (what every `make_*_node` factory returns)
    # -- a typing-overload friction, not a runtime one: every one of these closures is exercised end-to-end
    # by tests/unit/test_graph_integration.py against the real compiled graph. `# type: ignore[arg-type]`
    # on each factory-returned node, not on the plain-function ones below, which need no ignore.
    builder.add_node("l1_safety_check", l1_safety_check)
    builder.add_node(
        "guardrails_input_check",
        make_guardrails_input_node(client=guardrail_client),  # type: ignore[arg-type]
    )
    builder.add_node(
        "guardrail_blocked_response", _guardrail_blocked_response  # type: ignore[arg-type]
    )
    builder.add_node(
        "route_and_classify",
        make_route_and_classify_node(caller=bedrock_caller),  # type: ignore[arg-type]
    )
    builder.add_node("injury_escalation", injury_escalation)
    builder.add_node("handle_no_match_or_barge_in", handle_no_match_or_barge_in)
    builder.add_node("file_auto_claim", file_auto_claim)
    builder.add_node("check_claim_status", check_claim_status)
    builder.add_node(
        "coverage_question",
        make_coverage_question_node(  # type: ignore[arg-type]
            store=vector_store, embedder=embedder, bedrock_caller=bedrock_caller
        ),
    )
    builder.add_node(
        "rental_towing_entitlement",
        make_rental_towing_node(  # type: ignore[arg-type]
            store=vector_store, embedder=embedder, bedrock_caller=bedrock_caller
        ),
    )
    builder.add_node("update_contact_info", update_contact_info_node)
    builder.add_node(
        "guardrails_output_check",
        make_guardrails_output_node(client=guardrail_client),  # type: ignore[arg-type]
    )

    builder.add_edge(START, "l1_safety_check")
    builder.add_conditional_edges(
        "l1_safety_check",
        _after_l1,
        {
            "injury_escalation": "injury_escalation",
            "guardrails_input_check": "guardrails_input_check",
        },
    )
    builder.add_conditional_edges(
        "guardrails_input_check",
        _after_guardrails_input,
        {
            "guardrail_blocked_response": "guardrail_blocked_response",
            "route_and_classify": "route_and_classify",
        },
    )
    builder.add_edge("guardrail_blocked_response", END)
    builder.add_conditional_edges(
        "route_and_classify",
        _after_routing,
        {
            "injury_escalation": "injury_escalation",
            "handle_no_match_or_barge_in": "handle_no_match_or_barge_in",
            "file_auto_claim": "file_auto_claim",
            "check_claim_status": "check_claim_status",
            "coverage_question": "coverage_question",
            "rental_towing_entitlement": "rental_towing_entitlement",
            "update_contact_info": "update_contact_info",
        },
    )
    builder.add_edge("injury_escalation", END)
    builder.add_edge("handle_no_match_or_barge_in", END)
    for intent_node in (
        "file_auto_claim",
        "check_claim_status",
        "coverage_question",
        "rental_towing_entitlement",
        "update_contact_info",
    ):
        builder.add_conditional_edges(
            intent_node,
            _after_intent_node,
            {
                "guardrails_output_check": "guardrails_output_check",
                "handle_no_match_or_barge_in": "handle_no_match_or_barge_in",
            },
        )
    builder.add_edge("guardrails_output_check", END)

    assert_dominates(builder, "l1_safety_check")

    return builder.compile(checkpointer=checkpointer)
