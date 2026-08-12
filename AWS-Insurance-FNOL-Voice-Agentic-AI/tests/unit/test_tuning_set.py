"""The Phase 7 tuning set — `BUILD-PLAN.md` §2.1.

Frozen before rung A runs. These tests are the frozen part: the ablation ladder's every result is
relative to this population, so a later edit that adds a few easy negatives would improve every
downstream number without improving anything. The composition assertions make that edit fail.

The **overlap** test is the one that matters most. The set's author was deliberately blind to the
independent held-out set, which means nobody in the authoring loop could check for duplication — so the
check belongs here, run on every commit, rather than being a thing that was verified once by hand on
2026-08-12 and asserted thereafter. If a tuning item ever duplicates a verification item, tuning against
this file becomes a way of tuning against that one, and the independent set's whole value is gone.
"""

from __future__ import annotations

import difflib
import re

import pytest

from evals.holdout import HoldoutKind, structural_summary
from fnol_voice_agent.models.enums import KabcoCode

_NEAR_DUPLICATE_RATIO = 0.80


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _texts(kind: HoldoutKind) -> list[str]:
    """Reads the raw YAML rather than going through `structural_summary`, because comparing two sets
    genuinely needs the strings. Confined to this module and to a comparison whose output is a count.
    """
    import yaml

    from evals.holdout import _DIRECTORIES, _FILENAMES

    path = _DIRECTORIES[kind] / _FILENAMES[kind]
    return [p["text"] for p in yaml.safe_load(path.read_text())["phrasings"]]


def test_tuning_set_composition_is_frozen() -> None:
    s = structural_summary(HoldoutKind.TUNING)
    assert s.total >= 75
    assert s.positives >= 40, "the ladder needs enough positives for recall to move measurably"
    assert s.negatives >= 30, (
        "false escalation is the metric Phase 7 exists to move, so the negative half carries the "
        "phase's central measurement -- a thin one would make every rung look better than it is"
    )
    assert s.duplicate_text_count() == 0


def test_every_kabco_code_is_present_and_the_escalation_mapping_holds() -> None:
    """`K/A/B/C` must escalate, `O` must not. A single violation would put a mislabelled item into
    the denominator of the ladder's headline metric."""
    s = structural_summary(HoldoutKind.TUNING)
    for code in KabcoCode:
        assert s.count(kabco=code) > 0, f"{code.value} is unrepresented"
        should_escalate = code is not KabcoCode.NO_INJURY
        assert (
            s.count(kabco=code, should_escalate=not should_escalate) == 0
        ), f"{code.value} items must all have should_escalate={should_escalate}"


def test_positives_are_weighted_toward_indirect_phrasing() -> None:
    """A set of clean keyword positives would score flatteringly and measure nothing, since keyword
    cases are exactly what the deterministic L1 layer already handles."""
    s = structural_summary(HoldoutKind.TUNING)
    obvious = sum(
        s.count(should_escalate=True, containing=word) for word in ("died", "dead", "injured")
    )
    assert obvious <= s.positives // 4, "too many positives use the obvious keyword"


@pytest.mark.parametrize("other", [HoldoutKind.INDEPENDENT, HoldoutKind.WEAK])
def test_tuning_items_do_not_duplicate_a_held_out_item(other: HoldoutKind) -> None:
    """Verified as 0 exact and 0 near-duplicates on 2026-08-12 and re-verified on every run since.

    The isolation protocol prevented the author from checking this themselves -- which is the point of
    the protocol and also why the check has to live somewhere that runs without them.
    """
    tuning = {_normalise(t) for t in _texts(HoldoutKind.TUNING)}
    held_out = {_normalise(t) for t in _texts(other)}

    assert not tuning & held_out, f"exact overlap with the {other} set"

    near = [
        (t, h)
        for t in tuning
        for h in held_out
        if difflib.SequenceMatcher(None, t, h).ratio() >= _NEAR_DUPLICATE_RATIO
    ]
    assert not near, f"near-duplicates of {other} items (ratio >= {_NEAR_DUPLICATE_RATIO}): {near}"
