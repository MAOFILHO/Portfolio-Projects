"""The CI regression gate — Stage 8.

`SUCCESS-METRICS.md` §9: CI fails a PR that breaches **any GATE**, or that degrades **any TARGET by more
than 3 percentage points** against the committed baseline.

Two properties this implements that are easy to get wrong:

* **Improvements are never blocked.** The comparison is one-directional. A metric that gets better is
  reported and passes.
* **A metric that vanishes is a failure, not a pass.** If the baseline has a number and the current run
  does not, something stopped being measured — which is indistinguishable, in a green build, from
  everything being fine. Deleting a failing metric is the cheapest way to make a gate green, so it is
  explicitly a breach.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASELINE_PATH = Path(__file__).resolve().parent / "baselines" / "tier_a_baseline.json"

# `CF6`(c)'s source of measured variance for model-dependent metrics — five real Bedrock router calls
# against the identical golden corpus, committed at Stage 0.5 (`D27`). Not re-measured per gate run:
# spending money on every PR to re-derive a variance figure that changes only when the corpus or the
# router prompt changes would be the same mistake as gating a PR on Tier B directly (rejected in
# `aws-insurance-fnol-voice-agentic-ai-eval-gate.yml`'s own header comment, for cost and flakiness).
TEMP_VARIANCE_PATH = (
    Path(__file__).resolve().parent / "baselines" / "temperature_variance_20260812.json"
)

# Degradation allowance for TARGETs, in absolute rate points. GATEs have no allowance at all.
TARGET_TOLERANCE = 0.03

# Metrics compared against the baseline. `higher_is_better=False` inverts the comparison for rates where
# a smaller number is the good outcome — getting this backwards on false-escalation would build a gate
# that rewards escalating more.
_COMPARED: tuple[tuple[str, str, bool], ...] = (
    ("l1_golden.recall", "L1 recall, labelled safety set", True),
    ("l1_golden.false_escalation_rate", "L1 false-escalation, labelled set", False),
    ("l1_holdout_independent.recall", "L1 recall, independent held-out set", True),
    ("l1_holdout_independent.false_escalation_rate", "L1 false-escalation, independent set", False),
    ("retrieval.recall_at_5", "Retrieval recall@5", True),
    ("retrieval.mrr", "Retrieval MRR", True),
)


@dataclass(frozen=True)
class Regression:
    metric: str
    baseline: float | None
    current: float | None
    detail: str


def _dig(payload: dict[str, Any], dotted: str) -> float | None:
    node: Any = payload
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return float(node) if isinstance(node, int | float) else None


def compare(baseline: dict[str, Any], current: dict[str, Any]) -> list[Regression]:
    regressions: list[Regression] = []
    for key, label, higher_is_better in _COMPARED:
        before = _dig(baseline, key)
        after = _dig(current, key)
        if before is None:
            continue  # not in the baseline yet; nothing to regress against
        if after is None:
            regressions.append(
                Regression(
                    label,
                    before,
                    None,
                    "metric disappeared from the current run — deleting a metric is the cheapest way "
                    "to make a gate green, so it counts as a breach rather than a pass",
                )
            )
            continue
        delta = (after - before) if higher_is_better else (before - after)
        if delta < -TARGET_TOLERANCE:
            regressions.append(
                Regression(
                    label,
                    before,
                    after,
                    f"degraded by {abs(delta):.3f}, tolerance is {TARGET_TOLERANCE:.2f}",
                )
            )
    return regressions


# `CF6`(a): the maximum age a committed baseline may have before the gate refuses to compare against
# it. Generous, because Tier A is deterministic and offline -- nothing in it can drift underneath a
# stored number -- and the point of the check is to stop a stale baseline outliving the system it
# describes, not to force a weekly ritual. `CF6`(b)'s same-run control is what actually handles
# serving-side drift, and it is Phase 10's to build.
MAX_BASELINE_AGE_DAYS = 90


class BaselineProvenanceError(RuntimeError):
    """A committed baseline is unusable as a comparison target."""


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any]:
    """Loads the committed baseline and refuses to hand back one that cannot be compared against.

    `CF6`(a): *"a baseline that does not say what it was measured under cannot be compared against"*,
    and *"the gate fails on a baseline older than a stated max age rather than silently comparing
    against it"*. Both halves are enforced here rather than documented, because a provenance rule that
    lives only in prose is satisfied by whoever remembers it.
    """
    data: dict[str, Any] = json.loads(path.read_text())
    provenance = data.get("provenance")
    if not isinstance(provenance, dict):
        raise BaselineProvenanceError(
            f"{path} has no `provenance` block. CF6(a) requires the date, model ID, temperature and k "
            "a baseline was produced at; without them the comparison cannot say what it is comparing."
        )
    missing = [k for k in ("produced_utc", "model_id", "temperature", "k") if k not in provenance]
    if missing:
        raise BaselineProvenanceError(f"{path}: provenance is missing {missing}. See CF6(a).")

    produced = datetime.fromisoformat(str(provenance["produced_utc"]))
    age_days = (datetime.now(UTC) - produced).days
    if age_days > MAX_BASELINE_AGE_DAYS:
        raise BaselineProvenanceError(
            f"{path} was produced {age_days} days ago, over the {MAX_BASELINE_AGE_DAYS}-day maximum. "
            "Re-run `make eval --json-out` and commit the new baseline. Comparing against it silently "
            "is how a real regression hides inside drift (CF6, D31)."
        )
    return data


# --- Baseline-freshness check ------------------------------------------------------------------------

# Changing any of these can move every model-dependent number in the report, so a change to one without a
# corresponding baseline update means the committed baseline no longer describes the system it claims to.
BASELINE_SENSITIVE_PATHS = (
    "src/fnol_voice_agent/agents/lexicon.py",
    "src/fnol_voice_agent/agents/nodes/coverage_question.py",
    "src/fnol_voice_agent/agents/nodes/rental_towing.py",
    "src/fnol_voice_agent/config/settings.py",
    "evals/golden/",
    "evals/queries.py",
)


def baseline_is_stale(changed_paths: list[str], baseline_changed: bool) -> str | None:
    """Returns a message when prompt/model/corpus files changed without a baseline update."""
    if baseline_changed:
        return None
    touched = [
        p for p in changed_paths if any(p.startswith(prefix) for prefix in BASELINE_SENSITIVE_PATHS)
    ]
    if not touched:
        return None
    return (
        f"These changed without any update to evals/baselines/: {touched}. "
        f"They can move every model-dependent number in the report, so the committed baseline no "
        f"longer describes the system it claims to. Re-run `make eval` and commit the new baseline, "
        f"or say in the PR why the numbers cannot have moved."
    )


# --- `CF6`(b)/(c): same-run control and sd-based tolerance, for model-dependent metrics ---------------
#
# `compare()` above answers "did this PR change vs. the number we committed." For a deterministic Tier A
# metric that is the right question. For a model-dependent one it is the wrong question whenever the
# serving side can move between the day the baseline was committed and the day the PR runs — and `D29`
# shows this is not hypothetical: the intent router's macro-F1 moved from a committed 0.62325
# (`evals/baselines/tier_b_20260812.json`) to 0.517875 on every deterministic re-run since
# (`evals/baselines/temperature_variance_20260812.json`, the `zero` setting), with the code and corpus
# byte-identical both times. A flat-tolerance comparison against the committed number reads that ~0.105
# gap as a regression. It is drift, not a regression, and `compare()` would have blocked a clean PR on it.
#
# `CF6`(b)'s answer: never compare the PR's run against the *committed* number for a model-dependent
# metric. Compare it against a *control* — the unchanged baseline configuration, re-measured in the same
# job, the same session, under whatever the serving side is doing today. Both readings share the same
# drift, so drift cancels out of the comparison instead of masquerading as a finding.


@dataclass(frozen=True)
class ModelDependentMetricSpec:
    key: str
    label: str
    higher_is_better: bool


# The only metrics this project has a real, measured, repeated-run variance figure for
# (`temperature_variance_20260812.json`). `CF6`(c) forbids setting a tolerance for a metric whose sd has
# never been measured, so this list is deliberately not "every Tier B metric" — it is exactly the ones
# `load_measured_sd` can back with a number instead of a guess. `safety_flag_rate` is measured in the same
# file but is excluded here: it is a rate of raising a flag, not a quality score, and has no
# higher-is-better/lower-is-better direction to compare against (`D27`).
MODEL_DEPENDENT_COMPARED: tuple[ModelDependentMetricSpec, ...] = (
    ModelDependentMetricSpec("macro_f1", "Intent macro-F1 (router)", True),
    ModelDependentMetricSpec("accuracy", "Intent accuracy (router)", True),
    ModelDependentMetricSpec("oos_recall", "Out-of-scope recall (router)", True),
)


def load_measured_sd(
    metric_key: str,
    *,
    settings_key: str = "default_unset",
    path: Path = TEMP_VARIANCE_PATH,
) -> float:
    """The real, committed, repeated-run standard deviation for one Tier B metric.

    `settings_key="default_unset"` is the pre-`D27` reading (no `temperature` sent, Nova's own default),
    kept as the operative figure deliberately rather than switching to the post-`D27` `"zero"` group's
    0.0: intra-session sampling variance at temperature 0.0 is genuinely zero, but `D29`'s cross-session
    gap shows the metric still moves for reasons this project cannot see from the client, and a tolerance
    built from the wrong kind of "stable" would be exactly the false confidence `CF6` exists to remove.
    `default_unset`'s spread is the largest real figure on record for this metric and is used as the
    conservative bound until a cross-session variance figure exists to replace it.
    """
    data = json.loads(path.read_text())
    metrics = data["settings"][settings_key]["metrics"]
    if metric_key not in metrics:
        raise KeyError(
            f"No measured sd for {metric_key!r} in {path} [{settings_key}]. `CF6`(c) forbids a "
            f"tolerance for a metric whose sd has never been measured — measure it before comparing it."
        )
    return float(metrics[metric_key]["stdev"])


def sd_tolerance(measured_sd: float, corpus_size: int, k: float = 2.0) -> float:
    """`CF6`(c): a model-dependent metric's tolerance, in measured standard deviations — not fixed
    percentage points.

    `k=2.0` matches `ADR-014` §4's original "≥ 2 sd" bar. `D35` found that bar undefined the moment the
    router was pinned to temperature 0.0 (`D27`): intra-session sd becomes exactly 0.0, so "2 sd" admits
    no tolerance at all — not because the metric became infinitely stable, but because five identical
    runs producing byte-identical output is a property of a fixed corpus and a pinned decoder, not a
    property that generalises to "nothing can ever move." `D35`'s fallback, applied ad hoc at the time and
    formalised here: where the measured sd is 0.0, the tolerance is the change **one item moving**
    produces, `1 / corpus_size` — the gate is not made more sensitive than the corpus it is scored against
    can resolve.
    """
    if measured_sd > 0.0:
        return k * measured_sd
    if corpus_size <= 0:
        raise ValueError("corpus_size must be positive to apply the D35 zero-sd fallback")
    return 1.0 / corpus_size


def same_run_compare(
    control: dict[str, Any],
    candidate: dict[str, Any],
    specs: tuple[ModelDependentMetricSpec, ...] = MODEL_DEPENDENT_COMPARED,
    *,
    corpus_size: int,
    k: float = 2.0,
    sd_loader: Any = load_measured_sd,
) -> list[Regression]:
    """`CF6`(b): compares `candidate` against `control` — both measured in the same job/session — rather
    than against a committed baseline that may be stale relative to today's serving behaviour.

    `control` and `candidate` are flat dicts keyed by the same metric names as `MODEL_DEPENDENT_COMPARED`
    (e.g. `{"macro_f1": 0.51, "accuracy": 0.52, ...}`), not the nested `l1_golden.recall`-style paths
    `compare()` reads — Tier B's report shape is flatter than Tier A's. A metric absent from `control` is
    skipped (nothing to compare against yet); one that disappears from `candidate` is a breach, same rule
    as `compare()` and for the same reason.
    """
    regressions: list[Regression] = []
    for spec in specs:
        before = control.get(spec.key)
        if before is None:
            continue
        after = candidate.get(spec.key)
        if after is None:
            regressions.append(
                Regression(
                    spec.label,
                    before,
                    None,
                    "metric disappeared from the current run — deleting a metric is the cheapest way "
                    "to make a gate green, so it counts as a breach rather than a pass",
                )
            )
            continue
        sd = sd_loader(spec.key)
        tolerance = sd_tolerance(sd, corpus_size, k)
        delta = (after - before) if spec.higher_is_better else (before - after)
        if delta < -tolerance:
            regressions.append(
                Regression(
                    spec.label,
                    before,
                    after,
                    f"degraded by {abs(delta):.4f} vs. the same-run control; sd-based tolerance is "
                    f"{tolerance:.4f} (measured sd {sd:.4f}, k={k}, corpus {corpus_size})",
                )
            )
    return regressions
