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


def test_the_l1_gate_passes_after_the_stage_5_lexicon_fix() -> None:
    """Inverted from its original form, which asserted the gate FAILED at 0.778 with a missed fatality.

    That inversion is the mechanism working, not a test being loosened. The original assertion existed
    so that a later lexicon patch could not absorb the result silently -- it broke, which forced the
    before/after numbers into RESULTS.md instead of letting the improvement pass unremarked. The
    pre-fix reading is preserved immutably in evals/baselines/l1_before_fix_20260812.json.

    Scoped to the L1 gate specifically. `gate_failures` is not empty overall -- the retrieval gate fails
    at 0.800 -- and asserting emptiness here would couple an L1 assertion to an unrelated metric, so a
    retrieval improvement would silently "fix" a test about the lexicon."""
    l1_failures = [f for f in gate_failures(run_tier_a()) if "L1" in f]
    assert l1_failures == []


def test_the_gate_is_not_green_by_construction() -> None:
    """A gate that cannot fail is not a gate. Feeds the detector a case it has no entry for and
    confirms the harness would report it -- so the passing result above means something."""
    from evals.metrics import BinaryClassificationCounts
    from evals.tier_a import L1Result, TierAReport, gate_failures as gf

    missing = BinaryClassificationCounts(true_positives=8, false_negatives=1)
    fabricated = TierAReport(
        l1_golden=L1Result("synthetic", missing, ["inj-999: 'we lost her'"]),
        l1_holdout_weak=None,
        l1_holdout_independent=None,
        conversation_count=0,
        turn_count=0,
        category_counts={},
        mandatory_escalation_count=0,
    )
    failures = gf(fabricated)
    assert len(failures) == 1
    assert "inj-999" in failures[0]


def test_report_serialises_counts_not_only_rates() -> None:
    """A baseline that stored only rates could never be re-analysed for a metric this version did not
    happen to compute. Counts are the durable artifact."""
    payload = to_dict(run_tier_a())
    golden = payload["l1_golden"]
    assert golden is not None
    for key in ("true_positives", "false_positives", "true_negatives", "false_negatives"):
        assert key in golden


def test_independent_holdout_results_are_serialised_separately_from_the_weak_set() -> None:
    """Never blended. The gap between the two is the informative quantity -- a single averaged recall
    figure would conceal exactly the author-blind-spot measurement Marco asked for."""
    payload = to_dict(run_tier_a())
    assert payload["l1_holdout_independent"] is not None
    assert payload["l1_holdout_weak"] is not None
    assert (
        payload["l1_holdout_independent"]["recall"] != payload["l1_holdout_weak"]["recall"]
    ), "the two sets scoring identically would be surprising enough to warrant checking the loader"


# --- Retrieval on real Titan vectors ---------------------------------------------------------------


def test_every_gold_label_resolves_to_a_real_chunk() -> None:
    """The third instrument bug of Phase 6, as a standing guard.

    A gold label naming text that exists nowhere in the corpus yields `rank None`, which is
    arithmetically identical to the retriever failing to find a passage that WAS there. Two of the first
    ten graded queries were broken this way and would have been published as retrieval failures --
    recall would have read 0.700 instead of 0.800, and the obvious next move ("improve retrieval") would
    have been effort spent on a defect that did not exist."""
    from evals.retrieval import validate_gold_labels

    assert validate_gold_labels() == []


def test_retrieval_runs_offline_from_the_committed_fixture() -> None:
    """No credentials, no network, no cost -- the whole point of caching real vectors. Embeddings are a
    deterministic function of unchanged text, so caching them loses nothing; caching a *generation* would
    freeze a stochastic process and hide the variance Phase 6 exists to observe."""
    from evals.retrieval import evaluate_retrieval

    report = evaluate_retrieval()
    assert report.model_id == "amazon.titan-embed-text-v2:0"
    assert report.recall_at_5.denominator == 10


def test_mrr_averages_over_all_queries_including_misses() -> None:
    """A miss contributes 0, not exclusion. Averaging over hits only would report the mean rank of the
    successes and quietly drop the failures out of the denominator."""
    from evals.retrieval import evaluate_retrieval

    report = evaluate_retrieval()
    ranks = list(report.per_query_rank.values())
    expected = sum(0.0 if r is None else 1.0 / r for r in ranks) / len(ranks)
    assert report.mrr is not None
    assert abs(report.mrr - expected) < 1e-9


def test_retrieval_gate_fails_at_the_current_real_number() -> None:
    """recall@5 is 0.800 against a 0.90 GATE. Asserted rather than left implicit so the failure cannot be
    absorbed silently, and so a later improvement forces a re-report -- same mechanism as the L1 gate.
    """
    failures = gate_failures(run_tier_a())
    assert any("retrieval recall@5" in f for f in failures)
