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


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
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
