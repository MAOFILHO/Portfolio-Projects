"""Structural verification that a given node dominates the graph -- `ADR-010`'s "L1 runs before anything
else" requirement, enforced by construction, not by convention or a comment.

**Graph-theoretic dominance**: node `D` dominates node `N` if every path from `START` to `N` passes
through `D`. The check here is the standard algorithm: do a reachability search from `START`, but never
expand *past* `D` (its outgoing edges are not traversed). Any node still reachable in that restricted
search — other than `D` itself — has some path to it that never needed `D`, which is exactly the
violation `assert_dominates` exists to catch.

Used by `agents/graph.py` at construction time, before `.compile()` — a graph that violates this cannot be
built, not merely fails a test that happens to run.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START
from langgraph.graph.state import StateGraph

# This module is reused across any StateGraph shape (the real AgentState graph, and a generic
# TypedDict in its own tests) -- typed generically here rather than pinned to AgentState.
AnyStateGraph = StateGraph[Any, Any, Any, Any]


class GraphStructureError(RuntimeError):
    """Raised when a graph violates a structural invariant this project requires."""


def _all_edges(builder: AnyStateGraph) -> set[tuple[str, str]]:
    """Every edge in `builder`, direct and conditional. `builder.edges` holds direct edges as
    `(source, dest)` tuples; conditional edges live in `builder.branches` (`{source: {branch_name:
    BranchSpec}}`), whose `BranchSpec.ends` gives the possible destination node names for that branch --
    both are folded into one edge set so the dominance search doesn't need to know which kind of edge it's
    walking.
    """
    edges = set(builder.edges)
    for source, branch_dict in builder.branches.items():
        for spec in branch_dict.values():
            if spec.ends:
                for dest in spec.ends.values():
                    edges.add((source, dest))
    return edges


def find_dominance_violations(
    builder: AnyStateGraph, dominator: str, *, start: str = START
) -> set[str]:
    """Returns every node reachable from `start` WITHOUT passing through `dominator`. An empty set means
    `dominator` dominates the whole graph; any name in the set is a node `dominator` does NOT dominate.
    """
    edges = _all_edges(builder)
    adjacency: dict[str, set[str]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, set()).add(dst)

    visited = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        if current == dominator:
            continue  # never expand past the dominator -- anything only reachable beyond it stays unvisited
        for neighbor in adjacency.get(current, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)

    return visited - {start, dominator, END}


def assert_dominates(builder: AnyStateGraph, dominator: str, *, start: str = START) -> None:
    """Raises `GraphStructureError` if `dominator` does not dominate every other node in `builder`."""
    violations = find_dominance_violations(builder, dominator, start=start)
    if violations:
        raise GraphStructureError(
            f"{dominator!r} does not dominate this graph -- these nodes are reachable from {start!r} "
            f"without passing through {dominator!r}: {sorted(violations)}. ADR-010 requires L1 to run "
            "before anything else, every turn; this is a construction-time defect in the graph's edges, "
            "not a runtime one, and the graph must not be built until it's fixed."
        )
