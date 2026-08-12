# Pre-registration — how a dropped `safety_flag` is scored

**Written 2026-08-12, after the Stage 0.5 measurement finished and before its result was opened.** The
run completed while this document was being written; the JSON was not read, and the only observation from
the aborted first attempt is that the rate is non-zero somewhere at temperature 0.7 — one event, on the
fourth pass, which is what turned the crash into a measurement.

Marco's instruction: *"decide the threshold before you see the number… State now what rate you would
consider material, and whether a dropped-field event counts against union recall."*

This exists because the alternative is picking a threshold that the measured number happens to clear.

---

## 1. The structural fact this rests on

`agents/graph.py` wires exactly one path to the router:

```
START ─► l1_safety_check ─┬─ fired ──────► injury_escalation ─► END
                          └─ not fired ──► guardrails_input_check ─► route_and_classify
```

**The merged `classify_turn` call is only ever reached on turns where L1 did not fire.** There is no case
where a dropped field lands on a turn that L1 had already escalated — the router would not have been
called at all.

So there is no leniency branch to argue about. **Every dropped-field event is, by construction, a turn on
which L1 was silent and L2 was the only remaining detector.** Marco's reading — *"a turn that raises is a
turn where the safety detector produced no verdict"* — holds without exception, and it holds on precisely
the population that matters: L1 misses roughly 73% of indirect injury phrasing, so "L1 was silent" is the
normal case for exactly the utterances L2 exists to catch.

## 2. Scoring rules — fixed now

| Situation | Scored as |
|---|---|
| Dropped field on a turn that **must escalate** | **Union-recall MISS.** Silence is not a pass |
| Dropped field on a turn that **must not escalate** | **Excluded** from the false-escalation denominator, reported separately as a count |
| Dropped field, intent metrics | **Excluded** from macro-F1 and out-of-scope denominators, reported as a count beside them |
| Dropped field, availability | Counted in a per-turn **drop rate** over all attempts, reported for each temperature setting |

**The asymmetry between rows 1 and 2 is deliberate.** A turn with no verdict is scored against recall and
not against precision, because the cost of the two errors is not symmetric and `SUCCESS-METRICS.md` §2
already says so: *"a wasted transfer costs one human minute. A missed injury escalation is the failure
this system must not have."* Scoring a no-verdict turn as a non-escalation for recall and as a
non-escalation for precision would let the same event improve one metric while damaging the other, which
is the shape of a metric that can be gamed.

## 3. What counts as material — thresholds, before the number

### 3.1 Safety: zero tolerance, and this is entailed rather than chosen

**Any dropped-field event on a must-escalate turn is a C1 failure.** C1 is union recall 1.000 with no
tolerance; a miss is a miss regardless of whether it came from a wrong answer or from no answer. I am not picking this threshold — it follows from a constraint that already exists.

If that makes the merged baseline fail C1 outright, the merged baseline fails C1. Marco has already
accepted that outcome in advance: *"that is the honest reading of a guarantee that was written before we
knew this failure mode existed."*

### 3.2 Availability: the bands, and what each one obliges

At ~8 turns per 4-minute call, a per-turn drop rate `p` means roughly `1-(1-p)^8` of calls contain at
least one turn the system could not classify. There is **no retry on this path today** — the retry ladder
(`D18`) handles caller-side no-input and no-match, not a classifier exception — so a dropped turn is a
caller-visible failure, not a silent recovery.

| Measured per-turn rate | Reading | Obligation |
|---|---|---|
| **≥ 1%** | ~8% of calls hit an unclassifiable turn. Plainly unshippable | **Material correctness defect. Must be fixed inside Phase 7**, not deferred |
| **0.26% – 1%** | ~2–8% of calls affected | **Material.** Fix with a bounded retry on the classifier call, and record the latency cost against the 1,800 ms budget |
| **below ~0.26%** | Below what this run can resolve | **Report as "not resolvable at n=390 per setting", not as a rate.** Carry to `NOT-FIXED.md` with the observed count |

**0.26% is not a judgement, it is the measurement's resolution.** k=5 × 78 turns = 390 attempts per
setting, so one event is 1/390 ≈ 0.26%. Any rate below that is indistinguishable from zero at this sample
size, and reporting "0.1%" from this data would be inventing precision the run cannot support.

## 4. Stated expectation, so the result can surprise me

I expect the rate at temperature 0.7 to be **non-zero and small — order 0.3% to 1%** — and the rate at
temperature 0.0 to be **lower, possibly zero at this resolution**.

**What would change the conclusion:** if temperature 0.0 also drops the field at a material rate, the
defect is **not** temperature-driven, and unmerging moves from a fix for classification quality to the
primary remedy for a correctness defect. If neither setting drops it again in 780 attempts, the single
observed event is a rate estimate of 1/~390 with a confidence interval that includes very small numbers,
and it goes to `NOT-FIXED.md` rather than being fixed on the strength of one occurrence.

## 5. The remedy, ranked before the number is known

1. **A single-purpose detector emitting one boolean** — the leading Phase 7 hypothesis anyway. A model
   asked for one required field is a smaller target for field-dropping than one juggling four. **This is
   the preferred fix**, and saying so now prevents claiming afterwards that the ablation ladder "proved"
   what it was already designed to test.
2. **A bounded retry on the classifier call** — cheap and obvious, but it adds a full round-trip to a
   turn budget that already has L1, two `ApplyGuardrail` calls and a generation call in it, and it treats
   a symptom.
3. **Loosening the schema so `safety_flag` is optional with a fail-safe default of `true`** —
   **rejected in advance.** It would convert a loud failure into a silent one, which is precisely the
   property `ADR-004` built the required field to obtain. A detector that defaults to escalating on every
   malformed response also makes the false-escalation problem worse. Recorded here so it cannot be
   reached for later as the path of least resistance.

## 6. What `ADR-004` got right, stated before the number so it is not hindsight

ADR-004 claimed a schema-required field *"cannot be silently omitted without the call itself failing
validation — which is the mechanism, not just the intention, behind Q10's 'non-optional' requirement."*

**That is correct and it held.** The call raised; it did not return a classification with the safety field
quietly absent. Whatever the rate turns out to be, the failure was loud, and the ADR's mechanism is the
reason this is a measurable defect rather than an invisible one.

What ADR-004 did not anticipate is that the mechanism would fire in ordinary operation rather than as a
theoretical guard. Its Consequences section came close — *"a failure in that call affects both routing and
safety classification simultaneously"* — and accepted the risk on the grounds that L1 and L3 remain
independent. §1 above is why that mitigation is weaker than it reads: on the turns where L2 matters, L1
has already been silent.
