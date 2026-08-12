"""The merged router + L2 safety-classification node -- wraps `aws/bedrock_router.classify_turn`
(`ADR-004`, `PROMPT-REGISTRY.md` §1.1). Runs only if L1 didn't already terminate the turn (enforced by
`agents/graph.py`'s conditional edge out of `l1_safety_check`, not by this node itself).
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState, NodeFn
from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller, classify_turn


def make_route_and_classify_node(*, caller: BedrockConverseCaller | None = None) -> NodeFn:
    def route_and_classify(state: AgentState) -> dict[str, Any]:
        messages = [{"role": "user", "content": [{"text": state.get("turn_input", "")}]}]
        classification = classify_turn(messages, caller=caller)
        # D15's union semantics: L1 firing already ends the turn before this node runs (graph.py), so in
        # practice l1_safety_flag is False whenever this node executes -- read defensively anyway rather
        # than assume the graph always enforces that, since L2 can independently flag a turn L1 missed.
        safety_flag = state.get("l1_safety_flag", False) or classification.safety_flag
        return {
            "safety_flag": safety_flag,
            "intent": classification.intent.value,
            "intent_confidence": classification.intent_confidence,
            "coverage_question_type": classification.coverage_question_type.value,
        }

    return route_and_classify
