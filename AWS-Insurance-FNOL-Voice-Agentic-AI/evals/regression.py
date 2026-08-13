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
