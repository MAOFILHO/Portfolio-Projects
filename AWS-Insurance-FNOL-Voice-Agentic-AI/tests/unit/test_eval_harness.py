"""Tests for the eval harness itself.

The harness is the instrument every published number comes from, so its own bugs are worse than the
agent's: an agent defect produces a bad number that someone investigates, while a harness defect produces
a *good* number that nobody does. Stage 3 already produced one such bug — the L1 gate was scoring
`inj-011` as a miss when the corpus explicitly expects L2 to catch it, which would have driven exactly
the wrong fix (stuffing euphemisms into the deterministic lexicon).
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_the_retrieval_gate_now_passes_at_exactly_its_threshold_and_why_that_is_not_a_clean_pass() -> (
    None
):
    """recall@5 is **0.900 against a 0.90 GATE** -- met exactly, and only after Stage R corrected the
    `cq-008` gold label. It read 0.800 before that.

    This test replaces `test_retrieval_gate_fails_at_the_current_real_number`, which did its job: the
    old test asserted the failure specifically so that a later improvement would force a re-report
    rather than being absorbed silently. It forced this one.

    Three facts are pinned here rather than left to `RESULTS.md`, because a green suite is what a reader
    checks first:

    1. The threshold is met **exactly**. With n=10 the metric's resolution is 0.1, so this GATE is
       literally "at most one miss" and one query decides it.
    2. The label correction was made **after** seeing the failure. It is right on the merits and was
       found by auditing all ten labels rather than the two that failed -- but a threshold met by a
       post-hoc correction is not the same as one met by a pre-registered measurement, and this project
       does not let that distinction blur (`RESULTS.md` §5.1).
    3. `cq-005` is still a genuine miss at rank 8, and it is the entire remaining gap on **both**
       retrieval numbers.
    """
    from evals.retrieval import evaluate_retrieval

    report = evaluate_retrieval()
    assert report.recall_at_5.value == 0.9
    assert report.per_query_rank["cq-005"] == 8, "the one genuine retrieval defect, undisturbed"
    assert (
        report.per_query_rank["cq-008"] == 1
    ), "the corrected label; the retriever was always right"
    assert "retrieval recall@5" not in " ".join(gate_failures(run_tier_a()))


def test_mrr_is_still_below_its_target_and_turns_on_the_same_single_query() -> None:
    """MRR 0.7458 against a 0.75 TARGET -- short by 0.0042. Not rounded up.

    The shortfall is smaller than most single-rank improvements available on this set, which is a
    statement about the instrument's resolution rather than about retrieval quality: moving `cq-005`
    from rank 8 to rank 6 would land on 0.74997, still under. It clears 0.75 at rank 5. The target and
    the gate therefore turn on the same one query, which is exactly why the fix for it is not being
    tuned into place against a 10-query set (`NOT-FIXED.md` item 6)."""
    from evals.retrieval import evaluate_retrieval

    report = evaluate_retrieval()
    assert report.mrr is not None
    assert report.mrr < 0.75


# --- The staleness guard that did not exist until Stage R -------------------------------------------


def test_a_gold_label_correction_cannot_silently_report_the_old_number(tmp_path: Path) -> None:
    """The Stage R instrument defect, as a standing guard.

    Gold labels are copied into the fixture and were covered by **neither** fingerprint. Correcting a
    label in `queries.py` therefore changed nothing about the measured number, and nothing warned:
    `evaluate_retrieval` read the fixture's stale copy. `RESULTS.md` §6 records Phase 6 correcting two
    labels -- that correction only took effect because the fixture happened to be re-embedded in the
    same pass. Skip the paid run and the fix is a no-op that looks applied.
    """
    import json
    import shutil

    from evals.retrieval import (
        FIXTURE_PATH,
        FixtureStaleError,
        evaluate_retrieval,
        fixture_is_stale,
    )

    copy = tmp_path / "fixture.json"
    shutil.copy(FIXTURE_PATH, copy)
    fixture = json.loads(copy.read_text())
    fixture["queries"][0]["gold_text_contains"] = "a label nobody agreed to"
    copy.write_text(json.dumps(fixture))

    reasons = fixture_is_stale(copy)
    assert any("gold labels" in r for r in reasons)
    # And it must be raised by the metric itself, not merely available to a caller who remembers to ask.
    # A staleness check nobody invokes is the same artifact the previous version was.
    with pytest.raises(FixtureStaleError):
        evaluate_retrieval(copy)


def test_a_label_change_does_not_claim_the_vectors_need_re_embedding(tmp_path: Path) -> None:
    """The reason the two fingerprints are separate: a label is not an embedding input. Conflating them
    would price a $0.00 repair as a billed Titan run, and the repair instructions have to be right or
    nobody follows them."""
    import json
    import shutil

    from evals.retrieval import FIXTURE_PATH, fixture_is_stale

    copy = tmp_path / "fixture.json"
    shutil.copy(FIXTURE_PATH, copy)
    fixture = json.loads(copy.read_text())
    fixture["queries"][0]["gold_source_file"] = "somewhere-else.md"
    copy.write_text(json.dumps(fixture))

    reasons = fixture_is_stale(copy)
    assert reasons, "a changed gold label is a staleness condition"
    assert all("$0.00" in r for r in reasons)
    assert not any("re-embed" in r.lower() for r in reasons)


def test_refresh_labels_refuses_when_the_corpus_itself_has_changed(tmp_path: Path) -> None:
    """The $0.00 path must not be usable to paper over the condition that needs the paid one. A label
    refresh that accepted a changed corpus would clear the warning and leave the vectors describing text
    that no longer exists -- while printing a reassuring message."""
    import json
    import shutil

    from evals.retrieval import FIXTURE_PATH, FixtureStaleError, refresh_labels

    copy = tmp_path / "fixture.json"
    shutil.copy(FIXTURE_PATH, copy)
    fixture = json.loads(copy.read_text())
    fixture["fingerprint"] = "the corpus moved under us"
    copy.write_text(json.dumps(fixture))

    with pytest.raises(FixtureStaleError, match="Re-embed"):
        refresh_labels(copy)


def test_label_fingerprint_separates_its_fields() -> None:
    """`("cq-1", "a", "bc")` and `("cq-1", "ab", "c")` are different labels and must not hash alike.
    Concatenating fields without a separator is the standard way to make two different sets agree.
    """
    from evals.retrieval import label_fingerprint

    assert label_fingerprint([("cq-1", "a", "bc")]) != label_fingerprint([("cq-1", "ab", "c")])


# --- Regression gate -------------------------------------------------------------------------------


def test_regression_gate_catches_a_degraded_metric() -> None:
    from evals.regression import compare

    baseline = {"l1_golden": {"recall": 1.0}}
    current = {"l1_golden": {"recall": 0.80}}
    regressions = compare(baseline, current)
    assert len(regressions) == 1
    assert regressions[0].baseline == 1.0 and regressions[0].current == 0.80


def test_regression_gate_never_blocks_an_improvement() -> None:
    from evals.regression import compare

    assert compare({"l1_golden": {"recall": 0.80}}, {"l1_golden": {"recall": 1.0}}) == []


def test_a_lower_false_escalation_rate_is_an_improvement_not_a_regression() -> None:
    """The comparison direction is inverted for rates where smaller is better. Getting this backwards
    would build a gate that rewards escalating more often, which is the exact behaviour
    SUCCESS-METRICS.md §4's target exists to discourage."""
    from evals.regression import compare

    better = compare(
        {"l1_golden": {"false_escalation_rate": 0.40}},
        {"l1_golden": {"false_escalation_rate": 0.05}},
    )
    worse = compare(
        {"l1_golden": {"false_escalation_rate": 0.05}},
        {"l1_golden": {"false_escalation_rate": 0.40}},
    )
    assert better == []
    assert len(worse) == 1


def test_a_disappearing_metric_is_a_breach_not_a_pass() -> None:
    """Deleting a failing metric is the cheapest way to turn a gate green."""
    from evals.regression import compare

    regressions = compare({"retrieval": {"recall_at_5": 0.80}}, {"retrieval": {}})
    assert len(regressions) == 1
    assert regressions[0].current is None


def test_baseline_freshness_flags_a_prompt_change_with_no_baseline_update() -> None:
    from evals.regression import baseline_is_stale

    assert baseline_is_stale(["src/fnol_voice_agent/agents/lexicon.py"], False) is not None
    assert baseline_is_stale(["src/fnol_voice_agent/agents/lexicon.py"], True) is None
    assert baseline_is_stale(["README.md"], False) is None


def test_the_committed_baseline_matches_the_current_run() -> None:
    """If this fails, either the system changed without a baseline update or the baseline was committed
    from a different state. Both mean the baseline no longer describes what it claims to."""
    from evals.regression import compare, load_baseline

    assert compare(load_baseline(), to_dict(run_tier_a())) == []


# --------------------------------------------------------------------------------------------------
# CF6(a), enforced at Stage 8: a baseline that does not say what it was measured under cannot be
# compared against, and one older than the stated maximum must fail rather than be compared silently.
# --------------------------------------------------------------------------------------------------


def test_a_baseline_without_provenance_is_refused() -> None:
    """The rule existed as prose in `CF6` from Phase 6 and was satisfied by nobody. Prose is satisfied
    by whoever remembers it; this is the version that cannot be forgotten."""
    import json as _json

    from evals.regression import BaselineProvenanceError, load_baseline

    path = Path("/tmp/fnol-baseline-no-provenance.json")
    path.write_text(_json.dumps({"tier": "A", "l1_golden": {"recall": 1.0}}))
    with pytest.raises(BaselineProvenanceError, match="provenance"):
        load_baseline(path)


def test_a_baseline_past_the_maximum_age_fails_instead_of_being_compared_against() -> None:
    """`D31`: a fixed threshold against a baseline of unknown age cannot distinguish "this PR
    regressed the system" from "the model moved", and it fails in the worse direction -- a real
    regression hides inside drift."""
    import json as _json
    from datetime import UTC, datetime, timedelta

    from evals.regression import MAX_BASELINE_AGE_DAYS, BaselineProvenanceError, load_baseline

    old = datetime.now(UTC) - timedelta(days=MAX_BASELINE_AGE_DAYS + 1)
    path = Path("/tmp/fnol-baseline-stale.json")
    path.write_text(
        _json.dumps(
            {
                "provenance": {
                    "produced_utc": old.isoformat(),
                    "model_id": "n/a",
                    "temperature": "n/a",
                    "k": 1,
                }
            }
        )
    )
    with pytest.raises(BaselineProvenanceError, match="maximum"):
        load_baseline(path)


def test_the_committed_baseline_carries_its_own_provenance() -> None:
    """The check above proves the guard works. This one proves it is armed on the real file --
    a guard that passes only because nothing exercises it is `RESULTS.md` §3.5 again."""
    from evals.regression import load_baseline

    provenance = load_baseline()["provenance"]
    assert set(provenance) >= {"produced_utc", "model_id", "temperature", "k"}
    assert provenance["tier"] == "A"
