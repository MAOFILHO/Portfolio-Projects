# Committed baseline — 2026-08-12

`SUCCESS-METRICS.md` §9: baselines are committed artifacts, updated only by an explicit reviewed commit,
so the baseline cannot drift downward one PR at a time.

| File | What it is | Regenerate? |
|---|---|---|
| `tier_a_baseline.json` | Current Tier A run. The comparison target for the CI regression gate | Yes, with a reviewed diff |
| `tier_b_20260812.json` | Tier B: intent macro-F1, generation judged by Claude Haiku 4.5 | Date-stamped; write a new file |
| `l2_precision_20260812.json` | L2 false-escalation — the measurement that corrected the layered-design conclusion | Date-stamped; write a new file |
| `l1_before_fix_20260812.json` | **DO NOT REGENERATE.** The only uncontaminated L1 reading | Never |

Tier B files are date-stamped rather than overwritten because each one costs money to produce and
records a specific model's behaviour on a specific day. Overwriting would discard the only evidence of
what changed.
