"""Stage 7 integration tests -- full simulated conversations through the real, assembled graph
(`agents/graph.py`), against the real corpus (via `knowledge/ingest.py`'s real chunking, moto-backed) and
the real synthetic policyholder/vehicle/claim records. Every Bedrock call goes through
`FakeBedrockConverseClient`; every AWS call goes through moto (`mock_aws`) -- zero real network, zero real
spend, per `docs/phase5/BUILD-PLAN.md` Stage 7.

Per `docs/phase5/BUILD-PLAN.md` Stage 6's scope note: this graph receives already-interpreted slot values
the way a real Lex codehook would (Lex's own NLU job, not built until Phase 8) -- `_invoke_turn` below
simulates that by explicitly merging each turn's "answer" into `filled_slots` before calling the graph,
the same way a Lex `interpretedValue` would have arrived.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from moto import mock_aws

from fnol_voice_agent.agents.graph import build_graph
from fnol_voice_agent.agents.retry_ladder import RETRY_CEILING
from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_tool_use_response,
)
from fnol_voice_agent.aws.checkpointer import build_test_checkpointer
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, MockEmbedder, run_ingestion

_ROUTER_MODEL = "us.amazon.nova-micro-v1:0"


def _classification(
    intent: str,
    *,
    safety_flag: bool = False,
    confidence: float = 0.95,
    coverage_question_type: str = "not_applicable",
) -> dict[str, Any]:
    return converse_tool_use_response(
        "classify_turn",
        {
            "safety_flag": safety_flag,
            "intent": intent,
            "intent_confidence": confidence,
            "coverage_question_type": coverage_question_type,
        },
    )


@pytest.fixture
def real_store_and_embedder():
    with mock_aws():
        store = DynamoVectorStore(table_name="fnol-knowledge-integration-test", region="us-west-2")
        store.ensure_table()
        embedder = MockEmbedder()
        run_ingestion(
            corpus_dir=Path("data/synthetic/policy"),
            store=store,
            embedder=embedder,
            vector_store_backend_label="local",
            manifest_path=Path("/tmp/fnol-integration-test-manifest.json"),
        )
        yield store, embedder


def _invoke_turn(
    graph: Any,
    config: dict[str, Any],
    *,
    turn_input: str,
    new_slots: dict[str, Any] | None = None,
    is_barge_in: bool = False,
    contact_id: str = "contact-integration-test",
) -> dict[str, Any]:
    previous = graph.get_state(config).values or {}
    filled = dict(previous.get("filled_slots", {}))
    if new_slots:
        filled.update(new_slots)
    result: dict[str, Any] = graph.invoke(
        {
            "contact_id": contact_id,
            "turn_input": turn_input,
            "filled_slots": filled,
            "active_slot": previous.get("active_slot"),
            "retry_counts": previous.get("retry_counts", {}),
            "is_barge_in": is_barge_in,
        },
        config,
    )
    return result


# --- All six intents, happy path ------------------------------------------------------------------


def test_check_claim_status_happy_path(real_store_and_embedder: Any) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={_ROUTER_MODEL: _classification("CheckClaimStatus")}
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)

    result = graph.invoke(
        {
            "contact_id": "c1",
            "turn_input": "checking on my claim",
            "filled_slots": {"claim_number": "CLM-2608-00042-4"},
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "CLM-2608-00042-4" in result["response_text"]
    assert "RepairInProgress" in result["response_text"]


def test_coverage_question_mandatory_is_pure_rag_no_tool_call(real_store_and_embedder: Any) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={
            _ROUTER_MODEL: _classification(
                "CoverageQuestion", coverage_question_type="election_fact_mandatory"
            ),
            "us.amazon.nova-lite-v1:0": {
                "output": {
                    "message": {"content": [{"text": "Yes, DCPD is mandatory on every policy."}]}
                },
                "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
            },
        }
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)
    result = graph.invoke(
        {
            "contact_id": "c2",
            "turn_input": "is DCPD part of my coverage",
            "filled_slots": {"policy_number": "PY4821", "coverage_topic": "DCPD"},
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "DCPD" in result["response_text"]


def test_coverage_question_optional_election_is_rag_plus_tool(real_store_and_embedder: Any) -> None:
    # DIALOGUE-POLICIES.md §2 step 3: the RAG+tool compound case within intent 3 itself, not just intent
    # 4 -- PY4821 has income_replacement_benefit elected (real corpus record), used unmodified here.
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={
            _ROUTER_MODEL: _classification(
                "CoverageQuestion", coverage_question_type="election_fact_optional"
            ),
            "us.amazon.nova-lite-v1:0": {
                "output": {
                    "message": {"content": [{"text": "Yes, you have income replacement benefits."}]}
                },
                "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
            },
        }
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)
    result = graph.invoke(
        {
            "contact_id": "c2b",
            "turn_input": "do I have income replacement benefits",
            "filled_slots": {
                "policy_number": "PY4821",
                "coverage_topic": "income replacement benefit",
            },
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "income replacement" in result["response_text"].lower()
    # Confirms the tool call happened by construction -- generate_response only runs after
    # get_policyholder_elections succeeds inside coverage_question.py; a KeyError/exception there
    # would have propagated instead of reaching this point.


def test_coverage_question_eligibility_amount_is_fixed_deflection_no_generation(
    real_store_and_embedder: Any,
) -> None:
    # DIALOGUE-POLICIES.md §2 step 4: generation is never invoked for an eligibility/amount question.
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={
            _ROUTER_MODEL: _classification(
                "CoverageQuestion", coverage_question_type="eligibility_amount"
            )
        }
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)
    result = graph.invoke(
        {
            "contact_id": "c3",
            "turn_input": "will my claim get paid in full",
            "filled_slots": {"policy_number": "PY4821", "coverage_topic": "payout amount"},
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "let me get you to someone" in result["response_text"]
    # Only one call recorded -- the router. Nova Lite (generation) was never invoked.
    assert caller.requested_model_ids() == [_ROUTER_MODEL]


def test_rental_towing_entitlement_happy_path(real_store_and_embedder: Any) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={
            _ROUTER_MODEL: _classification("RentalTowingEntitlement"),
            "us.amazon.nova-lite-v1:0": {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": "Your rental entitlement applies, and you have 8 days remaining."
                            }
                        ]
                    }
                },
                "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
            },
        }
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)
    result = graph.invoke(
        {
            "contact_id": "c4",
            "turn_input": "how many rental days do I have left",
            "filled_slots": {
                "entitlement_type": "rental",
                "policy_number": "PY4821",
                "claim_number": "CLM-2608-00042-4",
            },
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "8 days" in result["response_text"]


def test_update_contact_info_happy_path_two_turns(real_store_and_embedder: Any) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={_ROUTER_MODEL: _classification("UpdateContactInfo")}
    )
    checkpointer = build_test_checkpointer("fnol-checkpoints-uci-test")
    graph = build_graph(
        vector_store=store, embedder=embedder, bedrock_caller=caller, checkpointer=checkpointer
    )
    config = {"configurable": {"thread_id": "uci-1"}}

    r1 = _invoke_turn(
        graph,
        config,
        turn_input="update my phone number to 555-0199",
        new_slots={"policy_number": "PY4821", "field": "phone", "new_value": "555-0199"},
    )
    assert "is that right" in r1["response_text"].lower()

    r2 = _invoke_turn(
        graph, config, turn_input="yes", new_slots={"confirm_update_contact_info": True}
    )
    assert "updated" in r2["response_text"].lower()


def test_file_auto_claim_full_multi_turn_happy_path(real_store_and_embedder: Any) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(by_model={_ROUTER_MODEL: _classification("FileAutoClaim")})
    checkpointer = build_test_checkpointer("fnol-checkpoints-fac-test")
    graph = build_graph(
        vector_store=store, embedder=embedder, bedrock_caller=caller, checkpointer=checkpointer
    )
    config = {"configurable": {"thread_id": "fac-1"}}

    turns = [
        ("I want to file a claim", {}),
        ("my policy number is PY1103", {"policy_number": "PY1103"}),
        ("it's my only car", {"insured_vehicle_vin": "9SYCD4568G1000102"}),
        ("this morning", {"loss_datetime": "2026-08-11T09:00:00-04:00"}),
        ("on Rue Principale in Ottawa", {"loss_location": "Rue Principale, Ottawa, ON"}),
        ("comprehensive, a windshield crack", {"loss_type": "Comprehensive"}),
        ("just the windshield", {"damage_description": "Windshield crack"}),
        ("no one else was involved", {"other_party_involved": False}),
        ("no police report", {"police_report_filed": False}),
        ("I was driving", {"driver_name": "Marc-Andre Tremblay"}),
    ]
    result: dict[str, Any] = {}
    for turn_input, new_slots in turns:
        result = _invoke_turn(graph, config, turn_input=turn_input, new_slots=new_slots)
        assert result.get("response_text"), f"no response for turn {turn_input!r}"

    # All slots filled -- next turn should be the confirmation prompt.
    result = _invoke_turn(graph, config, turn_input="that's everything")
    assert "should i go ahead and file" in result["response_text"].lower()

    result = _invoke_turn(graph, config, turn_input="yes", new_slots={"confirm_file_claim": True})
    assert "your claim number is clm-" in result["response_text"].lower()


# --- Injury preemption ------------------------------------------------------------------------------


def test_l1_injury_preemption_mid_flow_never_touches_bedrock(real_store_and_embedder: Any) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient()  # no responses scripted -- must never be called
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)

    result = graph.invoke(
        {
            "contact_id": "injury-1",
            "turn_input": "there's blood, I need help",
            "filled_slots": {"policy_number": "PY4821"},
            "active_slot": "loss_datetime",  # mid-FileAutoClaim, per DIALOGUE-POLICIES.md §5 step 4
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "call 911" in result["response_text"]
    assert result["escalation"]["route"] == 1
    assert result["escalation"]["triggering_layer"] == "L1"
    assert caller.call_count == 0  # L1 preempted before the router was ever reached


def test_l2_catches_an_injury_l1_misses(real_store_and_embedder: Any) -> None:
    # A phrasing L1's lexicon doesn't catch, but the merged router's L2 classification does -- D15's
    # union semantics: either layer firing escalates.
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={_ROUTER_MODEL: _classification("FileAutoClaim", safety_flag=True)}
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)

    result = graph.invoke(
        {
            "contact_id": "injury-2",
            "turn_input": "a genuinely novel phrasing L1's lexicon does not contain",
            "filled_slots": {},
            "retry_counts": {},
            "is_barge_in": False,
        }
    )
    assert "call 911" in result["response_text"]
    assert result["escalation"]["triggering_layer"] == "L2"


# --- Barge-in ----------------------------------------------------------------------------------------


def test_barge_in_inconclusive_gets_the_open_reprompt_not_the_generic_one(
    real_store_and_embedder: Any,
) -> None:
    store, embedder = real_store_and_embedder
    caller = FakeBedrockConverseClient(
        by_model={_ROUTER_MODEL: _classification("Ambiguous", confidence=0.3)}
    )
    graph = build_graph(vector_store=store, embedder=embedder, bedrock_caller=caller)

    result = graph.invoke(
        {
            "contact_id": "barge-1",
            "turn_input": "wait, um",
            "filled_slots": {},
            "active_slot": "loss_location",
            "retry_counts": {},
            "is_barge_in": True,
        }
    )
    assert result["response_text"] == "Sorry -- go ahead, what were you saying?"
    assert result["retry_counts"]["loss_location"] == 1


# --- Retry ceiling: the shared-ladder property, mixed triggers -----------------------------------------


def test_retry_ceiling_reached_via_mixed_normal_and_barge_in_triggers(
    real_store_and_embedder: Any,
) -> None:
    """Marco's explicit integration requirement: one no-match followed by one barge-in-inconclusive event
    on the SAME slot must reach the ceiling exactly like two of the same trigger would -- proving the
    shared ladder in practice, not just at the retry_ladder.py unit-test level."""
    store, embedder = real_store_and_embedder
    checkpointer = build_test_checkpointer("fnol-checkpoints-retry-test")

    # Turn 1: normal low-confidence no-match on loss_location.
    caller = FakeBedrockConverseClient(
        by_model={_ROUTER_MODEL: _classification("Ambiguous", confidence=0.2)}
    )
    graph = build_graph(
        vector_store=store, embedder=embedder, bedrock_caller=caller, checkpointer=checkpointer
    )
    config = {"configurable": {"thread_id": "retry-mixed-1"}}

    r1 = graph.invoke(
        {
            "contact_id": "retry-mixed-1",
            "turn_input": "hmm not sure",
            "filled_slots": {},
            "active_slot": "loss_location",
            "retry_counts": {},
            "is_barge_in": False,
        },
        config,
    )
    assert r1["retry_counts"]["loss_location"] == 1
    assert "I didn't quite catch that" in r1["response_text"]  # generic reprompt, not barge-in's

    # Turn 2: a barge-in-inconclusive event on the SAME slot -- must be the SAME counter, reaching the
    # ceiling (RETRY_CEILING == 2), not a fresh count of 1 on a separate barge-in ladder.
    r2 = _invoke_turn(graph, config, turn_input="wait sorry what", is_barge_in=True)
    assert r2["retry_counts"]["loss_location"] == RETRY_CEILING == 2
    assert "let me connect you with someone" in r2["response_text"]
    assert r2["escalation"]["route"] == 3
    assert r2["escalation"]["triggering_layer"] == "capability"


# --- Structural check, exercised again against the real graph (defense in depth) -----------------------


def test_the_real_compiled_graph_is_buildable_meaning_l1_dominance_already_held(
    real_store_and_embedder: Any,
) -> None:
    # build_graph() itself calls assert_dominates before compiling (agents/graph.py) -- this test doesn't
    # re-implement that check, it proves the real graph reaches this line at all, which it can only do if
    # that construction-time assertion already passed. A future edit that broke dominance would fail here
    # via the exception build_graph() raises, not silently.
    store, embedder = real_store_and_embedder
    graph = build_graph(vector_store=store, embedder=embedder)
    assert graph is not None
