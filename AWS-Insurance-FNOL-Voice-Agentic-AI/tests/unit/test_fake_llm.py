"""Unit tests for the fake-LLM harness itself (`agents/testing/fake_llm.py`).

Proves the harness is deterministic and network-free before anything else (Stage 4's own
`test_bedrock_router.py`, later Stage 6) is allowed to trust it as a Bedrock stand-in.
"""

from __future__ import annotations

import pytest

from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_text_response,
    converse_tool_use_response,
)


def test_queue_based_client_returns_canned_responses_in_order() -> None:
    first = converse_text_response("first")
    second = converse_text_response("second")
    client = FakeBedrockConverseClient(responses=[first, second])

    assert client.converse(modelId="m1", messages=[]) == first
    assert client.converse(modelId="m1", messages=[]) == second


def test_queue_response_appends_incrementally() -> None:
    client = FakeBedrockConverseClient()
    client.queue_response(converse_text_response("only"))

    result = client.converse(modelId="m1", messages=[])

    assert result["output"]["message"]["content"][0]["text"] == "only"


def test_calls_are_recorded_verbatim_and_in_order() -> None:
    client = FakeBedrockConverseClient(
        responses=[converse_text_response("a"), converse_text_response("b")]
    )

    client.converse(modelId="model-a", messages=[{"role": "user", "content": [{"text": "hi"}]}])
    client.converse(modelId="model-b", messages=[])

    assert client.call_count == 2
    assert client.requested_model_ids() == ["model-a", "model-b"]
    assert client.calls[0]["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]


def test_by_model_mapping_is_consulted_once_the_queue_is_empty() -> None:
    client = FakeBedrockConverseClient(
        by_model={
            "model-a": converse_text_response("from a"),
            "model-b": converse_text_response("from b"),
        }
    )

    result_a = client.converse(modelId="model-a", messages=[])
    result_b = client.converse(modelId="model-b", messages=[])

    assert result_a["output"]["message"]["content"][0]["text"] == "from a"
    assert result_b["output"]["message"]["content"][0]["text"] == "from b"


def test_queue_takes_priority_over_by_model_mapping() -> None:
    queued = converse_text_response("queued")
    client = FakeBedrockConverseClient(
        responses=[queued], by_model={"model-a": converse_text_response("mapped")}
    )

    result = client.converse(modelId="model-a", messages=[])

    assert result == queued


def test_unscripted_call_raises_rather_than_silently_returning_nothing() -> None:
    client = FakeBedrockConverseClient()

    with pytest.raises(AssertionError, match="no canned response"):
        client.converse(modelId="unscripted-model", messages=[])


def test_converse_tool_use_response_shape() -> None:
    response = converse_tool_use_response("classify_turn", {"safety_flag": False})

    block = response["output"]["message"]["content"][0]["toolUse"]
    assert block["name"] == "classify_turn"
    assert block["input"] == {"safety_flag": False}
    assert response["stopReason"] == "tool_use"


def test_converse_text_response_shape() -> None:
    response = converse_text_response("hello caller")

    assert response["output"]["message"]["content"] == [{"text": "hello caller"}]
    assert response["stopReason"] == "end_turn"
