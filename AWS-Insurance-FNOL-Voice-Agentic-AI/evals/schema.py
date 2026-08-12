"""Golden-conversation schema and loader (Phase 6, Stage 2).

`SUCCESS-METRICS.md` §9 lists "narrow the golden set to easy cases" as a named gaming route, countered by
"the set requires happy paths, edge cases, ambiguity, adversarial prompts and out-of-scope, with
per-category minimums; changes to it are reviewed as code." This module is how that counter is *enforced*
rather than merely intended: `CATEGORY_MINIMUMS` and `INTENT_MINIMUMS` are asserted by
`tests/unit/test_golden_set.py`, so a PR that deletes the hard conversations fails CI, and a PR that
lowers a minimum has to change a constant in a reviewed diff and say why.

## Why the expectations are deliberately narrow

Every field a golden conversation can assert is a field the harness actually grades. There is no
free-text "expected behaviour" field, because a corpus full of prose expectations reads like thorough
coverage and grades nothing. `notes` exists for the human reader and is never scored -- that separation is
the point of having both.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fnol_voice_agent.models.enums import Intent, KabcoCode

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


class Category(StrEnum):
    """The composition axes `SUCCESS-METRICS.md` §9 requires the set to span.

    Orthogonal to intent on purpose: "twelve `FileAutoClaim` conversations" says nothing about whether any
    of them is hard, and a set can hit every intent while being uniformly easy.
    """

    HAPPY_PATH = "happy_path"
    EDGE_CASE = "edge_case"
    AMBIGUITY = "ambiguity"
    ADVERSARIAL = "adversarial"
    OUT_OF_SCOPE = "out_of_scope"
    SAFETY = "safety"


class OutcomeKind(StrEnum):
    COMPLETED = "completed"  # the caller's task was finished by the agent
    ESCALATED = "escalated"  # transferred to a human, for any of DIALOGUE-POLICIES.md §8's routes
    ABSTAINED = "abstained"  # correctly declined -- scores as success (SUCCESS-METRICS.md §3)


class TurnExpectation(BaseModel):
    """What must hold after one caller turn. Every field is optional: a turn asserts only what it is
    actually about, so a slot-filling turn is not forced to restate an intent that has not changed.
    """

    model_config = ConfigDict(extra="forbid")

    intent: Intent | None = None
    intent_confidence_at_least: float | None = None
    safety_escalation: bool | None = None
    slots_filled: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[str] = Field(default_factory=list)
    response_includes: list[str] = Field(default_factory=list)
    response_excludes: list[str] = Field(default_factory=list)
    # Set on the turn where the retry ladder is expected to have counted an attempt, so the ONE shared
    # counter (DIALOGUE-POLICIES.md §7) is asserted by the corpus, not only by unit tests.
    retry_count_for_slot: dict[str, int] = Field(default_factory=dict)


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caller: str
    is_barge_in: bool = False
    expect: TurnExpectation = Field(default_factory=TurnExpectation)


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: OutcomeKind
    # DIALOGUE-POLICIES.md §8's routes 1-4, in priority order. Required for, and only for, escalations.
    escalation_route: int | None = Field(default=None, ge=1, le=4)
    escalation_layer: str | None = None  # "L1" | "L2" | "L3" | "capability" | "confidence"

    @model_validator(mode="after")
    def _route_iff_escalated(self) -> Outcome:
        escalated = self.kind is OutcomeKind.ESCALATED
        if escalated and self.escalation_route is None:
            raise ValueError("an escalated outcome must name which of §8's routes 1-4 fired")
        if not escalated and self.escalation_route is not None:
            raise ValueError("escalation_route is only meaningful on an escalated outcome")
        return self


class GoldenConversation(BaseModel):
    """One labelled conversation.

    `mandatory_escalation` is load-bearing rather than descriptive: `SUCCESS-METRICS.md` §4 excludes
    mandatory escalations (routes 1-2) from the containment denominator entirely, because counting a
    correctly-escalated injury call against containment would create pressure to suppress the exact
    behaviour this system exists to guarantee. The harness reads this field to build that denominator, so
    mislabelling it silently re-opens the gaming route Phase 1 closed -- hence the validator below deriving
    it from the route rather than trusting the author to set it consistently.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    category: Category
    intent: Intent | None  # the conversation's primary intent; None for out-of-scope
    description: str
    turns: list[Turn] = Field(min_length=1)
    outcome: Outcome
    tags: list[str] = Field(default_factory=list)
    # Seed state: what the agent is assumed to already know when the conversation opens (e.g. the caller
    # has been identified). Keeps a conversation about rental entitlement from spending four turns on
    # identification it is not trying to test.
    seed_slots: dict[str, Any] = Field(default_factory=dict)
    # Safety conversations only: the KABCO severity the phrasing indicates. K/A must escalate; B/C are the
    # discrimination TARGET (SUCCESS-METRICS.md §2) and must NOT be auto-escalated.
    kabco: KabcoCode | None = None
    notes: str = ""  # for the human reader. Never graded -- see the module docstring.

    @property
    def mandatory_escalation(self) -> bool:
        return self.outcome.escalation_route in (1, 2)

    @model_validator(mode="after")
    def _safety_conversations_are_labelled(self) -> GoldenConversation:
        if self.category is Category.SAFETY and self.kabco is None:
            raise ValueError(
                f"{self.id}: a safety conversation must carry a kabco label -- it is what puts it in "
                f"the denominator of the escalation-recall GATE, and what separates the K/A cases that "
                f"must escalate from the B/C cases that must not"
            )
        if self.kabco in (KabcoCode.K, KabcoCode.A):
            if self.outcome.kind is not OutcomeKind.ESCALATED:
                raise ValueError(
                    f"{self.id}: KABCO {self.kabco} indicates a fatality or incapacitating injury, so "
                    f"the only correct outcome is escalation (D12/D15, DIALOGUE-POLICIES.md §5)"
                )
        return self

    @model_validator(mode="after")
    def _out_of_scope_has_no_intent(self) -> GoldenConversation:
        if self.category is Category.OUT_OF_SCOPE and self.intent not in (
            None,
            Intent.OUT_OF_SCOPE,
        ):
            raise ValueError(
                f"{self.id}: an out-of-scope conversation cannot expect an in-scope intent"
            )
        return self


# --- Composition minimums -------------------------------------------------------------------------
#
# Changing a number here is a reviewed diff that has to justify itself, which is the whole mechanism.
# Lowering one to make a red build green is the gaming route SUCCESS-METRICS.md §9 names.

CATEGORY_MINIMUMS: dict[Category, int] = {
    Category.HAPPY_PATH: 12,
    Category.EDGE_CASE: 10,
    Category.AMBIGUITY: 6,
    Category.ADVERSARIAL: 8,
    Category.OUT_OF_SCOPE: 5,
    Category.SAFETY: 12,
}

# Every in-scope intent carries real weight. Without this, the category minimums alone could be met by a
# set that barely touches, say, UpdateContactInfo -- the intent with the write path and the confirmation
# policy, i.e. the one whose failure is a "critical defect, not a missed target" (Phase 1).
INTENT_MINIMUMS: dict[Intent, int] = {
    Intent.FILE_AUTO_CLAIM: 10,
    Intent.CHECK_CLAIM_STATUS: 6,
    Intent.COVERAGE_QUESTION: 9,
    Intent.RENTAL_TOWING_ENTITLEMENT: 7,
    Intent.UPDATE_CONTACT_INFO: 6,
    Intent.INJURY_ESCALATION: 10,
}

MINIMUM_TOTAL = 60


# --- Loading --------------------------------------------------------------------------------------


def load_file(path: Path) -> list[GoldenConversation]:
    """One file holds a `conversations:` list, grouped by intent or category.

    Grouped rather than one-file-per-conversation so the corpus stays reviewable as a whole: reading
    seventy sibling files to check that the `CoverageQuestion` cases actually span all three sub-question
    types is the kind of review nobody does twice. Diffs are still per-conversation blocks.
    """
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or "conversations" not in raw:
        raise ValueError(f"{path}: expected a mapping with a top-level 'conversations' list")
    entries = raw["conversations"]
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: 'conversations' must be a non-empty list")
    return [GoldenConversation.model_validate(entry) for entry in entries]


def iter_golden_paths(directory: Path = GOLDEN_DIR) -> Iterator[Path]:
    yield from sorted(directory.glob("*.yaml"))


def load_golden_set(directory: Path = GOLDEN_DIR) -> list[GoldenConversation]:
    """Loads and validates every conversation. Raises on the first invalid file rather than collecting
    errors: a malformed golden file means the corpus is not in a gradeable state, and grading a partial
    corpus would silently change the denominator of every rate the harness reports."""
    conversations = [c for p in iter_golden_paths(directory) for c in load_file(p)]
    ids = [c.id for c in conversations]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate golden conversation ids: {sorted(duplicates)}")
    return conversations
