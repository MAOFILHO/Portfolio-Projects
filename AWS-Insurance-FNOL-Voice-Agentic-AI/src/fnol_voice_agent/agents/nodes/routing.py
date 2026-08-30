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


def _confirmation_already_resolved(state: AgentState) -> bool:
    """D-new (live repro: contacts `003af9a0-bc53-45a7-a223-490001660e5b`/22:40,
    `f9a25ea6-eaa8-4b20-90f2-56f55d552ea4`/22:42, both `graph_intent=Ambiguous` on a bare "No").
    True when `active_slot` is an `AMAZON.Confirmation` slot AND Lex has already delivered this
    turn's interpretedValue for it -- the classifier cannot add anything on that turn, only
    misclassify a content-free "Yes"/"No" (unlike `D204`/`OI122`'s soft-prompt precedence clause,
    which does hold for a domain term like "Comprehensive" -- this is a structural gap, not a
    prompting one, hence the structural fix here rather than in `bedrock_router.py`).

    The signal is `isinstance(filled_slots[active_slot], bool)`, not a hand-maintained list of
    confirmation slot names mirrored from `bot.yaml.tftpl` (the `D78` drift this project has
    already been burned by once). It works because of two facts, each already relied on
    elsewhere and not invented for this check:

    1. `_coerce_slot_value` (`api/lex_codehook.py:540`) only ever produces a Python `bool` from
       Lex's literal `"Yes"`/`"No"` -- its own docstring: "No other slot type in this bot ever
       resolves to exactly Yes/No, so this coercion is safe applied blind." A `bool` in
       `filled_slots` is therefore proof the slot IS `AMAZON.Confirmation`-typed.
    2. A slot only ever becomes `active_slot` while still missing from `filled_slots`
       (`file_auto_claim.py`'s `_next_missing_slot`/`update_contact_info.py`'s equivalent, both
       clearing the confirm-slot key before re-asking on decline) -- so a value present for it now
       can only have arrived via THIS turn's `_merged_filled_slots` (`api/lex_codehook.py:573`),
       never a stale leftover from an earlier turn.

    This couples this check to `_coerce_slot_value`'s existing assumption rather than to a second,
    independently-drifting copy of it: if that assumption ever breaks (a future slot type also
    resolving to literal "Yes"/"No"), both break together, in the same place, not silently apart.
    """
    active_slot = state.get("active_slot")
    if not active_slot:
        return False
    filled_slots = state.get("filled_slots") or {}
    return isinstance(filled_slots.get(active_slot), bool)


def make_route_and_classify_node(*, caller: BedrockConverseCaller | None = None) -> NodeFn:
    def route_and_classify(state: AgentState) -> dict[str, Any]:
        if _confirmation_already_resolved(state):
            # Skip the Bedrock call entirely and let the coerced value flow through: reuse the
            # intent this call was already routing under (the checkpointer's persisted `intent`
            # from the turn that set this `active_slot` in the first place -- `route_and_classify`
            # is the only node that ever writes `intent`, so it is still last turn's value here,
            # before this branch would otherwise overwrite it). `safety_flag` is `l1_safety_flag`
            # only, no `classification.safety_flag` to union with -- `l1_safety_check` already
            # guarantees `l1_safety_flag` is False on every turn that reaches this node, and a bare
            # "Yes"/"No" carries no injury signal for L2 to have found anyway.
            return {
                "safety_flag": state.get("l1_safety_flag", False),
                "intent": state.get("intent"),
                "intent_confidence": 1.0,
                "coverage_question_type": state.get("coverage_question_type", "not_applicable"),
            }

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
