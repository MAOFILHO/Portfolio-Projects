"""Demonstrate `CF6`(b)/(c) has teeth, and that it fixes the exact failure `compare()` has for a
model-dependent metric -- Phase 10, criterion 1.

`SUCCESS-METRICS.md` §9 addendum: "The rule above stands unchanged for deterministic metrics... For
model-dependent metrics it is superseded by `CF6`, which requires baselines stamped with date/model/
temperature/k, a same-run control re-measuring the unchanged configuration in the same CI job, and
tolerances expressed in measured standard deviations rather than fixed points."

`ADR-013`'s own rule applies here too: no `mock_aws()` in this file, and there is nothing to guard against
in the first place -- every number below is either read from a committed JSON file or produced by
arithmetic on numbers read from one. No AWS credentials, no model calls, $0.00. This is what makes it safe
to run on every PR (wired into `fnol-eval-gate.yml`) rather than reserved for a one-off demonstration like
`demonstrate_regression_gate.py`.

## Two things this proves, both with real project data

1. **The failure `CF6`(b) exists to fix, reproduced.** `compare()` — the Tier A mechanism — flags a metric
   whenever it drops more than `TARGET_TOLERANCE` (a fixed 0.03) below whatever is in the *committed*
   baseline. Applied naively to a model-dependent metric, that rule reads `D29`'s real, already-documented
   drift (committed Tier B macro-F1 0.62325 vs. every deterministic re-run since, 0.517875 -- code and
   corpus unchanged) as a 0.105 regression. It would have blocked a clean PR. `same_run_compare` does not
   make this mistake, because the committed number is never one of its two arguments -- shown below by
   running the *same* real 0.517875 reading through both functions and comparing the verdicts.
2. **The gate still has teeth.** A synthetic regression, clearly labelled as such (matching
   `demonstrate_regression_gate.py`'s own convention), injected on top of the same real control reading —
   `same_run_compare` catches it.

All real numbers below are read from `evals/baselines/temperature_variance_20260812.json` and
`evals/baselines/tier_b_20260812.json` at run time -- not copied into this file -- so a change to either
committed artifact changes what this script demonstrates instead of silently going stale next to it.
"""

from __future__ import annotations

import json
import sys

from evals.regression import (
    TARGET_TOLERANCE,
    TEMP_VARIANCE_PATH,
    Regression,
    same_run_compare,
)
from evals.schema import load_golden_set

TIER_B_BASELINE_PATH = TEMP_VARIANCE_PATH.parent / "tier_b_20260812.json"

SCOPE_BANNER = """\
================================================================================================
SCOPE OF THIS CHECK -- read this before trusting a green run (CF7, PROJECT_STATE.md)
================================================================================================
This step gates the SAME-RUN-CONTROL MECHANISM (CF6(b)/(c)), not a live Tier B metric of THIS
PR's code. Every number below comes from committed historical data or a labelled synthetic
injection -- nothing here classifies this PR's own router output, because that would require
Bedrock credentials this workflow does not carry (cost gate; see fnol-eval-gate.yml header).

  GREEN means: "the comparison math is still correct against real historical drift and a
                synthetic regression."
  GREEN does NOT mean: "this PR's intent classifier still scores >= baseline."
  Nothing in this CI job currently checks the second claim. CF7 names what closing that gap
  would take (credentials, per-PR cost, whether it's even wanted) and is not yet resolved.
================================================================================================"""


def _print_regressions(label: str, regressions: list[Regression]) -> None:
    if not regressions:
        print(f"   {label}: none")
        return
    for r in regressions:
        before = "n/a" if r.baseline is None else f"{r.baseline:.4f}"
        after = "GONE" if r.current is None else f"{r.current:.4f}"
        print(f"   {label}: {r.metric}: {before} -> {after} ({r.detail})")


def main() -> int:
    print(SCOPE_BANNER)
    print()
    print("=" * 96)
    print(
        "CF6(b)/(c) DEMONSTRATION -- same-run control vs. a stale committed baseline, real project data"
    )
    print("=" * 96)

    committed = json.loads(TIER_B_BASELINE_PATH.read_text())["intent"]["macro_f1"]
    temp_variance = json.loads(TEMP_VARIANCE_PATH.read_text())
    control_now = temp_variance["settings"]["zero"]["metrics"]["macro_f1"]["mean"]
    corpus_size = len(load_golden_set())

    print("\n1. The real D29 gap")
    print(f"   Committed Tier B baseline macro-F1 (tier_b_20260812.json):        {committed:.5f}")
    print(f"   Every deterministic re-run since (temperature_variance, 'zero'):  {control_now:.5f}")
    print(
        f"   Delta, code and corpus unchanged both times:                     {committed - control_now:.5f}"
    )

    print(
        "\n2. What compare()'s flat-tolerance rule would say if applied to this metric the same way"
    )
    print(
        "   it is applied to every Tier A metric (macro_f1 is not actually wired into compare() --"
    )
    print("   Tier B never enters the per-PR gate directly, for cost reasons stated in")
    print("   fnol-eval-gate.yml. This replicates its exact arithmetic to show why not.):")
    naive_delta = (
        committed - control_now
    )  # higher_is_better=True, same direction compare() would use
    naive_regression = naive_delta > TARGET_TOLERANCE
    print(f"   delta = committed - control = {naive_delta:.5f}, tolerance = {TARGET_TOLERANCE:.2f}")
    would_have_blocked = naive_regression
    print(
        f"   Would this have blocked a clean PR?  "
        f"{'YES -- a false alarm on pure drift' if would_have_blocked else 'no'}"
    )

    print(
        "\n3. What CF6(b) same-run control does instead -- control and candidate are the SAME real"
    )
    print("   unchanged-configuration reading, not the committed number:")
    control = {"macro_f1": control_now}
    candidate_unchanged = {"macro_f1": control_now}
    clean = same_run_compare(control, candidate_unchanged, corpus_size=corpus_size)
    _print_regressions("same_run_compare(), nothing changed", clean)
    false_alarm_avoided = would_have_blocked and not clean
    print(
        f"   Drift-vs-regression correctly told apart?  "
        f"{'YES' if false_alarm_avoided else 'NO -- CF6(b) HAS NO TEETH ON THIS CASE'}"
    )

    print(
        "\n4. Still catches a real regression -- SYNTHETIC, injected on top of the same real control:"
    )
    injected_drop = 0.15
    candidate_bad = {"macro_f1": control_now - injected_drop}
    print(
        f"   Candidate = control - {injected_drop} = {candidate_bad['macro_f1']:.5f} (not measured, injected)"
    )
    caught = same_run_compare(control, candidate_bad, corpus_size=corpus_size)
    _print_regressions("same_run_compare(), synthetic regression", caught)
    gate_has_teeth = bool(caught)
    print(
        f"   Would CI block this?  {'YES' if gate_has_teeth else 'NO -- CF6(b)/(c) HAS NO TEETH'}"
    )

    ok = false_alarm_avoided and gate_has_teeth
    print(f"\n5. Overall: {'PASS' if ok else 'FAIL'}")
    print(
        "\n   Reminder: PASS above means the mechanism is correct, not that this PR's own Tier B "
        "numbers were checked -- see the SCOPE banner at the top of this output, or CF7."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
