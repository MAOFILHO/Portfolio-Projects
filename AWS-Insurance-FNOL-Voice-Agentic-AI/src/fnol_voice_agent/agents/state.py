"""LangGraph state schema (Stage 6/7, `docs/phase5/BUILD-PLAN.md`).

A `TypedDict`, not a Pydantic model -- LangGraph's standard convention: each node returns a partial dict of
the keys it changed, which LangGraph shallow-merges (last writer wins per key, no custom reducer needed
here since exactly one node touches any given key on a given turn, including the dict-valued fields --
every node that updates `retry_counts`/`filled_slots` reads the previous value from state and writes back
the whole updated dict itself, per `agents/retry_ladder.py`'s contract).

Persisted across turns by the DynamoDB checkpointer (`aws/checkpointer.py`, `ADR-005`), keyed on
`contact_id` (the Connect contact ID) as the LangGraph thread ID -- this is what makes `retry_counts` and
`filled_slots` durable turn-to-turn rather than reset on every invocation.
"""
from __future__ import annotations

from typing import Any, TypedDict


class EscalationRecord(TypedDict):
    """What gets handed to the human, per `DIALOGUE-POLICIES.md` §5 step 3 / §8's escalation-trigger
    table -- which route fired, which layer/trigger caused it, and the full context captured so far."""

    contact_id: str
    triggering_layer: str  # "L1" | "L2" | "L3" | "capability" | "confidence"
    route: int  # 1-4, DIALOGUE-POLICIES.md §8, in priority order
    reason: str
    context: dict[str, Any]


class AgentState(TypedDict, total=False):
    # --- Per-turn input, supplied by the (not-yet-built, Phase 8) Lex/Connect integration layer ---
    contact_id: str
    turn_input: str  # raw ASR transcript for this turn
    is_barge_in: bool  # whether this turn interrupted a prior bot prompt (DIALOGUE-POLICIES.md §6)

    # --- L1 (deterministic pre-node, D12/D15) ---
    l1_safety_flag: bool
    l1_matched_term: str | None

    # --- Merged router + L2 output (ADR-004, PROMPT-REGISTRY.md §1.1) ---
    safety_flag: bool  # union of L1 and L2 per D15 -- either firing sets this
    intent: str  # one of models.enums.Intent's values
    intent_confidence: float
    coverage_question_type: str  # one of models.enums.CoverageQuestionType's values

    # --- Guardrails (ADR-010) ---
    guardrail_input_blocked: bool
    guardrail_output_blocked: bool

    # --- Durable dialogue state, carried turn-to-turn via the checkpointer ---
    active_slot: str | None  # the slot/question currently being elicited, for retry-ladder keying
    filled_slots: dict[str, Any]  # accumulated slot values for the in-progress FileAutoClaim intake
    retry_counts: dict[str, int]  # the ONE shared no-match/barge-in retry ladder (DIALOGUE-POLICIES.md §7)

    # --- This turn's outcome ---
    response_text: str
    escalation: EscalationRecord | None
    turn_log: list[str]  # thin structlog-style trace of node transitions (Stage 7's observability slice)
