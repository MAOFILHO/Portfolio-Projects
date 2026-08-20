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

from collections.abc import Iterable
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


def assert_dominates_except(
    builder: AnyStateGraph,
    dominator: str,
    sources: Iterable[str],
    *,
    exceptions: frozenset[str] = frozenset(),
) -> None:
    """`ADR-017`'s dominance check for a shared node that is NOT the graph's entry point --
    `guardrails_output_check`, reached from a fixed, named set of fan-in `sources` (the five nodes that
    used to share `_after_intent_node`), rather than from every node in the graph. `assert_dominates`
    itself does not fit this shape: `dominator` here has real predecessors and real siblings (`l1_safety_
    check`, `injury_escalation`, `handle_no_match_or_barge_in`, ...) that are correctly reachable from
    `START` without passing through it, and a BFS from `START` that excluded all of those by name would
    not be "one named exception," it would be most of the graph. See `ADR-017`'s Round 2/Decision section
    for why the invariant under test is local to `sources`, not global to the graph.

    For each node in `sources`:

    - **Not in `exceptions`**: `dominator` must be one of its direct destinations, and `END` must not be
      (a response_text this node produces must reach the guardrail check, not skip straight past it).
    - **In `exceptions`**: the reverse -- `END` must be a direct destination and `dominator` must not be.
      This is the "named exception" half `Round 2 Q2` (conceded) says was never previously asserted: it
      does not merely tolerate the bypass, it requires it, so a future edit that accidentally restores the
      exception's routing through `dominator` (silently widening what the guardrail now protects, in a way
      nothing else here would notice) fails exactly as loudly as a routing edit that drops a `sources`
      node off the guardrail's protection would.

    One hop only, deliberately, not a transitive reachability search: from any of these `sources`, the
    ONLY way to reach `END` at all is via `dominator` or via the node-local no-response_text fallback
    (`handle_no_match_or_barge_in`) -- a transitive search would need to special-case that fallback (a
    legitimate bypass unrelated to `ADR-017`, present for every node in `sources` including the
    non-exceptions) to avoid flagging it as a false violation, which is exactly the kind of hand-tuned
    exception list this function exists to avoid needing.
    """
    edges = _all_edges(builder)
    direct_destinations: dict[str, set[str]] = {}
    for src, dst in edges:
        direct_destinations.setdefault(src, set()).add(dst)

    for source in sources:
        destinations = direct_destinations.get(source, set())
        goes_to_dominator = dominator in destinations
        goes_direct_to_end = END in destinations

        if source in exceptions:
            if goes_to_dominator:
                raise GraphStructureError(
                    f"{source!r} is named as an exception to {dominator!r}'s dominance (ADR-017), but it "
                    f"still has a direct edge to {dominator!r} -- the exception is stale: either the "
                    f"routing regressed back to going through the dominator (silently widening what the "
                    f"output guardrail now sees), or {source!r} no longer needs the exception and should "
                    "be removed from it."
                )
            if not goes_direct_to_end:
                raise GraphStructureError(
                    f"{source!r} is named as an exception to {dominator!r}'s dominance (ADR-017) but has "
                    f"no direct edge to END -- the exception no longer describes this node's actual "
                    "routing, and ADR-017's bypass may no longer be in effect."
                )
        else:
            if goes_direct_to_end:
                raise GraphStructureError(
                    f"{dominator!r} does not dominate {source!r}'s path to END, and {source!r} is not a "
                    f"named exception (ADR-017) -- a response_text from {source!r} can reach the caller "
                    f"without passing through {dominator!r}."
                )
            if not goes_to_dominator:
                raise GraphStructureError(
                    f"{source!r} has no direct edge to {dominator!r} at all -- it cannot be dominated by "
                    f"a node it never routes to. Either {source!r}'s routing regressed, or it belongs in "
                    "the exceptions set instead of the plain sources set."
                )
