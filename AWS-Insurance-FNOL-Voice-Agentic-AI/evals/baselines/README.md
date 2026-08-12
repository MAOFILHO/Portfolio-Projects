# Baselines

Committed artifacts, updated only by an explicit reviewed commit — `SUCCESS-METRICS.md` §9's rule, so the
baseline cannot drift downward one PR at a time.

## `l1_before_fix_20260812.json` — DO NOT REGENERATE

The L1 detector's performance against the independent held-out set **before** any fix informed by that
set's contents existed. It is the only uncontaminated measurement of what a lexicon written without those
examples achieves, and it cannot be reproduced once the lexicon changes.

Regenerating this file would silently overwrite the honest number with a contaminated one that looks
better. If you need current numbers, write a new file with a new date.
