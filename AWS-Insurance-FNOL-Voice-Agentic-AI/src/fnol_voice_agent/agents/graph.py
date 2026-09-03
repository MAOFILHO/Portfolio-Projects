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
                    -[UpdateContactInfo]--------------------> update_contact_info -+-[response_text]--> END (ADR-017 3-coarse)
                                                                                     -[no response_text]--> handle_no_match_or_barge_in -> END
```

**`ADR-017` (direction 3-coarse, ACCEPTED).** `update_contact_info` is the one named exception to
`guardrails_output_check`'s dominance over the five intent nodes above: its `response_text` goes straight
to `END`, never through the OUTPUT `ApplyGuardrail` call the other four still get. This is deliberate, not
a gap -- see the ADR for why (the node never calls an LLM, so the added exposure is bounded to
template-plus-slot-value text; `EMAIL`/`PHONE` `ANONYMIZE` was making its own confirmation readback
unconfirmable, `D121`). `assert_dominates_except`, called below alongside `assert_dominates`, asserts both
halves of this at construction time: the other four nodes still dominate through `guardrails_output_check`,
and `update_contact_info` still bypasses it -- a regression in either direction fails the build, not a test
that happens to run.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph

from fnol_voice_agent.agents.graph_structure import assert_dominates, assert_dominates_except
from fnol_voice_agent.aws.split_router import assert_detector_dominates
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
from fnol_voice_agent.agents.state import AgentState, EscalationRecord
from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller
from fnol_voice_agent.guardrails.client import GuardrailClient
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, Embedder
from fnol_voice_agent.mcp.escalation_server import initiate_escalation
from fnol_voice_agent.observability import tracing

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

# `ADR-017`. The five nodes that feed `guardrails_output_check` -- previously all wired through one shared
# `_after_intent_node` conditional-edge registration below; `update_contact_info` now gets its own
# (`_after_update_contact_info`) so it can bypass the OUTPUT guardrail specifically. Exported (not
# module-private) because `redteam/readback_probe.py`'s site-coverage check (ADR-017 condition part 3)
# reads these two constants directly rather than re-deriving or re-typing the node list a second place --
# a node added here without updating that probe's coverage set fails `make redteam` loudly instead of
# silently going unchecked, per the same instruction that produced `assert_dominates_except`.
OUTPUT_GUARDRAIL_SOURCES: tuple[str, ...] = (
    "file_auto_claim",
    "check_claim_status",
    "coverage_question",
    "rental_towing_entitlement",
    "update_contact_info",
)
OUTPUT_GUARDRAIL_EXCEPTIONS: frozenset[str] = frozenset({"update_contact_info"})

_GUARDRAIL_INPUT_BLOCKED_RESPONSE = (
    "I'm not able to help with that -- let me connect you with someone who can."
)


def _guardrail_blocked_response(state: AgentState) -> dict[str, Any]:
    # `D140`/`OI58`: this node used to speak `_GUARDRAIL_INPUT_BLOCKED_RESPONSE`'s transfer promise with
    # no `EscalationRecord` -- `D89`'s own INPUT-block path, and the same class of gap as `guardrails_
    # nodes.py`'s OUTPUT-block branch and `update_contact_info.py`'s confirm-ceiling branch. Called
    # directly (this node already receives the full `AgentState`, `contact_id` included) rather than
    # routed through `repair.py`'s shared `handle_no_match_or_barge_in`, which is keyed to no-match/
    # barge-in retry counting specifically and has no notion of an INPUT-guardrail block at all.
    result = initiate_escalation(
        contact_id=state.get("contact_id", "unknown"),
        triggering_layer="capability",
        context={
            "filled_slots": state.get("filled_slots", {}),
            "turn_input": state.get("turn_input", ""),
            "reason": "input_guardrail_blocked",
        },
    )
    escalation: EscalationRecord = {
        "contact_id": result.contact_id,
        "triggering_layer": result.triggering_layer,
        "route": 3,
        "reason": "input_guardrail_blocked",
        "context": result.context,
    }
    return {"response_text": _GUARDRAIL_INPUT_BLOCKED_RESPONSE, "escalation": escalation}


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


def _after_update_contact_info(state: AgentState) -> str:
    """`ADR-017` direction 3-coarse's routing edit. Same "no response_text yet" fallback every other
    intent node gets (mid multi-turn slot collection still needs `handle_no_match_or_barge_in`, same as
    `_after_intent_node`) -- the only difference is the destination for a real response_text: straight to
    `END`, never `guardrails_output_check`. `update_contact_info_node` never calls an LLM (every branch is
    a fixed string or an f-string over a slot value/enum/exception string), which is the fact the ADR's
    Round 2 Q1 leans on to bound this bypass's exposure.
    """
    return "end" if state.get("response_text") else "handle_no_match_or_barge_in"


def _add_traced_node(
    builder: StateGraph[AgentState, Any, Any, Any],
    name: str,
    fn: Callable[[AgentState], dict[str, Any]],
) -> None:
    """`ADR-018` criterion 3 (a span per LangGraph node) -- ONE seam here, not twelve edits to
    `agents/nodes/*.py`. `fn` is treated as an opaque callable: a plain top-level function
    (`l1_safety_check`, `check_claim_status`, ...) and a closure returned by a `make_*_node` factory
    (`make_route_and_classify_node(...)`, ...) both already coexist among the twelve call sites below, and
    this works uniformly for either shape -- it never inspects `fn` beyond calling it.

    `wrapper`'s signature is written out as a literal, concrete `Callable[[AgentState], dict[str, Any]]`
    (a real nested `def`, not something routed through a `TypeVar`-generic decorator) on purpose: mypy's
    `StateGraph.add_node` overloads resolve cleanly against a plain top-level-shaped function the same way
    they did before this change, and do NOT resolve against a value typed only through the `NodeFn`
    Callable alias -- which is exactly what used to need the `# type: ignore[arg-type]` comments on five of
    these twelve registrations. Routing every node through this one concrete `wrapper` def removes that
    friction for all twelve, not just the five that had it named -- confirmed by `make typecheck` staying
    clean with every one of those ignores removed, not assumed.
    """

    def wrapper(state: AgentState) -> dict[str, Any]:
        with tracing.traced_span(f"fnol.node.{name}") as span:
            tracing.set_span_attribute(span, "fnol.node.name", name)
            return fn(state)

    builder.add_node(name, wrapper)


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

    # `ADR-018` criterion 3: every node registration goes through `_add_traced_node`, which wraps `fn` in
    # a `fnol.node.<name>` span -- see that function's own docstring, including why this removed the
    # `# type: ignore[arg-type]` comments the five factory-returned nodes used to need here.
    _add_traced_node(builder, "l1_safety_check", l1_safety_check)
    _add_traced_node(
        builder, "guardrails_input_check", make_guardrails_input_node(client=guardrail_client)
    )
    _add_traced_node(builder, "guardrail_blocked_response", _guardrail_blocked_response)
    _add_traced_node(
        builder, "route_and_classify", make_route_and_classify_node(caller=bedrock_caller)
    )
    _add_traced_node(builder, "injury_escalation", injury_escalation)
    _add_traced_node(builder, "handle_no_match_or_barge_in", handle_no_match_or_barge_in)
    _add_traced_node(builder, "file_auto_claim", file_auto_claim)
    _add_traced_node(builder, "check_claim_status", check_claim_status)
    _add_traced_node(
        builder,
        "coverage_question",
        make_coverage_question_node(
            store=vector_store, embedder=embedder, bedrock_caller=bedrock_caller
        ),
    )
    _add_traced_node(
        builder,
        "rental_towing_entitlement",
        make_rental_towing_node(
            store=vector_store, embedder=embedder, bedrock_caller=bedrock_caller
        ),
    )
    _add_traced_node(builder, "update_contact_info", update_contact_info_node)
    _add_traced_node(
        builder, "guardrails_output_check", make_guardrails_output_node(client=guardrail_client)
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
    # `ADR-017`: `update_contact_info` is excluded from this loop -- OUTPUT_GUARDRAIL_SOURCES minus
    # OUTPUT_GUARDRAIL_EXCEPTIONS -- and wired separately below with its own conditional-edge function,
    # so its bypass of `guardrails_output_check` is a distinct routing registration, not a branch inside
    # a shared one. That distinctness is what makes `assert_dominates_except`'s one-hop check meaningful.
    for intent_node in OUTPUT_GUARDRAIL_SOURCES:
        if intent_node in OUTPUT_GUARDRAIL_EXCEPTIONS:
            continue
        builder.add_conditional_edges(
            intent_node,
            _after_intent_node,
            {
                "guardrails_output_check": "guardrails_output_check",
                "handle_no_match_or_barge_in": "handle_no_match_or_barge_in",
            },
        )
    builder.add_conditional_edges(
        "update_contact_info",
        _after_update_contact_info,
        {
            "end": END,
            "handle_no_match_or_barge_in": "handle_no_match_or_barge_in",
        },
    )
    builder.add_edge("guardrails_output_check", END)

    assert_dominates(builder, "l1_safety_check")
    # `ADR-014` I3, checked at construction time next to L1's graph-position check rather than only
    # in CI. The two guard the same property at two layers: L1 must dominate the graph, and the
    # split detector's verdict must not be overridable by the classifier that runs beside it. The
    # realistic failure for both is a later edit -- a shortcut that skips escalation when some other
    # signal looks confident -- and a check that only runs in a test does not stop that edit
    # reaching a caller. Cheap: four enumerated combinations, no model call, no I/O.
    assert_detector_dominates()
    # `ADR-017` condition part 2 -- Round 2 Q2's surviving half: the graph must assert the invariant
    # direction 3-coarse creates (guardrails_output_check dominates every intent node's response_text
    # EXCEPT update_contact_info's, which must NOT reach it) rather than leave it to a reader. There was
    # no `assert_dominates(builder, "guardrails_output_check")` before this ADR and never had been --
    # this is the property's first assertion, not a loosening of one that previously existed.
    assert_dominates_except(
        builder,
        "guardrails_output_check",
        OUTPUT_GUARDRAIL_SOURCES,
        exceptions=OUTPUT_GUARDRAIL_EXCEPTIONS,
    )

    return builder.compile(checkpointer=checkpointer)
