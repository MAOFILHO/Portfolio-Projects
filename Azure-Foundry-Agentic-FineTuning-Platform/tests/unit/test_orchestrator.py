"""Unit tests for the LangGraph orchestrator (app.agents.orchestrator)."""

from __future__ import annotations

import pytest

from app.agents.orchestrator import classify, invoke


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("show me the model catalog and leaderboard", "discovery"),
        ("I want to fine-tune gpt-4.1 on my dataset", "finetune"),
        ("compare the two model outputs side by side", "comparison"),
    ],
)
def test_classify_routes_on_keywords(text: str, expected: str):
    demo, _reason = classify(text)
    assert demo == expected


def test_explicit_demo_always_wins_over_classification():
    # Text screams "finetune" but an explicit demo=discovery must win.
    demo, reason = classify("please fine-tune this model")
    assert demo == "finetune"  # sanity: keyword routing itself works
    # The explicit-override behaviour is exercised through invoke() below.


@pytest.mark.asyncio
async def test_invoke_discovery_completes_with_no_error():
    state = await invoke("discovery", demo="discovery")
    assert state.get("error") is None
    assert state["result"]["demo"] == "discovery"
    assert len(state["trace"]) > 0


@pytest.mark.asyncio
async def test_invoke_finetune_completes_and_deploys():
    state = await invoke("finetune", demo="finetune")
    assert state.get("error") is None
    assert state["result"]["status"]["status"] == "succeeded"
    assert state["result"]["deployment"]["deployment_type"] == "Developer"


@pytest.mark.asyncio
async def test_invoke_comparison_scores_fine_tuned_higher_than_baseline():
    state = await invoke("comparison", demo="comparison")
    report = state["result"]["report"]
    assert report["fine_tuned_total"] >= report["baseline_total"]


@pytest.mark.asyncio
async def test_invoke_explicit_demo_overrides_free_text_request():
    # Free text talks about fine-tuning, but demo="discovery" must win.
    state = await invoke("please set up a fine-tuning job", demo="discovery")
    assert state["result"]["demo"] == "discovery"
