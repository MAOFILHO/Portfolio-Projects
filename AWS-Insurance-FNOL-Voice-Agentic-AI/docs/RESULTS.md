# Results — Phase 6

Real measurements. Every number was produced by `make eval` or by a cost-gated script in this repository,
and every number that failed is at its real value.

---

## 0. The correction, up front

An earlier reading of the Stage 6 data reported that the layered safety detector was **vindicated**,
on the strength of L2 catching 19 of 19 phrasings L1 missed.

**That reading was incomplete and the conclusion it supported was wrong.** L2's recall was measured; its
precision was not. Measuring it changed the answer:

| | recall | false-escalation |
|---|---|---|
| L1 (deterministic lexicon) | 0.269 | **0.029** |
| L2 (Nova Micro classifier) | **1.000** on L1's misses | **0.529** |
| **L1 ∪ L2 — what a caller experiences** | **1.000** | **0.529** |

The union catches every injury in the test set **and escalates more than half of the calls that should
never be escalated**, including *"I need to report an accident."* and *"If another driver hits me and
it's their fault, am I covered for the damage?"* — the two most ordinary openings this system has.

`SUCCESS-METRICS.md` §4 sets false-escalation at **TARGET ≤ 0.10**, and says in as many words why: it
"exists so safety cannot be bought by transferring everything." That is precisely what the current
configuration does. The measured rate is **5× the target**.

**The honest summary is not "the layered design works." It is: the layered design delivers the recall
guarantee it was built for, at a false-escalation cost that makes the system as currently configured
unusable as an IVR.** Both halves are real, and the second was found only because the anti-gaming metric
Phase 1 insisted on was actually implemented and run.

### Neither reader caught it. The metric did.

This is not a story about one person's oversight, and reporting it that way would be the more flattering
version rather than the true one. The incomplete conclusion was **written** on recall alone and
**endorsed** on recall alone: the 19/19 result was presented as vindication, and the project owner read it,
agreed, and said so in writing. Two readers, both working from a specification that already contained the
precision metric, both failed to notice it had never been computed.

What caught it was neither of them. It was `SUCCESS-METRICS.md` §4's false-escalation TARGET — written in
Phase 1, before any detector existed, for the reason stated there at the time: it *"exists so safety cannot
be bought by transferring everything."* Phase 6's standing rule was to implement **every** metric in that
document rather than the ones that felt relevant while building. Implementing this one produced 0.529 and
reversed the phase's headline claim.

**That makes this the strongest evidence in the project that the metric design earned its keep, and it is
worth more than any individual number in this report.** A metric that only ever confirms what its authors
already believe has not been tested. This one contradicted both of them, on the phase's central claim, in
the same session the claim was made — which is exactly the case anti-gaming metrics are written for, and
exactly the case where skipping one is easiest, because the result already looks good and nobody is looking
for a reason to doubt it.

The generalisable form: **a favourable result on one half of a trade-off pair is not a result.** Recall
without precision, containment without escalation appropriateness, latency without cost, coverage without
false-positive rate. The pairing has to be built into the harness in advance, because at the moment a good
number lands, neither the author nor the reviewer wants to go looking for its counterweight — and both
will accept it if nothing forces the question.

---

## 1. Rule-shaped and vocabulary-shaped defects

The most transferable result in this project, and the strongest evidence that splitting L1 from L2 was a
correct architectural decision rather than a cautious one.

**Two defect classes behave completely differently under repair, and which one you have determines
whether fixing it is worth doing.**

A single change — giving L1 a clause-scoped negation rule — was measured against a held-out set the fix
had never seen:

| | before | after | change |
|---|---|---|---|
| **False-escalation** (precision defect) | 0.412 | **0.059** | **−86%** |
| **Recall** (coverage defect) | 0.192 | 0.269 | +40% |

Same fix, same effort, same data, opposite outcomes.

**Rule-shaped defects generalise when repaired.** The seven false positives were not seven mistakes; they
were one — the lexicon had no notion of polarity and matched injury words as bare substrings, so *"nobody
was hurt"* fired on `hurt`. Polarity is a *property of language*, not a list of phrases. Encode the rule
once and it transfers to phrasings nobody enumerated. It did: false-escalation fell by 86% on utterances
the author never saw.

**Vocabulary-shaped defects do not.** To catch *"they covered him with a sheet"* you must first have
thought of *"they covered him with a sheet."* There is no rule to discover — the space of ways a human
can indicate a death without naming it is not enumerable, and each entry you add buys you exactly one
phrasing. Recall moved by two cases out of twenty-one misses.

### Why this generalises beyond safety detection

The distinction predicts, before you start, whether effort spent on a deterministic component will
compound or evaporate:

- **A component whose failures are rule-shaped is worth investing in deterministically.** Fixes compound,
  behaviour stays inspectable, cost stays zero, and latency stays negligible.
- **A component whose failures are vocabulary-shaped should not be asked to carry that responsibility at
  all.** Every fix is a one-off, the artifact grows without generalising, and the work has no end
  condition. Adding lexicon entries in response to missed cases is a treadmill that feels like progress
  because the labelled set keeps going green.

**This is the actual argument for the L1/L2 split**, and it is stronger than the one `ADR-010` was
written on. The original rationale was defence-in-depth — two detectors are safer than one. The measured
rationale is sharper: **the two layers should own the defect classes they can actually fix.** L1 owns
precision, latency, determinism and structural enforceability (`assert_dominates`). L2 owns recall,
because recall is vocabulary-shaped and only a model generalises over vocabulary.

§0 shows the corollary that completes it: **the split works only if each layer is held to the metric it
owns.** L2 currently carries recall superbly and precision not at all, and nothing in the system
constrains its precision. That is the Phase 7 problem, and it is now a specified one rather than a vague
concern.

---

## 2. Safety detector — full numbers

Ordering was fixed by Marco: the independent held-out set was generated **before** `lexicon.py` was
touched, so the "before" column is uncontaminated. Post-fix figures are contaminated by construction.

| Set | Recall before | after | False-escalation before | after |
|---|---|---|---|---|
| Golden labelled (GATE) | 0.778 (7/9) | **1.000 (11/11)** | 0.000 | 0.000 |
| **Independent held-out (L1)** | **0.192 (5/26)** | 0.269 ⚠ | **0.412 (7/17)** | 0.059 ⚠ |
| Weak held-out | **0.400 (6/15)** — final, not revisited | — | 0.250 | — |
| **L2 on L1's misses** | — | **19/19 = 1.000** | — | **0.529 (18/34)** |
| **Union (L1 ∪ L2)** | — | **26/26 = 1.000** | — | **0.529** |

⚠ Contaminated: the fix was made after seeing this set's results. `0.192` and `0.412` are the honest
readings.

L2 caught every fatality euphemism L1 has no entry for — *"we lost her"*, *"he didn't make it"*, *"they
covered him with a sheet"*, *"she passed at the scene"*. It also fired on *"the car's totalled"*, *"the
front end is completely destroyed"*, and *"she took a real beating, poor thing, I've had that car eleven
years"* — three descriptions of **vehicle** damage.

### What these numbers do not establish

- **The held-out set was written by a language model and classified by a language model.** It is
  independent of *the detector*; it is not independent of *language models in general*. Agent-authored
  euphemism may be more model-legible than what a panicking human says at the roadside. **A real-world
  recall claim requires human-authored phrasings, and this project has none.** Also recorded in the
  README, because anyone weighing the safety claim needs it without opening this file.
- **n = 26 positives, one sample each.** L2 is stochastic. 26/26 on one run is not a rate.
- **No real caller has ever spoken to this system.**

### One false positive deliberately left unfixed

> *"the ambulance did come out but after they'd had a look at the three of us they said there was no need
> for anyone to go in"*

The negation sits to the **right** of the trigger word, and `_is_negated` scopes backwards only.
Right-scoped all-clear is a real, buildable second category — and the only evidence for it is in the
independent held-out set. Building it would mean fixing against held-out data and spending the one
uncontaminated measurement this phase has. Named as an open gap instead; Marco confirmed the trade.

---

## 3. Intent classification — GATE failed

Real Nova Micro through the shipped `classify_turn` path, first turn of all 73 labelled conversations.

| Metric | Kind | Threshold | **Measured** |
|---|---|---|---|
| Intent macro-F1 | GATE | ≥ 0.90 | **0.623** ❌ |
| Out-of-scope detection | TARGET | ≥ 0.85 | **0.200** ❌ |

27 of 73 misclassified, and the errors are not scattered — **they are dominated by the same
over-triggering §0 measures.** Ten of the 27 are benign turns classified as `InjuryEscalation`, including
*"I need to report an accident."* and *"Someone keyed my car in a parking lot."*

Out-of-scope is the second cluster: all five out-of-scope conversations were misrouted, four into
in-scope intents. A home-insurance claim reads as `InjuryEscalation`; a life-insurance question reads as
`CoverageQuestion`. The router has no strong notion of the product boundary.

**These are one finding, not three.** The router is a single Nova Micro call doing intent classification
and L2 safety detection simultaneously (`ADR-004`'s merged call), and it is heavily biased toward
`InjuryEscalation`. That bias buys the perfect safety recall in §0 and pays for it in macro-F1,
out-of-scope detection, and false escalation at once. **Whether merging the two jobs into one call was
the right design is now a live question for Phase 7**, with data behind it rather than intuition.

---

## 4. Generation quality — passed, judged by a different vendor's model

`us.anthropic.claude-haiku-4-5` as judge, deliberately a different vendor and family from Nova Lite,
because Nova Lite judging Nova Lite is a self-preference setup. 3 trials × 3 cases.

| Metric | Kind | Threshold | Measured |
|---|---|---|---|
| Groundedness | GATE | ≥ 0.95 | **9/9** ✅ |
| Answer relevance | TARGET | ≥ 0.85 | **9/9** ✅ |
| Correct for *this* caller | — | — | **9/9** ✅ |

The third row is the one worth noting: `cq-003` asks about a benefit the caller has **not** elected while
the retrieved passage fully describes that benefit. A RAG-only answer would be fluent, well-grounded in
the retrieved text, and wrong. All three trials answered "you are not covered." The election lookup is
doing real work.

**Judge caveat, per Phase 1's standing rule:** a judge score is never sole evidence. All nine answers were
read; the judge's verdicts matched human reading on all nine. That is a small sample and is reported as
one.

### `RentalTowingEntitlement` redundancy — `CF5`

**0/9 redundant on this run.** The defect did not reproduce in three fresh trials of the exact scenario
that produced it twice before. This is consistent with what Stage 8 concluded — the prompt fix is
**probabilistic, not deterministic** — and three clean trials do not retire it. The detector's teeth are
proven against the two committed real defective outputs, not against a live run that happened to be
clean.

**General-mechanics leak: 2/9**, both on `rte-001`, both volunteering the corpus's 20-day cap alongside
the caller-specific answer. This is the divergence that persists.

---

## 5. Retrieval — GATE failed, on real Titan vectors

| Metric | Kind | Threshold | Measured |
|---|---|---|---|
| recall@5 | GATE | ≥ 0.90 | **0.800 (8/10)** ❌ |
| MRR | TARGET | ≥ 0.75 | **0.663** ❌ |

Computed from a committed fixture of real `amazon.titan-embed-text-v2:0` vectors, so the numbers are
genuinely real and recomputable offline at $0.00. Two genuine misses: `cq-005` (rideshare/commercial use)
at rank 8, `cq-008` (collision repairs) at rank 6.

**An instrument bug was caught before publishing.** Two of the ten gold labels named text that exists
nowhere in the corpus — one a substring appearing only in a section heading, which the chunker does not
carry into chunk text; the other the wrong source file. Both produced `rank None`, arithmetically
identical to the retriever failing to find a passage that was there. Recall would have been published as
0.700, and the obvious next move — "improve retrieval" — would have been effort aimed at a defect that
did not exist. `validate_gold_labels()` is now a gate in its own right: a broken label fails the run
rather than being folded into a score.

---

## 6. Instrument defects found this phase

Recorded as a category because all three share a property: **a harness defect produces a plausible number
that nobody investigates, which makes it worse than an agent defect.**

| # | Defect | What it would have published |
|---|---|---|
| 1 | L1 gate scored `inj-011` as a miss, though the corpus labels it L2-expected | Recall 0.700 instead of 0.778, driving euphemisms into the deterministic lexicon — L2's job |
| 2 | `--json-out` did not create parent directories | The report printed, the baseline silently never written |
| 3 | Two gold labels matched no chunk | Retrieval recall 0.700 instead of 0.800, as a model failure |

A fourth, in the code under test rather than the harness: `\b` matches nothing immediately before an
apostrophe-t contraction, so `\bn't\b` never fires inside `isn't` or `don't`. Present in two separate
places, independently written. In the negation cues it meant **no `-n't` contraction registered as a
negation at all.**

---

## 7. Cost

| Run | Calls | Cost |
|---|---|---|
| Embedding fixture (×2, regenerated after label fix) | 62 | $0.000274 |
| L2 recall measurement | 22 | $0.000852 |
| Tier B: intents + generation + judge | 96 | $0.010945 |
| L2 precision measurement | 34 | $0.001326 |
| **Total** | **214** | **$0.013397** |

**Phase 6 sub-budget: $0.0134 of $1.00.** Standing Bedrock cap: ≈$0.0138 of $5.00.

Tier A — the L1 numbers, retrieval, corpus checks, redundancy detection — costs **$0.00** and needs no
credentials. That is what makes it usable as a per-PR gate.

---

## 8. Scorecard

| Metric | Kind | Threshold | Measured | |
|---|---|---|---|---|
| L1 escalation recall, labelled set | GATE | 1.00 | 1.000 | ✅ |
| Union escalation recall, independent set | — | — | 1.000 | ✅ |
| **False-escalation rate** | **TARGET** | **≤ 0.10** | **0.529** | ❌ |
| **Intent macro-F1** | **GATE** | **≥ 0.90** | **0.623** | ❌ |
| **Out-of-scope detection** | **TARGET** | **≥ 0.85** | **0.200** | ❌ |
| **Retrieval recall@5** | **GATE** | **≥ 0.90** | **0.800** | ❌ |
| Retrieval MRR | TARGET | ≥ 0.75 | 0.663 | ❌ |
| Groundedness | GATE | ≥ 0.95 | 1.000 (9/9) | ✅ |
| Answer relevance | TARGET | ≥ 0.85 | 1.000 (9/9) | ✅ |
| Redundancy defect rate | TARGET | — | 0/9 this run; defect known intermittent | ⚠ |
| Bedrock spend, Phases 3–7 | GATE | ≤ $5.00 | $0.0138 | ✅ |

**Three GATEs fail and two TARGETs miss.** Per `SUCCESS-METRICS.md` §1, a failing gate means the system is
not working, regardless of the other numbers — and that is the correct description of where this system
is at the end of Phase 6. Phase 6 was specified as pre-tuning; these are the numbers tuning starts from,
reported at their real values rather than adjusted to make the phase look complete.

---

## 9. The regression gate, demonstrated

`SUCCESS-METRICS.md` §9: "an untested gate is not a gate." `scripts/demonstrate_regression_gate.py`
patches the lexicon in memory (never on disk) and shows the gate blocking the result.

The bad change is deliberately **subtle and plausible**: removing `"unconscious"` and `"died"` from the
presence keywords, both of which look redundant next to `"unresponsive"` and `"fatal"`. Nothing crashes.
It reads like tidying.

```
before      L1 recall, labelled set   1.000
after       L1 recall, labelled set   0.818
GATE FAIL   must be 1.000. Missed: inj-002 "She's unconscious in the passenger seat."
REGRESSION  1.000 -> 0.818 (degraded by 0.182, tolerance 0.03)
Would CI block this change?  YES
```

**And the system degrades gracefully.** Both phrasings L1 stops catching are ones L2 catches (measured,
`l2_recall_20260812.json`). System-level escalation recall is unchanged; only L1's contribution
collapses. A gate watching *only* the union would have seen nothing wrong.

That is the argument for gating each layer on the metric it owns rather than on the system's output: the
architecture is designed to hide exactly this kind of single-layer failure, and hiding it from a caller
is the point — hiding it from CI is not.

---

## 10. Not measured by Phase 6

Task success, containment, repair rate, turns-to-completion, context-handover completeness — these need
the full conversation harness driving multi-turn dialogues, which Phase 6 did not build.

**Latency is deliberately absent.** What this phase could measure is agent-internal turn latency; the
GATE is Lex-STT-completion to Polly-audio-start, which includes telephony, ASR and TTS legs this phase
never touches. Publishing an internal number next to the 1,800 ms budget would invite exactly the wrong
comparison. Phase 9 owns it.
