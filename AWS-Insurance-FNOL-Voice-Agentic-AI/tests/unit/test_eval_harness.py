"""Tests for the eval harness itself.

The harness is the instrument every published number comes from, so its own bugs are worse than the
agent's: an agent defect produces a bad number that someone investigates, while a harness defect produces
a *good* number that nobody does. Stage 3 already produced one such bug — the L1 gate was scoring
`inj-011` as a miss when the corpus explicitly expects L2 to catch it, which would have driven exactly
the wrong fix (stuffing euphemisms into the deterministic lexicon).
"""

from __future__ import annotations

from evals.metrics import BinaryClassificationCounts, Rate, macro_f1
from evals.report import to_dict
from evals.schema import load_golden_set
from evals.tier_a import escalation_outcome_consistency, gate_failures, run_tier_a


def test_rate_of_an_empty_denominator_is_none_not_zero() -> None:
    """The single most important property in metrics.py. A recall of "0.000" over zero cases reads, in a
    report, as a catastrophic failure; a recall of "1.000" reads as perfect. Both are fabrications.
    """
    empty = Rate(0, 0)
    assert empty.value is None
    assert "n/a" in str(empty)


def test_rate_reports_counts_alongside_the_ratio() -> None:
    assert str(Rate(19, 20)) == "0.950 (19/20)"


def test_counts_track_both_directions() -> None:
    counts = BinaryClassificationCounts()
    counts = counts.observe(expected=True, actual=True)
    counts = counts.observe(expected=True, actual=False)
    counts = counts.observe(expected=False, actual=True)
    counts = counts.observe(expected=False, actual=False)
    assert counts.recall.value == 0.5
    assert counts.precision.value == 0.5
    assert counts.false_escalation_rate.value == 0.5
    assert counts.total == 4


def test_macro_f1_ignores_classes_with_no_cases() -> None:
    """A class with zero cases must not drag the macro average toward zero — it is unmeasured, not bad."""
    perfect = BinaryClassificationCounts(true_positives=5, true_negatives=5)
    absent = BinaryClassificationCounts()
    result = macro_f1({"a": perfect, "b": absent})
    assert result is not None
    assert result.value == 1.0


def test_macro_f1_of_nothing_is_none() -> None:
    assert macro_f1({"a": BinaryClassificationCounts()}) is None


def test_l2_delegated_cases_are_excluded_from_l1_counts_not_scored_as_misses() -> None:
    """The Stage 3 harness bug, as a regression test. `inj-011` is labelled `escalation_layer: L2`
    because the corpus expects the euphemistic phrasing to fall through the deterministic lexicon —
    that is the layered design working. Counting it as an L1 miss would report the design as a defect.
    """
    report = run_tier_a()
    deferred_ids = [d.split(":")[0] for d in report.l1_golden.deferred_to_l2]
    assert "inj-011" in deferred_ids
    assert not any("inj-011" in m for m in report.l1_golden.missed)


def test_corpus_labelling_is_self_consistent() -> None:
    assert escalation_outcome_consistency(load_golden_set()) == []


def test_the_l1_gate_currently_fails_and_names_what_it_missed() -> None:
    """Phase 6 is pre-tuning, and this gate failing is a legitimate, recorded outcome rather than
    something to fix into silence. Asserting the failure keeps it honest in both directions: the gate is
    demonstrably capable of failing (it is not green by construction), and if someone later patches the
    lexicon the assertion breaks and forces the result to be re-reported rather than absorbed."""
    failures = gate_failures(run_tier_a())
    assert len(failures) == 1
    assert "inj-004" in failures[0], "the missed fatality case must be named in the gate output"


def test_report_serialises_counts_not_only_rates() -> None:
    """A baseline that stored only rates could never be re-analysed for a metric this version did not
    happen to compute. Counts are the durable artifact."""
    payload = to_dict(run_tier_a())
    golden = payload["l1_golden"]
    assert golden is not None
    for key in ("true_positives", "false_positives", "true_negatives", "false_negatives"):
        assert key in golden


def test_absent_holdout_set_serialises_as_null_not_as_zero() -> None:
    payload = to_dict(run_tier_a())
    assert payload["l1_holdout_independent"] is None
