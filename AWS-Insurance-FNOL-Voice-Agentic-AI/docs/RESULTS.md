# Results — Phase 6

Real measurements. Every number here was produced by `make eval` or by a cost-gated script in this
repository, and every number that failed is at its real value.

**Status: Phase 6 in progress (Stages 1–6 of 8).** Tier B's full run — intent macro-F1, groundedness,
answer relevance, task success — is not complete. This document currently covers the safety detector,
which is where the phase's most important finding is.

---

## 1. The headline finding

**The layered safety detector works, and it is the only reason this system's recall claim survives
contact with unseen language.**

Measured against 26 injury phrasings written by an isolated agent that never read the detector:

| Layer | Recall on the independent held-out set |
|---|---|
| **L1** (deterministic lexicon) alone | **0.269** (7/26) |
| **L2** (Nova Micro classifier) on the 19 L1 missed | **1.000** (19/19) |
| **L1 ∪ L2** — the union semantics `D15` specifies | **1.000** (26/26) |

L1 misses roughly three quarters of real indirect injury phrasing. L2 caught every single one of those
misses, including all five fatality euphemisms, and correctly declined to fire on the one false positive
L1 still produces.

`SUCCESS-METRICS.md` §2 committed to a layered detector on the argument that "a single detector
demonstrably cannot carry this." That was an assertion when it was written. It is now a measurement:
**a single deterministic detector would have missed 19 of 26 real injury reports, including four of five
descriptions of a death.**

Marco framed the stakes before the numbers existed: if L2 catches what L1 misses, that is the strongest
evidence the layered architecture was the right call; if it does not, that is the finding of the entire
project. It caught all of them.

### What this result does not establish

Stated with the result rather than below it, because a 1.000 is exactly the kind of number that travels
without its caveats.

- **n = 26 positives, one sample each.** L2 is a model call and therefore stochastic; a single sample per
  phrasing does not establish the rate is 1.000, only that it was 26/26 on this run. Repeated sampling
  is Phase 7's.
- **The held-out set was written by a language model, and classified by a language model.** This is the
  most serious threat to the result's validity and it has no clean fix here. An agent asked to write
  euphemistic injury phrasing may produce phrasing that is more *model-legible* than what a panicking
  human actually says at the roadside. The two systems may share an inductive bias that a real caller
  does not. The set is independent of **the detector**; it is not independent of **language models in
  general**. Any claim about real-world recall needs human-authored phrasings, and this project has none.
- **No real caller has ever spoken to this system.** Every figure here is from author-generated or
  agent-generated text.

---

## 2. L1 before and after the Stage 5 fix

Ordering was fixed by Marco and matters: the independent set was generated **before** `lexicon.py` was
touched, so the "before" column is uncontaminated. The "after" column is contaminated by construction
and is labelled as such wherever it appears.

| Set | Recall before | Recall after | False-escalation before | after |
|---|---|---|---|---|
| Golden labelled (GATE) | 0.778 (7/9) | **1.000 (11/11)** | 0.000 | 0.000 |
| **Independent held-out** | **0.192 (5/26)** | 0.269 ⚠ | **0.412 (7/17)** | 0.059 ⚠ |
| Weak held-out | **0.400 (6/15)** — final | *not revisited* | 0.250 | *not revisited* |

⚠ **Contaminated.** The fix was made after seeing the independent set's results. `0.192` and `0.412` are
the honest readings; the post-fix figures show the direction of change, not an independent measurement.

**The weak held-out set is closed at 0.400 by Marco's instruction** and is not re-reported. Its purpose
was served: it is what identified the negation class in the first place.

### The two numbers moved for opposite reasons, and that is the interesting part

**False-escalation fell 0.412 → 0.059 on data the fix never saw.** That is genuine generalisation. The
seven false positives were not seven mistakes; they were one — the lexicon had no notion of polarity and
matched injury words as bare substrings, so "nobody was hurt" fired on `hurt`. Replacing that with a
clause-scoped negation rule fixed the class, and it transferred to unseen phrasings almost completely.

**Recall barely moved, 0.192 → 0.269.** Two cases. This is not a failure of effort; it is the structural
limit of the approach. Precision problems in a lexicon are *rule-shaped* and generalise when you fix the
rule. Recall problems are *vocabulary-shaped*: to catch "they covered him with a sheet" you must have
thought of "they covered him with a sheet". No amount of care makes a keyword list generalise to language
it has not seen.

**The design consequence is concrete: L1 should not be asked to carry recall, and adding entries to it in
response to missed cases is a treadmill.** Its real jobs are precision, zero latency, zero cost, and being
deterministic enough that its position in the graph can be structurally enforced (`ADR-010`). Recall is
L2's, and §1 shows L2 can carry it.

### What was deliberately not fixed

One false positive survives on the independent set:

> *"the ambulance did come out but after they'd had a look at the three of us they said there was no need
> for anyone to go in"*

The negation ("no need") sits to the **right** of the trigger word ("ambulance"), and `_is_negated` only
scopes backwards. Handling right-scoped all-clear assertions is a real, buildable second category — and
the only evidence for it is in the independent held-out set. Building it would mean fixing against
held-out data and spending the one uncontaminated measurement this phase has. **Left as a named open gap
instead**, recorded here and in `lexicon.py`'s own docstring.

### Two regex hazards, same shape, found twice

`\b` matches nothing immediately before an apostrophe-t contraction: in `isn't`, the `n` is preceded by a
word character, so `\bn't\b` never fires. This bug was present in the third-party status pattern (caught
by an existing Phase 5 test) and again, independently, in the negation cues — where it meant **no `-n't`
contraction registered as a negation at all**, and only the handful spelled out explicitly in the list
worked. Recorded because it is the kind of defect that reads as correct on review and fails silently in
the safe-looking direction.

---

## 3. Response quality — `RentalTowingEntitlement` redundancy

Tracked as `CF5`. **TARGET in Phase 6, GATE at Phase 7 sign-off**, per Marco's decision at approval.

The Phase 4 prompt fix reduces the defect without eliminating it. Two real trials of the same prompt
against the same claim produced one clean answer and one that restated "8 days remaining" in a third
sentence having already given it in the second. Both real outputs are committed verbatim in
`evals/fixtures/known_bad/`, and the detector is proven against them:

| Fixture | Redundant? | Leaks general mechanics? |
|---|---|---|
| Stage 8 real output (3 sentences) | **yes** — "8 day" in sentences 2 and 3 | yes |
| Phase 4 real output (2 sentences) | **yes** — "8 day" in both | no |
| Stage 8 real output (clean trial) | no | **yes** |

The third row is why the two checks are kept separate: the redundancy-clean answer still volunteered the
corpus's 20-day cap against the prompt's explicit instruction, and a single blended quality score would
have called it fine.

**The detector needed a second real fixture to be correct.** Built against the Stage 8 output it passed
immediately, then failed on the Phase 4 output, which states the unit before the value ("your remaining
rental days is 8"). One real example was not enough to specify the check — the same lesson as `CF3` and
`D21`, arriving from a third direction.

---

## 4. Corpus and coverage

77 golden conversations, 140 turns, grounded in the real Phase 3 synthetic records. Composition minimums
are asserted in CI so the set cannot be quietly narrowed to easy cases:

| Category | Count | Minimum |
|---|---|---|
| happy_path | 16 | 12 |
| edge_case | 19 | 10 |
| ambiguity | 7 | 6 |
| adversarial | 10 | 8 |
| out_of_scope | 5 | 5 |
| safety | 20 | 12 |

---

## 5. Cost

| Run | Calls | Tokens | Cost |
|---|---|---|---|
| L2 recall measurement (Stage 6) | 22 | 20,421 in / 978 out | **$0.000852** |

Phase 6 sub-budget: **$0.00085 of $1.00** consumed. Standing Bedrock cap: ≈$0.0012 of $5.00.

Tier A runs — the L1 numbers, the corpus checks, the redundancy detector — cost **$0.00** and need no AWS
credentials. That is deliberate: they are the body of the CI gate.

---

## 6. Still outstanding

Tier B's full run (intent macro-F1, groundedness, answer relevance, abstention, compound-case
correctness, task success, per-conversation cost and latency), the retrieval metrics on real Titan
vectors, `CF3`'s repeated tight-turn sampling, the committed baseline, and the CI regression gate with
its deliberately-bad-change demonstration. Stages 5–8 of the build plan.

**Latency is not reported here and will not be reported by Phase 6 as a comparison against the 1,800 ms
budget.** What this phase can measure is agent-internal turn latency; the GATE is Lex-STT-completion to
Polly-audio-start, which includes telephony, ASR and TTS legs this phase never touches. Phase 9 owns that
measurement.
