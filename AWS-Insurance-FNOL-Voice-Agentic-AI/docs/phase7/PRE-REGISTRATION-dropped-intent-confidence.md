# Pre-registration — how a dropped `intent_confidence` is scored

**Written 2026-08-12, after rung C crashed on the first occurrence and before the rate was measured.**
Same discipline as [the dropped-`safety_flag` pre-registration](PRE-REGISTRATION-dropped-safety-flag.md),
for the same reason: the alternative is picking a rule that the measured number happens to survive.

## What happened

Rungs A and B completed clean — 1,580 real calls, zero dropped fields. Rung C, the first rung to use the
**split** classifier, raised on a tuning-set item:

```
ValidationError: 1 validation error for IntentClassification
intent_confidence
  Field required [type=missing, input_value={'coverage_question_type': ..., 'intent': 'CoverageQuestion'}]
```

The model returned a well-formed tool call with `intent` and `coverage_question_type` and simply omitted
`intent_confidence`. `ADR-004`'s mechanism worked exactly as designed — a schema-required field cannot be
silently absent, so the call failed loudly instead of producing a partial classification.

**This is the failure mode the earlier pre-registration was written for, arriving on a different field.**
That document predicted 0.3–1% for `safety_flag` and measured 0 in 780. This one appeared inside the first
80 items of the first split rung, which is already informative: the merged call has now made 1,580 clean
calls in this phase's protocol, and the split's classifier dropped a field almost immediately.

## The single most important difference from the `safety_flag` case

**`intent_confidence` is not a safety field, so `C1` is not engaged.** The detector runs as an independent
concurrent call; its verdict arrived normally. A dropped classifier field cannot cost union escalation
recall, because the safety answer does not come from that call any more — which is, incidentally, the first
concrete benefit the split has demonstrated: `ADR-004`'s accepted residual risk was that *"a failure in
that call affects both routing and safety classification simultaneously"*, and it no longer does.

## Scoring rules — fixed now

| Situation | Scored as |
|---|---|
| Dropped classifier field, **intent macro-F1** | **A miss.** The turn is counted with a wrong intent, not excluded |
| Dropped classifier field, **out-of-scope recall** | **A miss**, same reasoning |
| Dropped classifier field, **escalation recall / false escalation** | **Unaffected.** The detector is a separate call and answered |
| Dropped classifier field, availability | Counted in a per-call **drop rate**, reported per rung |

**Why a miss rather than an exclusion, which is the opposite of the `safety_flag` rule.** There, a
no-verdict turn was excluded from the false-escalation *denominator* because counting it as a
non-escalation would let one event improve one metric while damaging another. Here the exposure runs the
other way: excluding unusable classifications from macro-F1 would let a configuration **raise its score by
failing more often**, dropping exactly the turns it finds hardest. A turn the system could not classify is
a turn the system got wrong. That is what a caller experiences.

Both rules follow the same principle — **score the failure against the metric it would otherwise
flatter** — and they point in opposite directions because the two metrics are exposed in opposite
directions.

## What counts as material — before the number

| Measured per-call rate | Reading | Obligation |
|---|---|---|
| **≥ 1%** | ~8% of 8-turn calls hit an unclassifiable turn | **Blocks promotion of the split.** Must be fixed in Phase 7 or the split is not shippable regardless of its metrics |
| **0.13% – 1%** | ~1–8% of calls affected | **Material.** Requires a named remedy in Phase 7, with its cost stated |
| **below ~0.13%** | Below what this run resolves (1 event in 790 calls per rung) | Report as a count, carry to `NOT-FIXED.md` |

**The rate is per *classifier call*, not per turn**, and it is reported for the split rungs (C, D) and the
merged rungs (A, B) separately — the whole question is whether the split made this worse.

## The remedy, ranked before the rate is known

1. **A bounded retry on the classifier call only.** One retry, detector untouched. Cheap in the split
   specifically, because the two legs are concurrent: a classifier retry costs a second classifier
   round-trip, not a second safety round-trip, and the safety verdict is already in hand. **Preferred.**
2. **Make `intent_confidence` optional, absence routing to the ambiguity clarifier.** Defensible — an
   unreported confidence genuinely is low information, and asking the caller to clarify is the
   conservative response — but it is a **design change to the dialogue policy**, not a harness fix, and it
   would be smuggled in as an experiment artefact if done now. Deferred to a decision with `D18`'s retry
   ladder in view.
3. **Add a "you must always set `intent_confidence`" instruction to the classifier prompt.** **Rejected
   for rung C**: rung C's prompt is the merged prompt's intent half with the injury instruction removed
   and *nothing added*, which is what makes C−B attributable to the split. Adding a field instruction to
   rung C would confound the rung it is meant to isolate. Available to rung D, which is allowed to change
   wording — and if it is used there, D−C stops being purely about the injury instruction and that must be
   said out loud.
4. **Drop `intent_confidence` from the classifier schema entirely.** Rejected: the ambiguity clarifier
   (`D18`, `INTENT-TAXONOMY.md` §2.3) routes on it. Removing a field because the model is unreliable about
   filling it is how a dialogue policy loses a branch nobody notices.

**None of these is applied during Stage 4.** The harness records the event and scores it per the table
above; the ladder measures configurations, and changing one mid-ladder would make its rungs
incomparable. The remedy is chosen after the ladder reports, with the rate in hand.

## Stated expectation, so the result can surprise me

I expect the split's classifier drop rate to be **non-zero but under 1%** — order 1–5 events per 790-call
rung — and the merged rungs to stay at **0**, since they have already produced 1,580 clean calls under this
exact protocol. If the merged rungs also drop fields once the harness stops crashing on the first event,
then this is a property of Nova Micro and forced tool use generally, not of the split, and the
`ADR-014` §4 comparison is unaffected by it.

**What would change the conclusion:** a rate at or above 1% on the split rungs makes the split unshippable
on availability grounds even if it wins on quality — and `ADR-014` §4's selection rule does not currently
mention availability, which is a gap in that ADR that this document is recording rather than quietly
patching.

---

## Outcome — appended after the ladder ran

See `RESULTS.md` §3.4 for the measured rates and the ladder they belong to.
