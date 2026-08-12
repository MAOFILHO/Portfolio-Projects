"""Composition tests for the Phase 6 golden set.

These are not tests of the agent. They are tests of the *measuring instrument* — the mechanism that makes
`SUCCESS-METRICS.md` §9's "narrow the golden set to easy cases" gaming route cost a reviewed diff instead
of a quiet deletion. A corpus that silently loses its hard cases produces better numbers with no code
change anywhere, which is precisely why the guard belongs in CI rather than in a reviewer's memory.
"""

from __future__ import annotations

import pytest

from evals.schema import (
    CATEGORY_MINIMUMS,
    INTENT_MINIMUMS,
    MINIMUM_TOTAL,
    Category,
    GoldenConversation,
    KabcoCode,
    OutcomeKind,
    load_golden_set,
)


@pytest.fixture(scope="module")
def golden() -> list[GoldenConversation]:
    return load_golden_set()


def test_every_golden_file_parses_and_validates(golden: list[GoldenConversation]) -> None:
    """`load_golden_set` raises on the first invalid file, so reaching this assertion at all means the
    whole corpus validated."""
    assert golden, "golden set is empty"


def test_total_meets_the_roadmap_minimum(golden: list[GoldenConversation]) -> None:
    assert (
        len(golden) >= MINIMUM_TOTAL
    ), f"{len(golden)} conversations, roadmap requires >= {MINIMUM_TOTAL}"


@pytest.mark.parametrize("category", list(Category))
def test_category_minimum(golden: list[GoldenConversation], category: Category) -> None:
    count = sum(1 for c in golden if c.category is category)
    assert count >= CATEGORY_MINIMUMS[category], (
        f"category {category} has {count}, minimum is {CATEGORY_MINIMUMS[category]}. "
        f"Lowering the minimum to make this pass is the gaming route SUCCESS-METRICS.md §9 names."
    )


@pytest.mark.parametrize("intent", list(INTENT_MINIMUMS))
def test_intent_minimum(golden: list[GoldenConversation], intent: object) -> None:
    count = sum(1 for c in golden if c.intent is intent)
    assert count >= INTENT_MINIMUMS[intent], (  # type: ignore[index]
        f"intent {intent} has {count}, minimum is {INTENT_MINIMUMS[intent]}"  # type: ignore[index]
    )


def test_every_ka_safety_case_escalates(golden: list[GoldenConversation]) -> None:
    """The escalation-recall GATE's denominator. Enforced by the schema too, but asserted here because
    this is the property the whole safety argument rests on, and it should fail visibly by name."""
    for c in golden:
        if c.kabco in (KabcoCode.K, KabcoCode.A):
            assert c.outcome.kind is OutcomeKind.ESCALATED, f"{c.id}: KABCO {c.kabco} must escalate"


def test_bc_severity_cases_exist_and_do_not_auto_escalate(golden: list[GoldenConversation]) -> None:
    """`SUCCESS-METRICS.md` §2's injury-severity discrimination TARGET: the system must not escalate
    every scraped knee. Without B/C cases in the corpus, a detector that escalates on any injury word
    would score 100% recall and look perfect — the set has to be able to catch over-escalation."""
    bc = [c for c in golden if c.kabco in (KabcoCode.B, KabcoCode.C)]
    assert (
        len(bc) >= 3
    ), f"only {len(bc)} B/C-severity cases; recall cannot be distinguished from bias"
    assert any(
        c.outcome.kind is not OutcomeKind.ESCALATED for c in bc
    ), "every B/C case escalates, so the corpus cannot detect over-escalation at all"


def test_mandatory_escalations_are_derived_not_hand_labelled(
    golden: list[GoldenConversation],
) -> None:
    """`mandatory_escalation` drives the containment denominator (`SUCCESS-METRICS.md` §4). It is a
    derived property of the route, not an author-set flag, so it cannot drift from the route it is
    supposed to reflect. This asserts the derivation, i.e. that no route-1/2 conversation is treated as
    discretionary."""
    for c in golden:
        expected = c.outcome.escalation_route in (1, 2)
        assert c.mandatory_escalation is expected, c.id


def test_adversarial_and_ambiguity_cases_are_not_all_single_turn(
    golden: list[GoldenConversation],
) -> None:
    """A one-turn adversarial case tests classification. Multi-turn ones test whether the agent recovers,
    which is the harder and more realistic property — and the one a corpus drifts away from first,
    because single-turn cases are much easier to write."""
    hard = [c for c in golden if c.category in (Category.ADVERSARIAL, Category.AMBIGUITY)]
    multi = [c for c in hard if len(c.turns) > 1]
    assert len(multi) >= 5, f"only {len(multi)} multi-turn adversarial/ambiguity cases"


def test_ids_are_prefixed_by_category_or_intent(golden: list[GoldenConversation]) -> None:
    """Cheap readability guard: a failing eval reports an id, and an id that says nothing means opening
    the file to learn what broke."""
    for c in golden:
        assert (
            "-" in c.id and c.id.islower()
        ), f"{c.id}: expected lowercase kebab ids like 'fac-001'"


# --- Held-out sets ---------------------------------------------------------------------------------


def test_weak_holdout_set_loads_and_has_both_polarities() -> None:
    from evals.holdout import HoldoutKind, load_holdout

    phrasings = load_holdout(HoldoutKind.WEAK)
    positives = [p for p in phrasings if p.should_escalate]
    negatives = [p for p in phrasings if not p.should_escalate]
    assert len(positives) >= 12, "too few positives to make recall meaningful"
    assert (
        len(negatives) >= 6
    ), "without negatives, a detector that escalates on every utterance scores 100% recall"


def test_independent_holdout_set_exists_and_is_weighted_toward_indirect_phrasing() -> None:
    """Criterion 14's set, generated 2026-08-12 by an isolated agent that read only `evals/holdout.py`.

    Inverted from an assertion of absence, exactly as that test predicted it would be. The composition
    assertions matter more than the count: a set of clean keyword phrasings would score flatteringly and
    measure nothing, since clean keyword cases are what any lexicon already handles."""
    from evals.holdout import HoldoutKind, structural_summary

    # Goes through `structural_summary`, not `load_holdout`: since Phase 7 Stage 2 the independent set
    # is locked behind a declared `verification_run`, and a unit test is not one. The lock is on the
    # items; facts about the file stay freely checkable, which is exactly what this test needs.
    s = structural_summary(HoldoutKind.INDEPENDENT)
    assert s.total >= 35
    assert s.positives >= 20 and s.negatives >= 10
    # Fatality cases that never use the word "died" -- the euphemism axis the weak set under-covered.
    assert s.count(should_escalate=True, kabco=KabcoCode.K) >= 4
    assert (
        s.count(should_escalate=True, kabco=KabcoCode.K, containing="died") == 0
    ), "every fatality phrasing using the obvious keyword would make this set a keyword test"


def test_holdout_sets_cannot_be_loaded_blended() -> None:
    """`load_holdout` requires a `kind`. There is deliberately no function that returns both sets
    concatenated, because a single blended recall figure would conceal the gap between them -- and the
    gap is the measurement Marco asked for."""
    import evals.holdout as holdout_module

    assert not hasattr(holdout_module, "load_all_holdouts")
