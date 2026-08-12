"""`aws/checkpointer.py` tests -- `ADR-005`'s DynamoDB-backed state persistence, against a moto-mocked
table (`build_test_checkpointer`). No real DynamoDB table is created or assumed anywhere here, per
`docs/phase5/BUILD-PLAN.md` §2.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START
from langgraph.graph.state import StateGraph
from moto import mock_aws

from fnol_voice_agent.aws.checkpointer import build_test_checkpointer


class _CounterState(TypedDict):
    x: int


def _increment(state: _CounterState) -> dict[str, int]:
    return {"x": state.get("x", 0) + 1}


def _build_counter_graph(checkpointer: object) -> object:
    builder = StateGraph(_CounterState)
    builder.add_node("increment", _increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=checkpointer)  # type: ignore[arg-type]


def test_checkpointer_persists_state_across_invocations_on_the_same_thread() -> None:
    with mock_aws():
        checkpointer = build_test_checkpointer("fnol-checkpoints-test-1")
        graph = _build_counter_graph(checkpointer)
        config = {"configurable": {"thread_id": "contact-abc"}}

        r1 = graph.invoke({"x": 0}, config)  # type: ignore[attr-defined]
        r2 = graph.invoke({"x": r1["x"]}, config)  # type: ignore[attr-defined]

        assert r1["x"] == 1
        assert r2["x"] == 2
        state = graph.get_state(config)  # type: ignore[attr-defined]
        assert state.values == {"x": 2}


def test_checkpointer_keeps_separate_threads_independent() -> None:
    # Different contact_id -> different thread_id -> independent state, per ADR-005's keying scheme.
    with mock_aws():
        checkpointer = build_test_checkpointer("fnol-checkpoints-test-2")
        graph = _build_counter_graph(checkpointer)
        config_a = {"configurable": {"thread_id": "contact-a"}}
        config_b = {"configurable": {"thread_id": "contact-b"}}

        # An empty input dict leaves the checkpointed "x" channel untouched by the input-merge step, so
        # the node sees whatever the checkpoint already holds -- {"x": 0} on the *second* call would
        # instead reset the channel to 0 before incrementing, which is a test-authoring bug, not a real
        # checkpointer one (caught while first writing this test).
        graph.invoke({"x": 0}, config_a)  # type: ignore[attr-defined]
        graph.invoke({}, config_a)  # type: ignore[attr-defined]
        graph.invoke({"x": 0}, config_b)  # type: ignore[attr-defined]

        assert graph.get_state(config_a).values == {"x": 2}  # type: ignore[attr-defined]
        assert graph.get_state(config_b).values == {"x": 1}  # type: ignore[attr-defined]
