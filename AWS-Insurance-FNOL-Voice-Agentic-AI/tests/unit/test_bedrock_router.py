"""Unit tests for `aws/bedrock_router.py` (docs/phase5/BUILD-PLAN.md Stage 4).

Every test here drives `classify_turn`/`generate_response` through
`FakeBedrockConverseClient` (`agents/testing/fake_llm.py`) -- zero real Bedrock calls
anywhere in this file, per this stage's own constraint. A real Bedrock call against this
exact code path is Stage 8's job, cost-gated and separate.
"""

from __future__ import annotations

import pytest
from openfeature import api
from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider
from pydantic import ValidationError

from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_text_response,
    converse_tool_use_response,
)
from fnol_voice_agent.aws.bedrock_router import (
    BedrockRouterError,
    CLASSIFY_TURN_TOOL_NAME,
    classify_turn,
    generate_response,
)
from fnol_voice_agent.config.flags import (
    GENERATION_TIER_FLAG,
    configure_default_flags,
)
from fnol_voice_agent.config.settings import (
    ALTERNATE_GENERATION_MODEL_ID,
    DEFAULT_GENERATION_MODEL_ID,
    ROUTER_MODEL_ID,
)
from fnol_voice_agent.models.enums import CoverageQuestionType, Intent
from fnol_voice_agent.models.routing import TurnClassification

# PROMPT-REGISTRY.md §3.1 -- CoverageQuestion election-fact synthesis. Verbatim, current
# (already-fixed) text -- no earlier draft.
COVERAGE_QUESTION_SYSTEM_PROMPT = (
    "Answer the caller's coverage question using only the policy text and, if provided, their "
    "specific election record below. State the answer first, in one sentence. You may add one "
    "short supporting clause from the retrieved text if it adds real information (a limit, a "
    "condition) — otherwise stop after the first sentence. Never exceed two sentences. Do not "
    'restate the caller\'s question. Do not add a disclaimer, caveat, or "please note" unless '
    "the policy text itself states a condition the caller needs to know. If the retrieved text "
    "does not clearly answer the question, say exactly: \"I don't have that in your policy — "
    'let me get you to someone who does." Never guess.'
)

# PROMPT-REGISTRY.md §3.2 -- RentalTowingEntitlement compound synthesis. Verbatim, current
# (already-fixed) text -- this is the prompt AFTER the real-verification fix (§4): the
# "do not restate the same fact" instruction was added in direct response to an observed
# defect (the rental compound answer's second sentence restated the "8 days" fact instead
# of adding the dollar figure). Tests here must exercise this fixed text, not an earlier draft.
RENTAL_TOWING_ENTITLEMENT_SYSTEM_PROMPT = (
    "Answer using both the policy terms and the claim status below — both are required, and an "
    "answer that uses only one of them is wrong even if it sounds correct. State whether the "
    "entitlement applies, then state the concrete number that matters to the caller right now "
    "(days/dollars remaining for rental; covered or not for towing). Two to three sentences. Do "
    "not explain the endorsement's general mechanics beyond what answers this caller's "
    "situation — they asked about their claim, not the product in the abstract. Do not restate "
    "the same fact in a second sentence using different words — each sentence must add new "
    "information. If the claim status tool call did not return a resolvable claim, say so "
    "plainly and state the policy terms only, without implying the entitlement is currently "
    "active."
)


def _user_turn(text: str) -> list[dict[str, object]]:
    return [{"role": "user", "content": [{"text": text}]}]


def _valid_classification() -> dict[str, object]:
    return {
        "safety_flag": False,
        "intent": "CoverageQuestion",
        "intent_confidence": 0.9,
        "coverage_question_type": "election_fact_optional",
    }


# --- classify_turn: happy path --------------------------------------------------------------


def test_classify_turn_parses_a_well_formed_tool_use_response() -> None:
    canned = converse_tool_use_response(
        CLASSIFY_TURN_TOOL_NAME,
        {
            "safety_flag": False,
            "intent": "CoverageQuestion",
            "intent_confidence": 0.92,
            "coverage_question_type": "election_fact_optional",
        },
    )
    caller = FakeBedrockConverseClient(responses=[canned])

    result = classify_turn(_user_turn("Is towing covered on my policy?"), caller=caller)

    assert result == TurnClassification(
        safety_flag=False,
        intent=Intent.COVERAGE_QUESTION,
        intent_confidence=0.92,
        coverage_question_type=CoverageQuestionType.ELECTION_FACT_OPTIONAL,
    )


def test_classify_turn_calls_the_fixed_router_model_with_forced_tool_use() -> None:
    canned = converse_tool_use_response(
        CLASSIFY_TURN_TOOL_NAME,
        {
            "safety_flag": True,
            "intent": "InjuryEscalation",
            "intent_confidence": 1.0,
            "coverage_question_type": "not_applicable",
        },
    )
    caller = FakeBedrockConverseClient(responses=[canned])

    classify_turn(_user_turn("he's not moving"), caller=caller)

    assert caller.call_count == 1
    call = caller.calls[0]
    assert call["modelId"] == ROUTER_MODEL_ID
    assert call["toolConfig"]["toolChoice"] == {"tool": {"name": CLASSIFY_TURN_TOOL_NAME}}
    tool_names = {t["toolSpec"]["name"] for t in call["toolConfig"]["tools"]}
    assert tool_names == {CLASSIFY_TURN_TOOL_NAME}


# --- classify_turn: Q10 -- a missing required field must raise, not silently omit -----------


def test_classify_turn_raises_on_missing_safety_flag() -> None:
    """Q10: "L2's per-turn classifier must not be switchable off... the safety flag must
    not be silently omittable." Prove parsing enforces this -- a tool-use response
    missing `safety_flag` must fail loudly (ValidationError), never fall back to a
    partial/default classification.
    """
    canned = converse_tool_use_response(
        CLASSIFY_TURN_TOOL_NAME,
        {
            # safety_flag deliberately omitted.
            "intent": "CoverageQuestion",
            "intent_confidence": 0.5,
        },
    )
    caller = FakeBedrockConverseClient(responses=[canned])

    with pytest.raises(ValidationError, match="safety_flag"):
        classify_turn(_user_turn("some turn"), caller=caller)


def test_classify_turn_raises_on_missing_intent() -> None:
    canned = converse_tool_use_response(
        CLASSIFY_TURN_TOOL_NAME,
        {"safety_flag": False, "intent_confidence": 0.5},
    )
    caller = FakeBedrockConverseClient(responses=[canned])

    with pytest.raises(ValidationError, match="intent"):
        classify_turn(_user_turn("some turn"), caller=caller)


def test_classify_turn_raises_bedrock_router_error_when_no_tool_use_block_present() -> None:
    """A malformed/unexpected Converse response (e.g. the model produced only prose,
    no tool call) must not be silently coerced into a classification either."""
    caller = FakeBedrockConverseClient(responses=[converse_text_response("I refuse to classify.")])

    with pytest.raises(BedrockRouterError):
        classify_turn(_user_turn("some turn"), caller=caller)


# --- generate_response: happy path, both documented generation-node prompts ------------------


def test_generate_response_coverage_question_election_fact() -> None:
    caller = FakeBedrockConverseClient(
        responses=[converse_text_response("Yes, DCPD is mandatory on every Example Mutual policy.")]
    )

    result = generate_response(
        COVERAGE_QUESTION_SYSTEM_PROMPT,
        "Is DCPD mandatory on my policy?",
        caller=caller,
    )

    assert result == "Yes, DCPD is mandatory on every Example Mutual policy."
    call = caller.calls[0]
    assert call["system"] == [{"text": COVERAGE_QUESTION_SYSTEM_PROMPT}]
    assert call["modelId"] == DEFAULT_GENERATION_MODEL_ID  # flag not overridden in this test


def test_generate_response_rental_towing_entitlement_compound() -> None:
    caller = FakeBedrockConverseClient(
        responses=[
            converse_text_response(
                "Yes, rental coverage applies to your claim. You have 8 days of rental "
                "remaining, up to $35 per day."
            )
        ]
    )

    result = generate_response(
        RENTAL_TOWING_ENTITLEMENT_SYSTEM_PROMPT,
        "How many rental days do I have left?",
        caller=caller,
    )

    assert "8 days" in result
    assert caller.calls[0]["system"] == [{"text": RENTAL_TOWING_ENTITLEMENT_SYSTEM_PROMPT}]


def test_generate_response_raises_bedrock_router_error_when_no_text_present() -> None:
    caller = FakeBedrockConverseClient(
        responses=[converse_tool_use_response("some_other_tool", {})]
    )

    with pytest.raises(BedrockRouterError):
        generate_response(COVERAGE_QUESTION_SYSTEM_PROMPT, "a question", caller=caller)


# --- D27 / Q12: both model calls are pinned to temperature 0.0 ------------------------------
#
# Neither pin had a test when it shipped. `ROUTER_TEMPERATURE` was set at Stage 0.5 and
# `GENERATION_TEMPERATURE` at Stage 2, both verified only by the measurement scripts that
# motivated them -- which is not the same as a test, because a script that stops being run
# stops noticing. The pins exist to make measurement possible at all, so a silent revert to
# Bedrock's default 0.7 would invalidate every number taken after it without failing anything.


def test_classify_turn_sends_temperature_zero_by_default() -> None:
    caller = FakeBedrockConverseClient(
        responses=[converse_tool_use_response(CLASSIFY_TURN_TOOL_NAME, _valid_classification())]
    )

    classify_turn(_user_turn("some turn"), caller=caller)

    assert caller.calls[0]["inferenceConfig"]["temperature"] == 0.0


def test_generate_response_sends_temperature_zero_by_default() -> None:
    caller = FakeBedrockConverseClient(responses=[converse_text_response("an answer")])

    generate_response(COVERAGE_QUESTION_SYSTEM_PROMPT, "a question", caller=caller)

    assert caller.calls[0]["inferenceConfig"]["temperature"] == 0.0


def test_temperature_none_omits_the_key_entirely_on_both_calls() -> None:
    """`temperature=None` must send no `temperature` key at all, not `temperature: None`
    (which Bedrock would reject) and not a silently substituted 0.0. This is the escape
    hatch the measurement scripts use to reproduce pre-fix behaviour, so it has to keep
    working -- otherwise the 0.7-vs-0.0 comparison stops being reproducible."""
    router_caller = FakeBedrockConverseClient(
        responses=[converse_tool_use_response(CLASSIFY_TURN_TOOL_NAME, _valid_classification())]
    )
    classify_turn(_user_turn("some turn"), caller=router_caller, temperature=None)
    assert "temperature" not in router_caller.calls[0]["inferenceConfig"]

    gen_caller = FakeBedrockConverseClient(responses=[converse_text_response("an answer")])
    generate_response(COVERAGE_QUESTION_SYSTEM_PROMPT, "q", caller=gen_caller, temperature=None)
    assert "temperature" not in gen_caller.calls[0]["inferenceConfig"]


# --- ADR-004 / Q10: structural separation, proven concretely, not just asserted -------------


def test_generation_tier_flag_changes_generation_call_but_never_reaches_router_call() -> None:
    """The concrete, testable proof of ADR-004/Q10's structural-separation claim: flip
    the generation-tier flag via config/flags.py's own mechanism (the same pattern
    test_flags.py uses), drive BOTH call paths through one shared fake client, and
    assert on the actually-recorded `modelId` per call -- not on a docstring's claim.
    """
    caller = FakeBedrockConverseClient(
        by_model={
            ROUTER_MODEL_ID: converse_tool_use_response(
                CLASSIFY_TURN_TOOL_NAME,
                {
                    "safety_flag": False,
                    "intent": "CheckClaimStatus",
                    "intent_confidence": 0.8,
                    "coverage_question_type": "not_applicable",
                },
            ),
            DEFAULT_GENERATION_MODEL_ID: converse_text_response("nova-lite answer"),
            ALTERNATE_GENERATION_MODEL_ID: converse_text_response("claude-haiku answer"),
        }
    )

    try:
        # 1. Default flag state (nova-lite).
        configure_default_flags()
        classify_turn(_user_turn("what's my claim status"), caller=caller)
        generate_response(COVERAGE_QUESTION_SYSTEM_PROMPT, "q1", caller=caller)

        # 2. Flip the flag to the alternate tier -- same mechanism test_flags.py uses.
        api.set_provider(
            InMemoryProvider(
                {
                    GENERATION_TIER_FLAG: InMemoryFlag(
                        default_variant="claude-haiku-4-5",
                        variants={
                            "nova-lite": DEFAULT_GENERATION_MODEL_ID,
                            "claude-haiku-4-5": ALTERNATE_GENERATION_MODEL_ID,
                        },
                    )
                }
            )
        )
        classify_turn(_user_turn("what's my claim status"), caller=caller)
        generate_response(RENTAL_TOWING_ENTITLEMENT_SYSTEM_PROMPT, "q2", caller=caller)
    finally:
        configure_default_flags()  # restore, so this test doesn't leak state into others

    model_ids = caller.requested_model_ids()
    assert model_ids == [
        ROUTER_MODEL_ID,  # classify_turn, flag = nova-lite
        DEFAULT_GENERATION_MODEL_ID,  # generate_response, flag = nova-lite
        ROUTER_MODEL_ID,  # classify_turn, flag = claude-haiku-4-5 -- UNCHANGED
        ALTERNATE_GENERATION_MODEL_ID,  # generate_response, flag = claude-haiku-4-5 -- moved
    ]
    # The router's requested model is identical before and after the flip -- the concrete
    # assertion that the generation-tier flag has no code path to the router call.
    assert model_ids[0] == model_ids[2] == ROUTER_MODEL_ID
    # The generation call's requested model DID move with the flag.
    assert model_ids[1] != model_ids[3]
