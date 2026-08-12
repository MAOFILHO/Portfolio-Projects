"""The ablation ladder's own validity — `scripts/run_ablation_ladder.py`, Stage 4.

The ladder produces the numbers that decide `ADR-014`'s open question, so the ways it can be wrong are
worth more attention than the ways a normal script can be wrong. Two of them are silent:

* **Rung B stops being an ablation** if the schema surgery no-ops. B would then be a duplicate of A, the
  B−A delta would be noise reported as a finding, and nothing would look broken.
* **Rung D trades recall for precision** if its revised prompt drops the recall bias. That is the one
  trade `C1` forbids outright, and it would show up as a beautiful false-escalation number.

Both are checked here rather than trusted.
"""

from __future__ import annotations

from typing import Any

import pytest

from fnol_voice_agent.aws.bedrock_router import build_classify_turn_tool_spec
from fnol_voice_agent.models.enums import Intent
from scripts.run_ablation_ladder import (
    _REVISED_DETECTOR_PROMPT,
    RUNGS,
    _build_no_injury_tool_spec,
)


def _intent_enum(spec: dict[str, Any]) -> list[str]:
    for definition in spec["toolSpec"]["inputSchema"]["json"]["$defs"].values():
        if "enum" in definition and Intent.COVERAGE_QUESTION.value in definition["enum"]:
            return list(definition["enum"])
    raise AssertionError("no intent enum found in the tool spec")


# --- Rung B is a real ablation --------------------------------------------------------------------


def test_rung_b_removes_injury_escalation_from_the_enum() -> None:
    assert Intent.INJURY_ESCALATION.value in _intent_enum(build_classify_turn_tool_spec())
    assert Intent.INJURY_ESCALATION.value not in _intent_enum(_build_no_injury_tool_spec())


def test_rung_b_changes_nothing_else_about_the_schema() -> None:
    """B−A must attribute to the label space and nothing else. One stray difference and the delta
    measures two changes at once."""
    baseline = _intent_enum(build_classify_turn_tool_spec())
    rung_b = _intent_enum(_build_no_injury_tool_spec())
    assert rung_b == [v for v in baseline if v != Intent.INJURY_ESCALATION.value]

    spec_a, spec_b = build_classify_turn_tool_spec(), _build_no_injury_tool_spec()
    assert spec_a["toolSpec"]["name"] == spec_b["toolSpec"]["name"]
    schema_a = spec_a["toolSpec"]["inputSchema"]["json"]
    schema_b = spec_b["toolSpec"]["inputSchema"]["json"]
    assert schema_a["properties"] == schema_b["properties"]
    assert schema_a.get("required") == schema_b.get("required")


def test_rung_b_does_not_mutate_the_shipped_spec() -> None:
    """`build_classify_turn_tool_spec()` returns a fresh dict each call, but if that ever changed to a
    cached constant, the surgery would corrupt production's schema and the ladder would be measuring
    rung B four times."""
    _build_no_injury_tool_spec()
    assert Intent.INJURY_ESCALATION.value in _intent_enum(build_classify_turn_tool_spec())


def test_rung_b_fails_loudly_if_the_schema_shape_moves(monkeypatch: Any) -> None:
    """A schema-shape change must break the run, not silently produce rung A twice."""
    import scripts.run_ablation_ladder as ladder

    monkeypatch.setattr(
        ladder,
        "build_classify_turn_tool_spec",
        lambda: {"toolSpec": {"name": "classify_turn", "inputSchema": {"json": {}}}},
    )
    with pytest.raises(RuntimeError, match="meaningless B-A delta"):
        ladder._build_no_injury_tool_spec()


# --- Rung D does not trade away recall ------------------------------------------------------------


def test_the_revised_detector_prompt_keeps_the_recall_bias() -> None:
    """`C1` is not tradeable: *"Any configuration that reduces it is rejected regardless of what it
    buys."* A revised prompt that quietly drops "when in doubt, true" would buy false-escalation
    improvements with recall, which is the one purchase this phase may not make."""
    assert "when in doubt" in _REVISED_DETECTOR_PROMPT.lower()


def test_the_revised_detector_prompt_only_adds_the_measured_distinctions() -> None:
    """Rung D is capped at 3 revisions and this is revision 1. Its edit is narrow on purpose: the two
    false-positive shapes the Phase 6 error analysis actually found (vehicle damage in human terms,
    a bare mention that a collision occurred), not a rewrite."""
    lowered = _REVISED_DETECTOR_PROMPT.lower()
    assert "vehicle" in lowered
    assert "a person" in lowered
    # Still a single-purpose detector: no intent classification has crept in.
    assert "intent" in lowered and "you do not classify" in lowered


def test_the_ladder_is_cumulative_and_ordered() -> None:
    """Each rung adds one change to the previous one, which is what makes pairwise deltas
    attributable. Order matters for the same reason."""
    assert [name for name, _description, _run in RUNGS] == ["A", "B", "C", "D"]


# --- Dropped classifier fields are scored, not excluded -------------------------------------------


def _fixed_rung(intent: Intent | None, *, safety: bool = False) -> Any:
    from scripts.run_ablation_ladder import TurnOutcome

    def run(_text: str, _caller: Any) -> TurnOutcome:
        return TurnOutcome(safety_flag=safety, intent=intent, latencies={}, error=None)

    return run


def test_a_dropped_classification_is_counted_and_not_skipped() -> None:
    """The pre-registered rule: a turn the system could not classify is a turn it got wrong. The
    turn stays in the denominator."""
    from evals.schema import load_golden_set
    from scripts.run_ablation_ladder import _measure_intent

    conversations = load_golden_set()
    _f1, _raw, _oos, _unstable, confusions, drops = _measure_intent(
        _fixed_rung(None), caller=None, conversations=conversations, k=1
    )
    labelled = sum(1 for c in conversations if (c.turns[0].expect.intent or c.intent) is not None)
    assert drops == labelled, "every call dropped, so every call should be counted as a drop"
    assert len(confusions) == labelled, "a dropped turn is a confusion, not an exclusion"


def test_dropping_cannot_score_better_than_answering_correctly() -> None:
    """The property that matters: a configuration cannot improve its macro-F1 by failing on the
    turns it finds hardest."""
    from evals.schema import load_golden_set
    from scripts.run_ablation_ladder import _measure_intent

    conversations = load_golden_set()
    dropped_f1, _r, _o, _u, _c, _d = _measure_intent(
        _fixed_rung(None), caller=None, conversations=conversations, k=1
    )
    guessing_f1, _r2, _o2, _u2, _c2, _d2 = _measure_intent(
        _fixed_rung(Intent.COVERAGE_QUESTION), caller=None, conversations=conversations, k=1
    )
    assert dropped_f1 is not None and guessing_f1 is not None
    assert (dropped_f1.value or 0.0) == 0.0
    # A confident wrong answer scores at least as well, because it can still be right sometimes.
    # Stated rather than hidden: dropping incurs a false negative but no false positive, so it is
    # not scored *worse* than an equally wrong guess -- only never better than a correct one.
    assert (guessing_f1.value or 0.0) >= (dropped_f1.value or 0.0)


def test_a_classifier_drop_keeps_its_turn_in_the_escalation_denominator() -> None:
    """The pre-registered rule -- a classifier drop cannot cost escalation metrics -- is only true if
    the safety verdict survives the classifier's failure. It did not, until the discard-bug fix.

    **This test previously asserted the opposite** (`union.total == 0`), encoding the bug as the
    expected behaviour. That is the trap in writing a test against observed output: the harness and
    the test agreed with each other and both were wrong, and the disagreement only surfaced when the
    denominator in a published number turned out to be 31 instead of 35.
    """
    from evals.holdout import HoldoutKind, structural_summary
    from scripts.run_ablation_ladder import _measure_escalation

    union, _l2, _unstable, _lat, drops, det_drops, breaches = _measure_escalation(
        _fixed_rung(None), None, 1
    )
    summary = structural_summary(HoldoutKind.TUNING)
    assert drops == summary.total, "every sample dropped its classifier field"
    assert det_drops == 0 and breaches == []
    assert union.total == summary.total, (
        "a classifier drop must not remove its turn from the escalation denominator -- doing so "
        "flatters the rung by excluding exactly the turns it failed on"
    )


def _detector_dropping_rung() -> Any:
    """Every call loses the safety verdict -- the failure the first ladder run died on."""
    from scripts.run_ablation_ladder import TurnOutcome

    def run(_text: str, _caller: Any) -> TurnOutcome:
        return TurnOutcome(
            safety_flag=False,
            intent=None,
            latencies={},
            error="missing:injury_indicated",
            detector_dropped=True,
        )

    return run


def test_a_missing_safety_verdict_on_a_must_escalate_turn_is_a_c1_breach() -> None:
    """PRE-REGISTRATION-dropped-safety-flag.md section 2: *"Silence is not a pass."* A turn where the
    detector produced no verdict and L1 was silent is a union-recall MISS, not an exclusion."""
    from scripts.run_ablation_ladder import _measure_escalation

    union, _l2, _unstable, _lat, _drops, det_drops, breaches = _measure_escalation(
        _detector_dropping_rung(), None, 1
    )
    assert det_drops > 0
    assert breaches, "must-escalate turns with no verdict have to surface as C1 breaches"
    assert (union.recall.value or 1.0) < 1.0, "a silent detector cannot score perfect recall"


def test_a_missing_safety_verdict_on_a_must_not_escalate_turn_is_excluded_not_counted() -> None:
    """The other half of the same pre-registered table, and the asymmetry is deliberate: scoring a
    no-verdict turn as a non-escalation for BOTH metrics would let one event improve one number
    while damaging the other, which is the shape of a metric that can be gamed."""
    from evals.holdout import HoldoutKind, structural_summary
    from scripts.run_ablation_ladder import _measure_escalation

    union, _l2, _unstable, _lat, _drops, _det, _breaches = _measure_escalation(
        _detector_dropping_rung(), None, 1
    )
    negatives = structural_summary(HoldoutKind.TUNING).negatives
    scored_negatives = union.true_negatives + union.false_positives
    assert scored_negatives == 0, (
        f"all {negatives} must-not-escalate turns dropped their verdict and must be excluded from "
        f"the false-escalation denominator, not scored as clean passes"
    )
