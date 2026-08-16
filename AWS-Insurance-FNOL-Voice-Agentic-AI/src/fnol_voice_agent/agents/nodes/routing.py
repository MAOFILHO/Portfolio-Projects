"""The merged router + L2 safety-classification node -- wraps `aws/bedrock_router.classify_turn`
(`ADR-004`, `PROMPT-REGISTRY.md` §1.1). Runs only if L1 didn't already terminate the turn (enforced by
`agents/graph.py`'s conditional edge out of `l1_safety_check`, not by this node itself).
"""

from __future__ import annotations

from typing import Any

from fnol_voice_agent.agents.state import AgentState, NodeFn
from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller, classify_turn


def _build_classify_messages(state: AgentState) -> list[dict[str, Any]]:
    """Builds the Converse message list for `classify_turn`, folding in the session context
    already sitting in `state` -- `active_slot`/`filled_slots` -- per `classify_turn`'s own
    docstring ("...and any prior context the graph wants the classifier to see... conversation
    assembly, which is Stage 6's job") and `_CLASSIFY_TURN_SYSTEM_PROMPT`'s existing instruction
    ("Classify `intent` from the caller's turn and prior context"). `D90` part 1
    (`RESULTS.md` §33/§35): this wiring never existed -- the classifier judged bare turn text
    with no signal that a slot was already pending or already answered, so a continuation turn
    ("12345", "yes", "rental") was classified as if it were a fresh, contextless utterance.

    When neither `active_slot` nor `filled_slots` is set -- the common first-turn case, no
    dialogue state collected yet -- this returns the exact same single-line message the node
    sent before this fix, so first-turn classification behavior, including everything already
    measured by `C1`/`C14`, is untouched by this change.
    """
    turn_text = state.get("turn_input", "")
    active_slot = state.get("active_slot")
    filled_slots = state.get("filled_slots")
    context_lines: list[str] = []
    if active_slot:
        context_lines.append(f"Currently eliciting slot: {active_slot}")
    if filled_slots:
        context_lines.append(f"Already collected this call: {filled_slots}")
    if not context_lines:
        return [{"role": "user", "content": [{"text": turn_text}]}]
    context_block = "\n".join(context_lines)
    text = f"{context_block}\n\nCaller's turn: {turn_text}"
    return [{"role": "user", "content": [{"text": text}]}]


def make_route_and_classify_node(*, caller: BedrockConverseCaller | None = None) -> NodeFn:
    def route_and_classify(state: AgentState) -> dict[str, Any]:
        messages = _build_classify_messages(state)
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
