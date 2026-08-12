# Results — Phase 6

Real measurements. Every number was produced by `make eval` or by a cost-gated script in this repository,
and every number that failed is at its real value.

> **Read §0.1 before quoting any number from this report.** Phase 6 ran the whole Tier B harness **once**,
> against models sampling at temperature 0.7. Phase 7 measured the spread that produces and it is large.
> Roughly half the numbers below are **single draws**, not estimates; §0.1 says exactly which, and to how
> many decimal places each may honestly be read.

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

> **The 0.529 is not an artefact of which cases were chosen.** The obvious objection to it is that its
> 34-case denominator included **eight ordinary openings picked by hand**, so the rate depends on the
> picking. It was re-measured on a **complete, rule-based** population — every negative in the independent
> held-out set, 17 of them, nothing selected — and came back at **0.529 (9/17)** against the original's
> **0.529 (18/34)**. Two denominators built on different principles, same rate. §2.1 has the run.

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

## 0.1 The second correction — which numbers in this report are single draws

**This is a retrospective caveat on Phase 6, not a Phase 7 finding, and it is the same class of error as
§0.** Phase 6 ran the Tier B harness once and published the result as a scorecard. The harness calls Nova
Micro and Nova Lite, both of which were sampling at **temperature 0.7** — no `temperature` key was sent, so
Bedrock applied Nova's default. Phase 7 measured what that costs: **five runs × 78 turns at each of two
settings** (§3.3).

| | measured |
|---|---|
| Intent macro-F1 range across five identical runs at 0.7 | **0.488 – 0.551**, sd 0.024 |
| Turns whose **intent** was not stable across those runs | **35 of 78** |
| Turns whose **`safety_flag`** was not stable across those runs | **13 of 78** |
| The same, at temperature 0.0 | **0 of 78**, sd 0.000 |

**A scorecard printed to three decimal places from one draw of that distribution overstates its own
precision, and it did so in the document a reader is most likely to quote from.** §0's error was reporting
one half of a trade-off pair. This one is reporting a sample as though it were an estimate. Both are
failures of the same kind: **a number that looked settled, published without the thing that would have
shown it wasn't.**

### Which is which

Not every number here is affected, and saying "everything is noisy" would be as unhelpful as saying nothing.
The dividing line is whether a model sampled anything to produce the number.

| Numbers | Produced by | Reproducible? |
|---|---|---|
| **All L1 figures** — §2's recall/false-escalation before and after, §9's gate demonstration | `lexicon.py`, deterministic Python, no model call | **Exactly.** Same input, same output, every time |
| **Retrieval recall@5 0.800, MRR 0.663** (§5) | Titan embeddings + cosine over a fixed index | **By construction** — the embeddings call has no sampling parameter. Argued, not re-measured |
| **Bedrock spend $0.0138** (§7) | Token accounting from the responses | **Exact.** It is a bill, not an estimate |
| **L2 recall 19/19, false-escalation 0.529, union 0.529** (§0, §2) | Nova Micro @ 0.7, **one sample per item** | **Single draw** as published. Since re-measured: **union recall holds at 1.000 under k=5**, and 0.529 reproduces on a complete rule-based denominator (§2.1) |
| **Intent macro-F1 0.623, out-of-scope 0.200** (§3) | Nova Micro @ 0.7, one run | **Single draw — and the outlier.** See §3.3: 0.623 sits ~4.3 sd above the distribution five later runs describe |
| **Groundedness 1.000 (9/9), answer relevance 1.000 (9/9)** (§4) | Claude Haiku 4.5 judge @ 0.0, judging **Nova Lite output generated @ 0.7** | **Single draw.** The judge is deterministic; what it judged was not. Also 9 items — a ceiling on nine |
| **Redundancy defect 0/9, "known intermittent"** (§4, `CF5`) | Same path | **Single draw, and already labelled as one.** "Intermittent" was the right word and this is its mechanism |

**How to read the affected numbers:** to the nearest 0.05, not to three decimals, unless they have been
re-measured at temperature 0.0 with k ≥ 5. Nothing in this report has been, except the intent metrics in
§3.3.

### What survives, and why it is not everything

The **conclusions** of §0, §1 and §3.2 stand, and each for a reason that does not depend on a point estimate:

- **§0's false-escalation finding.** 0.529 is not stable to three decimals; the margin is 5× the ≤ 0.10
  TARGET, which is ~20 sd of anything measured here. The specific value moves; the verdict does not.
- **§1's rule-shaped vs vocabulary-shaped result.** L1 is deterministic. That entire section is exactly
  reproducible.
- **§3.2's merge evidence.** A **within-run** association (27/28 vs 3/50, Fisher p < 10⁻⁸) — it does not
  ask two runs to agree about anything.

What does **not** survive is every use of these numbers as a *baseline*: the regression gate, any
before/after comparison across runs, and any claim that a Phase 7 change improved something. Those need a
temperature-0.0 re-baseline, which is why the ablation protocol requires one (`D30`).

### One place the fix has not been applied

`ROUTER_TEMPERATURE = 0.0` pins the **router**. `generate_response()` still sends no `temperature` and so
still runs Nova Lite at 0.7 — meaning §4's generation numbers remain single draws from a stochastic process
even now, and `CF5`'s intermittent redundancy defect is a direct symptom. It is left as-is deliberately
rather than overlooked: pinning it would invalidate Phase 6's generation baselines mid-phase, and whether a
*spoken* response should be deterministic is a design question, not a hygiene one. **Named here as an open
item** (`Q12`), owned by Phase 7's verification stage.

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

### 2.1 Union recall 1.000 survives repetition — measured, not assumed (Phase 7 Stage 2)

Phase 6's `1.000 (26/26)` was **one sample per item**, and `C1` then made it a non-tradeable constraint.
Marco's instruction at Phase 7 approval: *"if the merged baseline does not hold 1.000 under repetition,
report it as a correction to Phase 6 in RESULTS.md, not as a footnote in Phase 7."*

Measured on the **unchanged merged configuration**, before any candidate existed to be flattered by the
comparison — 43 items × k=5 = **215 real Nova Micro calls, $0.0083**
(`scripts/measure_union_baseline.py`, `evals/baselines/union_baseline_k5_20260812.json`):

| | k=5, any-sample-miss |
|---|---|
| **Union (L1 ∪ L2) escalation recall** | **1.000 (26/26)** — holds |
| Union false-escalation, **rule-based** denominator | **0.529 (9/17)** |
| L1 alone | recall 0.269, false-escalation 0.059 |
| Items whose L2 verdict varied across five samples | **0 of 43** |

**No correction is owed.** Phase 6's figure was an n=1 observation that happens to be right, which is worth
distinguishing from an n=1 observation that is trusted — the first is luck, the second is method. `C1` now
attaches to a number measured under a stated protocol.

**Two things worth naming rather than banking:**

1. **The 0.529 was not an artefact of a hand-picked denominator.** §0's rate came from 34 cases, eight of
   them ordinary openings selected by ID (`measure_l2_precision.py` says so in its own docstring). This
   run's 17 negatives are *every* negative in the independent set — a complete, rule-based population — and
   it lands on the same rate. Two different denominators, same answer: the false-escalation finding is
   about the detector, not about which cases were chosen.
2. **k=5 verified determinism; it did not estimate a spread.** At temperature 0.0 five identical answers
   was the expected outcome, and 0 of 43 items varied. This was stated as the reading *before* the run
   (see the script's docstring), because "all five agreed" is otherwise easy to present as a stability
   result the design earned rather than one it was pinned into. The useful part is that §3.3's determinism
   was measured on the 78 golden first turns and has now held on a population it was never tested on.

**Ledger:** `evals/holdout_ledger.json` — **1 distinct configuration fingerprint** measured against the
independent set. One is an honest verification. That count is published here precisely because it can only
ever embarrass us: it is the number that would reveal tuning against the verification set, and it is
computed from the file rather than asserted.

### What these numbers do not establish

- **The held-out set was written by a language model and classified by a language model.** It is
  independent of *the detector*; it is not independent of *language models in general*. Agent-authored
  euphemism may be more model-legible than what a panicking human says at the roadside. **A real-world
  recall claim requires human-authored phrasings, and this project has none.** Also recorded in the
  README, because anyone weighing the safety claim needs it without opening this file.
- ~~**n = 26 positives, one sample each.** L2 is stochastic. 26/26 on one run is not a rate.~~
  **Addressed 2026-08-12** — §2.1 re-measured it at k=5 and the 1.000 holds. The caveat was correct when
  written and the measurement is what retires it, not the passage of time.
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

> **Corrected 2026-08-12 by Phase 7 Stage 0.** Four write-up errors in this section, and one measurement
> caveat that is more serious than any of them. Corrections are inline below; the caveat is §3.1. The two
> harness-produced numbers in the table — 0.623 and 0.200 — are unchanged by the write-up corrections.

Real Nova Micro through the shipped `classify_turn` path, first turn of all **78** labelled conversations.
(This section previously said 73. The corpus is 78 conversations / 141 turns, and has been since before
this run; the harness iterated all 78. Two other counts in this document's history — "71 conversations,
134 turns" and "77 conversations, 140 turns" — were also wrong. **78 / 141 is the verified figure**, and
`evals/baselines/tier_a_baseline.json` recorded it correctly the whole time while the prose did not.)

| Metric | Kind | Threshold | **Measured** |
|---|---|---|---|
| Intent macro-F1 | GATE | ≥ 0.90 | **0.623** ❌ |
| Out-of-scope detection | TARGET | ≥ 0.85 | **0.200** ❌ |

27 of 78 misclassified, and the errors are not scattered — **they are dominated by the same
over-triggering §0 measures.** **Twelve** of the 27 are benign turns classified as `InjuryEscalation`
(previously stated as ten), including *"I need to report an accident."*

*"Someone keyed my car in a parking lot."* was cited here as one of them. **It was not.** That turn
(`fac-003`) was classified with the *correct* intent; what it triggered was L2's `safety_flag`. Citing a
safety-flag false positive as an intent misclassification blurred the exact distinction §3.1 and Phase 7
exist to examine, and it is the kind of error that makes a finding look tidier than it is.

Out-of-scope is the second cluster: **four of the six** conversations whose expected intent is
`OutOfScope` were misrouted, all four into in-scope intents. (Previously: *"all five … were misrouted,
four into in-scope intents"* — wrong on both counts, and internally inconsistent with the 0.200 recall in
the table above, which is 1/5.) The 5-vs-6 discrepancy is real and worth naming: **the out-of-scope metric
counts by conversation *category* while the confusion list counts by expected *intent*, and the two
definitions disagree** on `adv-004`, an adversarial conversation whose expected intent is `OutOfScope`.
Neither definition is wrong; having both unlabelled in the same section was.

A home-insurance claim reads as `InjuryEscalation`; a life-insurance question reads as `CoverageQuestion`.
The router has no strong notion of the product boundary.

### 3.1 These are n=1 samples from a high-variance process

**The router runs at Nova's default sampling temperature.** `classify_turn` passes
`inferenceConfig={"maxTokens": ...}` and sets neither `temperature` nor `topP`; AWS's Converse
documentation gives the defaults as **temperature 0.7, topP 0.9**. The judge in `evals/tier_b.py` sets
`temperature: 0.0` explicitly. The classifier — the component whose output is supposed to be a decision —
does not.

Re-running the identical code over the identical 78 turns on 2026-08-12 gives:

| | Phase 6 run | Stage 0 re-run | Δ |
|---|---|---|---|
| Misclassified | 27 / 78 | **39 / 78** | +12 |
| Accuracy | 0.654 | **0.500** | −0.154 |
| Intent macro-F1 | 0.623 | **0.474** | **−0.149** |
| Out-of-scope recall | 0.200 (1/5) | 0.167 (1/6) | — (different denominators, see above) |

Only 25 of the two runs' confusion sets are shared; 2 cases were wrong only in Phase 6 and 14 only in the
re-run.

> **Corrected again, 2026-08-12, by the measurement described in §3.3.** The attribution below — that
> temperature explains this swing — **is not supported by the data.** Five runs at each setting put the
> temperature-0.7 spread at **0.063**, not 0.149, and Phase 6's 0.623 falls *outside* that distribution
> entirely. The instability is real and temperature causes most of it; the size of *this particular gap*
> is not accounted for. §3.3 has the measurement and the unexplained residual. The three consequences
> below still hold, and the first two hold more strongly.

**A 0.149 swing on identical inputs is roughly five times the regression gate's 3-point TARGET
tolerance.** Three consequences, stated plainly:

1. **Every Tier B number in this document is a single draw**, not an estimate. That includes the
   false-escalation 0.529 that §0 is built on. §0's *conclusion* does not depend on the exact value — the
   rate is far above target under any reading, and the coupling in §3.2 is a within-run property — but
   the specific figures are not stable to three decimal places and should never have been printed as
   though they were.
2. **The regression gate cannot function against this much noise.** A 3-point tolerance on a metric that
   moves 15 points between runs will fire on luck and miss real regressions. The gate was demonstrated to
   have teeth (§9); it does not yet have a usable threshold for the Tier B metrics.
3. **n=2 establishes that the variance is large. It does not establish the distribution.** Two runs are
   not a spread. Quantifying it — and deciding whether the router should run at temperature 0 at all — is
   Phase 7 Stage 2 work, not a claim this section makes.

This is the same class of error as §0's: **a number published as a guarantee that was only ever an n=1
observation.** It was found by the same route — checking a thing that already looked settled. **§0.1 states
this as a caveat over the whole report** — which numbers are single draws and which are reproducible —
because a reader who quotes the scorecard will never reach this subsection.

### 3.2 The merge is real, measured at the item level

Phase 7 Stage 0 re-ran the merged call storing the **whole** `TurnClassification` rather than only
`.intent`, over all 78 first turns in one run:

| | `intent = InjuryEscalation` | other intent |
|---|---|---|
| `safety_flag` true | **27** | 1 |
| `safety_flag` false | 3 | 47 |

Given `safety_flag`, the intent is `InjuryEscalation` **27 times out of 28**. Without it, 3 times out of
50. Fisher exact p < 10⁻⁸. Restricted to the cases where Phase 6's two separate baselines happen to
overlap, the same association holds at p = 0.007.

**The two fields are very nearly the same decision wearing two names**, which is exactly what `D25`
predicted and what `ADR-004`'s merged structured output would produce. `RESULTS.md` §0's false-escalation
rate and this section's macro-F1 are two views of one behaviour.

### 3.3 Temperature, measured — and the part of §3.1 it does not explain

**5 runs × 78 turns at each of two settings; 780 real Nova Micro calls, $0.0303.**
`scripts/measure_temperature_variance.py`, raw data in
`evals/baselines/temperature_variance_20260812.json`.

| | temperature 0.7 (shipped through Phase 6) | temperature 0.0 |
|---|---|---|
| Intent macro-F1 | 0.488 – 0.551, **sd 0.024** | **0.518 on all five runs, sd 0.000** |
| Accuracy | 0.513 – 0.551 | 0.526 on all five |
| Out-of-scope recall | **0.000** on all five | **0.000** on all five |
| `safety_flag` fire rate | 0.341 | **0.397** |
| Turns whose **intent** flipped between runs | **35 of 78** | **0 of 78** |
| Turns whose **`safety_flag`** flipped between runs | **13 of 78** | **0 of 78** |
| `safety_flag` dropped from the response | **0 of 390** | **0 of 390** |

**Four results, three of which contradict something previously written here.**

**1. The instability is real, and per-item it is much worse than the aggregate suggested.** At 0.7, 35 of
78 turns did not produce a stable intent across five runs, and **13 produced a different `safety_flag`
verdict between runs.** A safety detector that changes its answer on 17% of turns is not something a gate
can be written against. At 0.0 that number is zero, across 390 calls.

**2. Temperature 0 buys reproducibility, not accuracy.** 0.518 sits *inside* the 0.7 range. The fix does
not move quality at all — it makes quality measurable. That distinction matters, because "we set
temperature to 0 and macro-F1 became 0.518" would read as an improvement and is not one.

**3. It probably makes the false-escalation problem slightly worse.** `safety_flag` fires on **39.7%** of
first turns at 0.0 versus 34.1% at 0.7. Some of the escapes that flattered the Phase 6 precision number
were sampling noise, not discrimination. Recorded now so the Phase 7 ablation cannot bank it as a gain.

**4. The dropped-`safety_flag` prediction was wrong.** [The pre-registration]
(phase7/PRE-REGISTRATION-dropped-safety-flag.md), written before this result was opened, expected
0.3–1% at temperature 0.7. Measured: **0 in 780 attempts.** Including the aborted first run, the total
observation is **1 event in roughly 1,000 attempts at 0.7** — below the ~0.26% this design can resolve.
Per the pre-registered rule that is reported as a count, not a rate, and carried to `NOT-FIXED.md`
rather than fixed on the strength of one occurrence. **No recall instability was observed at all:** all
13 flag-unstable turns are must-not-escalate cases, so every instance of it was a precision event.

### What temperature does not explain

Phase 6 measured **0.623**. Five runs at the same setting give **0.488–0.551**. That is roughly **4.3
standard deviations above** the distribution the shipped configuration actually produces. Stage 0's
0.474 is about 1.7 sd *below* the mean and is unremarkable.

So the honest reading is not "temperature swings macro-F1 by 15 points." It is: **Stage 0's re-run is a
normal draw, and Phase 6's number is the anomaly.** Out-of-scope recall says the same thing more starkly —
0.200 in Phase 6, and **0.000 in every one of the ten runs measured since**, at both temperatures.

Nothing in this repository accounts for it. The code is byte-identical (`git diff` across the Tier B
commit touches only the new `temperature` parameter, a no-op when unset), the corpus has not changed
since before that run, and Phase 6's stored macro-F1 reconstructs exactly from its own stored confusion
list — so it was a real measurement of something.

Two hypotheses remain and **neither can be tested from here**:

- **Model-side change.** `us.amazon.nova-micro-v1:0` is served through a cross-region inference profile;
  the seven hours between runs is ample for a serving-side update, and the client cannot observe one.
- **A heavier tail than five samples reveal.** Possible, but 4.3 sd is a long way out.

**This is left unexplained rather than attributed.** It is the second time in this phase that a
confident causal story had to be withdrawn after measurement, and inventing a third would be worse than
saying the residual is open.

The practical consequence is the one that matters: **at temperature 0.0 the configuration is
reproducible (sd 0.000 over 390 calls), so a future difference is a real change rather than a draw.**
If model-side drift is the explanation, then even a 3-point regression tolerance is unsafe across days
and the gate needs a re-baseline discipline rather than a threshold — an open question this phase now
carries rather than one it can close.

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

The **draw** column is not decoration: per §0.1, a `1×` number is one sample from a process whose macro-F1
moves 0.063 between identical runs, and must not be read to three decimals or used as a baseline.

| Metric | Kind | Threshold | Measured | | Draw |
|---|---|---|---|---|---|
| L1 escalation recall, labelled set | GATE | 1.00 | 1.000 | ✅ | deterministic |
| Union escalation recall, independent set | — | — | 1.000 | ✅ | **k=5** (§2.1) |
| **False-escalation rate** | **TARGET** | **≤ 0.10** | **0.529** | ❌ | **1×**; reproduced at 0.529 on a complete rule-based denominator (§2.1) |
| **Intent macro-F1** | **GATE** | **≥ 0.90** | **0.623** | ❌ | **1×**, and ~4.3 sd high (§3.3) |
| **Out-of-scope detection** | **TARGET** | **≥ 0.85** | **0.200** | ❌ | **1×**; 0.000 in all ten runs since |
| **Retrieval recall@5** | **GATE** | **≥ 0.90** | **0.800** | ❌ | deterministic |
| Retrieval MRR | TARGET | ≥ 0.75 | 0.663 | ❌ | deterministic |
| Groundedness | GATE | ≥ 0.95 | 1.000 (9/9) | ✅ | **1×**, n=9 |
| Answer relevance | TARGET | ≥ 0.85 | 1.000 (9/9) | ✅ | **1×**, n=9 |
| Redundancy defect rate | TARGET | — | 0/9 this run; defect known intermittent | ⚠ | **1×** |
| Bedrock spend, Phases 3–7 | GATE | ≤ $5.00 | $0.0138 | ✅ | exact |

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

### 9.1 The gate then caught a real change, by its own author, for a reason nobody anticipated

§9 above is a *demonstration* — a deliberately bad change, introduced to show the gate blocking it. On
2026-08-12 the gate blocked a change nobody had staged as a test.

Phase 7 Stage 2 implemented Marco's `C2` constraint by locking the independent held-out set behind a
declared verification run. `make test` failed immediately, on a rule written in Phase 6 for an entirely
different purpose:

```
Regression(metric='L1 recall, independent held-out set', baseline=0.269, current=None,
  detail='metric disappeared from the current run — deleting a metric is the cheapest way
          to make a gate green, so it counts as a breach rather than a pass')
```

**The gate was right and the change was wrong.** Locking the set had removed a metric from the Tier A
baseline as a side effect. That L1 number is already spent for tuning purposes (`C2` says so explicitly),
but it is deterministic, free to recompute, and a live check on the lexicon — so the change would have
traded away a working regression check to satisfy a rule aimed at something else entirely. The guard was
rebuilt to fire on the *pair* — reading the set **and** constructing a real Bedrock client, in either
order — which protects the model-based measurement that actually needed protecting and leaves the
deterministic read alone (`D33`).

Three things make this worth more than §9's demonstration:

1. **The author was the one caught.** Not a synthetic bad PR — a change made in good faith, by whoever was
   holding the pen, in service of a constraint the project owner had set.
2. **The rule fired for a reason it was not written for.** *"Deleting a metric is the cheapest way to make
   a gate green"* was written against the case of someone quietly dropping an inconvenient number. It
   caught an accidental deletion instead, which is the more common failure and the one nobody writes a rule
   for.
3. **It cost minutes.** The alternative was a silently narrower eval suite, which is exactly the class of
   defect `D28` found six phases late.

This is the second time in this project that a Phase 1 metric decision has caught something its authors
missed — §0's false-escalation TARGET was the first. Both were written before there was anything to
measure, and both were the sort of item that is easy to argue out of a spec on the grounds that it is
obvious and nobody would do the thing it forbids.

---

## 10. Not measured by Phase 6

Task success, containment, repair rate, turns-to-completion, context-handover completeness — these need
the full conversation harness driving multi-turn dialogues, which Phase 6 did not build.

**Latency is deliberately absent.** What this phase could measure is agent-internal turn latency; the
GATE is Lex-STT-completion to Polly-audio-start, which includes telephony, ASR and TTS legs this phase
never touches. Publishing an internal number next to the 1,800 ms budget would invite exactly the wrong
comparison. Phase 9 owns it.
