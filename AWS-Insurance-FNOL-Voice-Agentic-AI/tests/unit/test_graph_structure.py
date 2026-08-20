"""Tests for the dominance check itself, independent of the real graph -- proves the check has teeth
(catches a real violation) before trusting it to guard `agents/graph.py`.
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.graph import END, START
from langgraph.graph.state import StateGraph

from fnol_voice_agent.agents.graph_structure import (
    GraphStructureError,
    assert_dominates,
    assert_dominates_except,
)


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


# --- assert_dominates_except -- ADR-017's shape: a shared node that is NOT the graph's entry point, ----
# --- reached from a fixed, named set of fan-in sources, one of which is a deliberate, named bypass. -----


def _router_response_or_none(_: _S) -> str:
    return "response"


def test_dominates_except_holds_when_the_named_exception_really_bypasses() -> None:
    # `a` and `b` both feed `guard` the way `ADR-017`'s five intent nodes fed `guardrails_output_check`,
    # each with its own "no response yet" fallback to a third, shared node unrelated to the property under
    # test -- a passing check must not be confused by that fallback (`assert_dominates`'s own transitive
    # search would be, which is why `assert_dominates_except` is one-hop, not transitive; see its
    # docstring). `b` is the named exception and really does bypass `guard`, straight to END.
    builder: StateGraph[_S, None, str, str] = StateGraph(_S)
    builder.add_node("a", _noop)
    builder.add_node("b", _noop)
    builder.add_node("guard", _noop)
    builder.add_node("fallback", _noop)
    builder.add_edge(START, "a")
    builder.add_conditional_edges(
        "a", _router_response_or_none, {"response": "guard", "none": "fallback"}
    )
    builder.add_conditional_edges(
        "b", _router_response_or_none, {"response": END, "none": "fallback"}
    )
    builder.add_edge("guard", END)
    builder.add_edge("fallback", END)

    assert_dominates_except(
        builder, "guard", ("a", "b"), exceptions=frozenset({"b"})
    )  # must not raise


def test_dominates_except_flags_a_non_exception_source_that_bypasses_the_dominator() -> None:
    # `a` (not a named exception) bypasses `guard` directly -- the exact regression ADR-017 condition
    # part 2 exists to catch: a node that should be checked skips the check.
    builder: StateGraph[_S, None, str, str] = StateGraph(_S)
    builder.add_node("a", _noop)
    builder.add_node("b", _noop)
    builder.add_node("guard", _noop)
    builder.add_node("fallback", _noop)
    builder.add_edge(START, "a")
    builder.add_conditional_edges(
        "a", _router_response_or_none, {"response": END, "none": "fallback"}
    )
    builder.add_conditional_edges(
        "b", _router_response_or_none, {"response": END, "none": "fallback"}
    )
    builder.add_edge("guard", END)
    builder.add_edge("fallback", END)

    with pytest.raises(GraphStructureError, match="'a'"):
        assert_dominates_except(builder, "guard", ("a", "b"), exceptions=frozenset({"b"}))


def test_dominates_except_flags_a_source_with_no_edge_to_the_dominator_at_all() -> None:
    builder: StateGraph[_S, None, str, str] = StateGraph(_S)
    builder.add_node("a", _noop)
    builder.add_node("guard", _noop)
    builder.add_edge(START, "a")
    builder.add_edge("a", END)  # never routes to `guard` in any branch
    builder.add_edge("guard", END)

    with pytest.raises(GraphStructureError, match="'a'"):
        assert_dominates_except(builder, "guard", ("a",))


def test_dominates_except_flags_a_stale_exception_that_still_reaches_the_dominator() -> None:
    # The other regression direction: an old bypass gets accidentally re-routed through the dominator
    # (silently widening what it now protects) and nothing else here would notice.
    builder: StateGraph[_S, None, str, str] = StateGraph(_S)
    builder.add_node("a", _noop)
    builder.add_node("b", _noop)
    builder.add_node("guard", _noop)
    builder.add_node("fallback", _noop)
    builder.add_edge(START, "a")
    builder.add_conditional_edges(
        "a", _router_response_or_none, {"response": "guard", "none": "fallback"}
    )
    builder.add_conditional_edges(
        "b", _router_response_or_none, {"response": "guard", "none": "fallback"}
    )
    builder.add_edge("guard", END)
    builder.add_edge("fallback", END)

    with pytest.raises(GraphStructureError, match="'b'"):
        assert_dominates_except(builder, "guard", ("a", "b"), exceptions=frozenset({"b"}))


def test_dominates_except_flags_a_named_exception_with_no_direct_end_edge() -> None:
    # b is named an exception but was never actually wired to bypass anything -- it doesn't reach `guard`
    # OR `END` directly (e.g. it only ever falls through to the shared fallback). The exception claim is
    # stale in the other possible way: not "still checked", but "not doing what being excepted means".
    builder: StateGraph[_S, None, str, str] = StateGraph(_S)
    builder.add_node("a", _noop)
    builder.add_node("b", _noop)
    builder.add_node("guard", _noop)
    builder.add_node("fallback", _noop)
    builder.add_edge(START, "a")
    builder.add_conditional_edges(
        "a", _router_response_or_none, {"response": "guard", "none": "fallback"}
    )
    builder.add_edge("b", "fallback")  # no direct edge to guard, none to END either
    builder.add_edge("guard", END)
    builder.add_edge("fallback", END)

    with pytest.raises(GraphStructureError, match="'b'"):
        assert_dominates_except(builder, "guard", ("a", "b"), exceptions=frozenset({"b"}))
