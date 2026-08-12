"""L1 -- the deterministic injury/fatality pre-node (`D12`, `D15`, `ADR-010`). No model call, no external
dependency -- pure function of `state["turn_input"]` via `agents/lexicon.py`. This is the node
`agents/graph.py`'s dominance check requires to be the sole successor of `START`.
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.agents.state import AgentState

NODE_NAME = "l1_safety_check"


def l1_safety_check(state: AgentState) -> dict[str, Any]:
    fired, matched_term = detect_safety_trigger(state.get("turn_input", ""))
    return {"l1_safety_flag": fired, "l1_matched_term": matched_term}
