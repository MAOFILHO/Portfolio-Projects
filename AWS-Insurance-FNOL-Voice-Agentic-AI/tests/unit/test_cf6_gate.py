"""`CF6`(b)/(c) — same-run control and sd-based tolerance for model-dependent metrics.

`CF6`(a) (baseline provenance + max-age) is tested in `test_eval_harness.py`, built and enforced at
Phase 7 Stage 8. This file covers the two properties Phase 10 owns: comparing a PR's run against a
same-session control rather than a stale committed number, and expressing tolerance in measured standard
deviations rather than fixed percentage points.
"""

from __future__ import annotations

import pytest

from evals.regression import (
    MODEL_DEPENDENT_COMPARED,
    load_measured_sd,
    same_run_compare,
    sd_tolerance,
)

# --- `sd_tolerance` ------------------------------------------------------------------------------------


def test_sd_tolerance_is_k_times_measured_sd_when_sd_is_nonzero() -> None:
    assert sd_tolerance(0.02433853040962006, corpus_size=78, k=2.0) == pytest.approx(0.04867706)


def test_sd_tolerance_falls_back_to_one_item_moving_when_sd_is_zero() -> None:
    """`D35`: "2 sd" is undefined once the router is pinned to temperature 0.0 and intra-session sd is
    exactly 0.0 — the fallback is the change one item moving produces, not a tolerance of zero."""
    assert sd_tolerance(0.0, corpus_size=78, k=2.0) == pytest.approx(1 / 78)


def test_sd_tolerance_rejects_a_nonpositive_corpus_when_the_fallback_is_needed() -> None:
    with pytest.raises(ValueError, match="corpus_size"):
        sd_tolerance(0.0, corpus_size=0)


# --- `load_measured_sd` — reads the real committed file, not a hardcoded number ------------------------


def test_load_measured_sd_reads_the_real_committed_variance_file() -> None:
    """This is `D27`'s own measurement (`evals/baselines/temperature_variance_20260812.json`), read
    back rather than copied into a constant — `CF6`(c) forbids a tolerance for a metric whose sd was
    never measured, and a hardcoded copy is one edit away from silently no longer being that."""
    sd = load_measured_sd("macro_f1")
    assert sd == pytest.approx(0.02433853040962006)


def test_load_measured_sd_raises_for_an_unmeasured_metric() -> None:
    with pytest.raises(KeyError, match="never been measured"):
        load_measured_sd("a_metric_nobody_ever_ran_five_times")


# --- `same_run_compare` ---------------------------------------------------------------------------------


def test_same_run_compare_passes_a_real_historical_gap_that_compare_would_have_flagged() -> None:
    """The exact `D29` gap, real numbers: committed Tier B baseline macro-F1 was 0.62325
    (`tier_b_20260812.json`); every deterministic re-run since reads 0.517875 (`temperature_variance
    ...json`, the `zero` setting) — a ~0.105 drop with the code and corpus unchanged. Comparing the
    *committed* number against today's run (what `compare()` does for Tier A) would read this as a
    regression under any flat tolerance. `same_run_compare` never makes that comparison: the committed
    number is not one of its two arguments. Here the control and the candidate are the *same* real,
    unchanged-configuration reading (0.517875) — the honest "nothing changed" case same-run control
    exists to pass cleanly regardless of how far it has drifted from whatever was committed."""
    control = {"macro_f1": 0.517875, "accuracy": 0.5256410256410257, "oos_recall": 0.0}
    candidate = {"macro_f1": 0.517875, "accuracy": 0.5256410256410257, "oos_recall": 0.0}
    assert same_run_compare(control, candidate, corpus_size=78) == []


def test_same_run_compare_catches_a_real_regression_injected_on_top_of_the_real_control() -> None:
    """Synthetic on top of real: the control is the genuine 0.517875 reading; the candidate subtracts
    0.15 from it, several times the measured tolerance (~0.049 at k=2). Labelled synthetic rather than
    presented as measured, matching `demonstrate_regression_gate.py`'s convention for its own bad change.
    """
    control = {"macro_f1": 0.517875, "accuracy": 0.5256410256410257, "oos_recall": 0.0}
    candidate = {"macro_f1": 0.517875 - 0.15, "accuracy": 0.5256410256410257, "oos_recall": 0.0}
    regressions = same_run_compare(control, candidate, corpus_size=78)
    assert len(regressions) == 1
    assert regressions[0].metric == "Intent macro-F1 (router)"


def test_same_run_compare_never_blocks_an_improvement() -> None:
    control = {"macro_f1": 0.50}
    candidate = {"macro_f1": 0.60}
    assert same_run_compare(control, candidate, corpus_size=78) == []


def test_same_run_compare_treats_a_disappearing_metric_as_a_breach() -> None:
    control = {"macro_f1": 0.50}
    candidate: dict[str, float] = {}
    regressions = same_run_compare(control, candidate, corpus_size=78)
    assert len(regressions) == 1
    assert regressions[0].current is None


def test_same_run_compare_skips_a_metric_absent_from_the_control() -> None:
    """Nothing to compare against yet is not a breach — same asymmetry `compare()` already has for a
    metric not yet in the committed baseline."""
    assert same_run_compare({}, {"macro_f1": 0.10}, corpus_size=78) == []


def test_model_dependent_compared_excludes_safety_flag_rate() -> None:
    """`safety_flag_rate` has a real measured sd in the same file but no quality direction (`D27`) —
    it must not appear in the comparison set."""
    assert "safety_flag_rate" not in {spec.key for spec in MODEL_DEPENDENT_COMPARED}
