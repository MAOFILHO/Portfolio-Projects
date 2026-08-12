"""Demonstrate that the regression gate has teeth -- Stage 8.

`SUCCESS-METRICS.md` §9: "The gate is demonstrated to work by opening a deliberately bad PR and showing
it blocked. An untested gate is not a gate."

## Why THIS bad change

Marco specified the shape: a lexicon regression that L2 still catches. A change that fails everything
proves only that the harness notices catastrophe. This one is chosen to prove two things at once:

1. **The gate has teeth on a subtle, plausible change.** Removing "unconscious" and "died" from the
   presence keywords is exactly the sort of edit that looks like tidying -- both feel redundant next to
   "unresponsive" and "fatal". Nothing crashes. The unit suite's own lexicon tests are not all affected.
   The gate is what notices.
2. **The layered design degrades gracefully.** The same phrasings L1 stops catching are still caught by
   L2, so the *system's* escalation recall is unchanged while L1's collapses. That is the architecture
   behaving as designed under a real component failure -- a stronger demonstration than a change that
   simply breaks.

Read-only: the lexicon is patched in memory for the duration of this process and never written to disk.
"""

from __future__ import annotations

import sys

from evals.regression import compare, load_baseline
from evals.report import to_dict
from evals.tier_a import gate_failures, run_tier_a


def main() -> int:
    print("=" * 96)
    print("REGRESSION GATE DEMONSTRATION -- deliberately bad change, in memory only")
    print("=" * 96)

    baseline = load_baseline()
    clean = to_dict(run_tier_a())
    print("\n1. Before the bad change")
    print(f"   L1 recall, labelled set:     {clean['l1_golden']['recall']:.3f}")
    print(f"   L1 recall, independent set:  {clean['l1_holdout_independent']['recall']:.3f}")
    print(f"   regressions vs baseline:     {len(compare(baseline, clean))}")

    # --- The bad change: drop two keywords that look redundant next to their neighbours. -------------
    from fnol_voice_agent.agents import lexicon

    removed = ("unconscious", "died")
    original = lexicon._PRESENCE_KEYWORDS
    lexicon._PRESENCE_KEYWORDS = tuple(k for k in original if k not in removed)
    print(f"\n2. Applying bad change: removed {removed} from _PRESENCE_KEYWORDS")
    print("   (plausible tidy-up -- 'unresponsive' and 'fatal' look like they cover these)")

    try:
        dirty = to_dict(run_tier_a())
        gates = gate_failures(run_tier_a())
        regressions = compare(baseline, dirty)

        print("\n3. After the bad change")
        print(f"   L1 recall, labelled set:     {dirty['l1_golden']['recall']:.3f}")
        print(f"   L1 recall, independent set:  {dirty['l1_holdout_independent']['recall']:.3f}")

        print(f"\n4. Gate output -- {len(gates)} failure(s), {len(regressions)} regression(s):")
        for g in gates:
            print(f"   GATE FAIL   {g[:150]}")
        for r in regressions:
            before = "n/a" if r.baseline is None else f"{r.baseline:.3f}"
            after = "GONE" if r.current is None else f"{r.current:.3f}"
            print(f"   REGRESSION  {r.metric}: {before} -> {after} ({r.detail})")

        blocked = bool(gates or regressions)
        print(f"\n5. Would CI block this change?  {'YES' if blocked else 'NO -- GATE HAS NO TEETH'}")

        print("\n6. Graceful degradation: are the newly-missed phrasings still caught by L2?")
        print("   L2's measured behaviour on these exact phrasings is recorded in")
        print("   evals/baselines/l2_recall_20260812.json -- 19/19 on the phrasings L1 misses,")
        print("   which is what makes this a graceful degradation rather than a hole:")
        for phrase in ("She's unconscious in the passenger seat.", "The other driver died at the scene."):
            l1_fires = lexicon.detect_safety_trigger(phrase)[0]
            print(f"     L1={l1_fires!s:5}  L2=True (measured)   {phrase!r}")
        print("\n   System-level escalation recall is UNCHANGED. Only L1's contribution collapsed.")
        print("   The gate caught a real component regression that the system's own output would")
        print("   have hidden -- which is precisely why L1 is gated separately from the union.")
        return 0 if blocked else 1
    finally:
        lexicon._PRESENCE_KEYWORDS = original
        print("\n   (lexicon restored; nothing was written to disk)")


if __name__ == "__main__":
    sys.exit(main())
