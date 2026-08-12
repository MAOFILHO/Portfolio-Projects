"""Tests for the dominance check itself, independent of the real graph -- proves the check has teeth
(catches a real violation) before trusting it to guard `agents/graph.py`.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.graph import END, START
from langgraph.graph.state import StateGraph

from fnol_voice_agent.agents.graph_structure import GraphStructureError, assert_dominates


class _S(TypedDict):
    x: int


def _noop(_: _S) -> dict[str, int]:
    return {}


def _router_a_or_b(_: _S) -> str:
    return "a"


def test_dominance_holds_when_l1_is_the_sole_entry_point() -> None:
    builder = StateGraph(_S)
    builder.add_node("l1", _noop)
    builder.add_node("a", _noop)
    builder.add_node("b", _noop)
    builder.add_edge(START, "l1")
    builder.add_conditional_edges("l1", _router_a_or_b, {"a": "a", "b": "b"})
    builder.add_edge("a", END)
    builder.add_edge("b", END)

    assert_dominates(builder, "l1")  # must not raise


def test_dominance_violated_by_a_second_edge_from_start() -> None:
    # The exact failure mode ADR-010 exists to prevent: a node reachable from START without ever
    # touching L1.
    builder = StateGraph(_S)
    builder.add_node("l1", _noop)
    builder.add_node("a", _noop)
    builder.add_node("bypass", _noop)
    builder.add_edge(START, "l1")
    builder.add_edge(START, "bypass")  # the violation
    builder.add_edge("l1", "a")
    builder.add_edge("a", END)
    builder.add_edge("bypass", END)

    with pytest.raises(GraphStructureError, match="bypass"):
        assert_dominates(builder, "l1")


def test_dominance_violated_by_a_conditional_edge_bypassing_l1() -> None:
    # Same violation, but via a conditional edge rather than a direct one -- proves the check inspects
    # builder.branches, not just builder.edges.
    def _router_from_start(_: _S) -> str:
        return "l1"

    builder = StateGraph(_S)
    builder.add_node("l1", _noop)
    builder.add_node("shortcut", _noop)
    builder.add_conditional_edges(START, _router_from_start, {"l1": "l1", "shortcut": "shortcut"})
    builder.add_edge("l1", END)
    builder.add_edge("shortcut", END)

    with pytest.raises(GraphStructureError, match="shortcut"):
        assert_dominates(builder, "l1")


def test_a_node_only_reachable_through_the_dominator_is_not_flagged() -> None:
    builder = StateGraph(_S)
    builder.add_node("l1", _noop)
    builder.add_node("downstream", _noop)
    builder.add_edge(START, "l1")
    builder.add_edge("l1", "downstream")
    builder.add_edge("downstream", END)

    assert_dominates(builder, "l1")  # must not raise -- downstream is only reachable via l1
