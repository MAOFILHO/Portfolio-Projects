# Committed baseline — 2026-08-12

`SUCCESS-METRICS.md` §9: baselines are committed artifacts, updated only by an explicit reviewed commit,
so the baseline cannot drift downward one PR at a time.

| File | What it is | Regenerate? |
|---|---|---|
| `tier_a_baseline.json` | Current Tier A run. The comparison target for the CI regression gate | Yes, with a reviewed diff |
| `tier_b_20260812.json` | Tier B: intent macro-F1, generation judged by Claude Haiku 4.5 | Date-stamped; write a new file |
| `l2_precision_20260812.json` | L2 false-escalation — the measurement that corrected the layered-design conclusion | Date-stamped; write a new file |
| `l1_before_fix_20260812.json` | **DO NOT REGENERATE.** The only uncontaminated L1 reading | Never |
| `composed_pipeline_k5_20260812.json` | **Stage 8's `C1` verification of the shipped composition** (`L1 → guardrail v2 → L2`). Ledger entry #4 | **Never without a new ledger fingerprint.** Re-running it spends the independent set again |
| `cf5_redundancy_20260812.json` | `CF5`'s tuning pass, both temperature arms | Date-stamped; write a new file |

Tier B files are date-stamped rather than overwritten because each one costs money to produce and
records a specific model's behaviour on a specific day. Overwriting would discard the only evidence of
what changed.

**`CF6`(a), enforced at Stage 8:** `tier_a_baseline.json` carries a `provenance` block with
`produced_utc`, `model_id`, `temperature` and `k`, and `evals/regression.load_baseline()` **refuses** a
baseline that lacks it or that is older than `MAX_BASELINE_AGE_DAYS` (90) rather than silently comparing
against it. A baseline that does not say what it was measured under cannot be compared against, and a
provenance rule that lives only in prose is satisfied by whoever remembers it.
