# Phase 7 build plan — Responsible AI, red-teaming, and the router/L2 split

**Status:** proposed 2026-08-12. No work begins until Marco types `APPROVED: Phase 7`.

Phase 6 was specified as pre-tuning and delivered three failing GATEs at their real values. Phase 7 is the
phase that gets to change the system. It has one central task and a set of Responsible-AI deliverables that
the roadmap has always assigned here; the central task is not one item among five.

---

## 1. The central task

`D25`: intent macro-F1 **0.623**, out-of-scope detection **0.200** and false-escalation **0.529** are one
finding, not three. The merged `classify_turn` call emits `safety_flag` and `intent` as **one structured
object**, so the recall bias deliberately placed on `safety_flag` — *"when in doubt, true"*, verbatim in
`bedrock_router.py`'s system prompt — has a direct path into `intent`. A model producing a structured object
makes its fields mutually consistent: once `safety_flag` is true, `intent: InjuryEscalation` is the coherent
completion.

**Leading hypothesis, per Marco's instruction: unmerge.** A recall-biased detector whose only job is injury,
running independently of a classifier whose only job is intent.

### `ADR-004` anticipated this, and its alternatives table has a gap worth naming

ADR-004's own Consequences section already wrote the exit: *"If Phase 6 ever needs the router and the safety
classifier to run on different models … the merged-call design would need to be split apart — recorded as a
design cost of the current optimization, to be paid only if evidence requires it."* The evidence now exists.
ADRs are immutable, so this is superseded by a new ADR, never edited.

But the more useful finding is in the alternatives table. ADR-004 rejected **"separate *sequential* calls for
routing and L2"** on the grounds of *"two round-trips against the same latency budget."* It never evaluated
**separate parallel calls** — and `SUCCESS-METRICS.md` §2, written earlier, had already specified L2 as a
*"single-purpose binary 'injury indicated?' call"* whose *"latency sits inside the 1,800 ms budget as a
parallel call, not a serial one."*

**The latency argument for merging only holds against an alternative the specification never asked for.**
Two concurrent Nova Micro calls cost `max(t₁, t₂)`, not `t₁ + t₂`. If that holds when measured, the merge
bought approximately nothing and cost the three metrics above. That is a hypothesis, not a conclusion, and
Stage 3 measures it.

### The hypothesis stated so it can fail

> Splitting the call reduces false-escalation and raises intent macro-F1 and out-of-scope detection
> **simultaneously**, without reducing union escalation recall.

Refuted if the split leaves false-escalation near 0.5 while macro-F1 stays near 0.62. **If that is the
result, it is reported as a refutation and the merge is not the cause** — the register in
`docs/phase7/NOT-FIXED.md` gains an entry and Phase 7 does not quietly try a fifth thing until something
moves.

### Two competing explanations, tested rather than assumed away

A single before/after cannot distinguish these, so the phase runs an ablation ladder instead:

| Rung | Configuration | What it isolates |
|---|---|---|
| **A** | Current merged call, unchanged | Reproduces Phase 6's numbers on the new tuning set, establishing comparability. Without this, every later delta is confounded by the change of set |
| **B** | Merged call, `InjuryEscalation` removed from the **classifier's output enum** | **Label-space coupling.** If macro-F1 recovers here, the problem was that the model had a coherent injury-shaped intent to fall into, not the merge itself |
| **C** | Split into two parallel calls; injury instruction copied **verbatim**, no rewording | **The merge itself.** Same words, two prompts. If false-escalation stays at 0.5, the instruction was the cause and the merge was innocent |
| **D** | Split + detector prompt revised | The only rung where tuning happens. Reported with its iteration count |

Rung B needs one clarification stated up front so it cannot be mistaken for a scope change: **removing
`InjuryEscalation` from the classifier's output enum does not remove an intent from the system.** CLAUDE.md's
six intents are unchanged, the golden set's labels are unchanged, and the escalation path is unchanged.
`D12` already says injury detection is *"a deterministic pre-node, not an intent classified by the model"* —
rung B makes the implementation match a decision taken in Phase 1.

Consequence for scoring, fixed now rather than after the numbers land: **intent macro-F1 is scored on the
system's *effective* intent** (detector fires → effective intent is `InjuryEscalation`), because that is the
system's actual behaviour. The classifier's raw output is reported **alongside** it, so the change is visible
and the split cannot be credited by a scoring convention.

---

## 2. Held-out set discipline — Marco's two constraints, made structural

> **C1.** Union recall 1.000 on the independent set is not tradeable. Any configuration that reduces it is
> rejected regardless of what it buys.
>
> **C2.** The independent set is spent for L1. Do not tune L2 against it either — it is the only
> uncontaminated measure of the union, and Phase 7 will want it intact to verify the fix.

Phase 6's criterion 14 said the same thing prospectively: *"the moment Phase 7 uses this set for tuning it is
spent — a fresh independent set is required for any recall number reported after that."* Three mechanisms,
because a rule this easy to violate accidentally should not rest on remembering it.

### 2.1 A separate tuning set, generated before anything changes

An isolated subagent with a clean context, never reading `agents/lexicon.py`, `bedrock_router.py`, either
existing held-out set, or `INTENT-TAXONOMY.md` §2.4 — the same protocol that produced the independent set,
seeded from different source vocabulary. ~80 items, both polarities, including the false-positive shapes L2
actually failed on (vehicle damage described in human terms, ordinary claim openings). **Generated and frozen
before rung A runs.** All tuning in rungs B–D happens against this set and nothing else.

### 2.2 The independent set is unreachable outside a declared verification run

`load_holdout(INDEPENDENT)` raises unless an explicit verification flag is set. Blunt, and deliberately so:
the failure mode is a convenient `make eval` during a tuning loop, not a decision to cheat.

### 2.3 An append-only fingerprint ledger

The real distinction is **not** "use it once." Repeated *sampling* of a fixed configuration is legitimate and
necessary — L2 is stochastic and `RESULTS.md` already says 26/26 on one run is not a rate. What contaminates
a held-out set is changing the system **in response to what it showed**.

So the discipline is: **one configuration, any number of samples.**

`evals/holdout_ledger.json`, append-only, records for every independent-set run: timestamp, a config
fingerprint (hash of router prompts, model IDs, tool schema, `lexicon.py`), sample count, and the metrics.
`RESULTS.md` publishes **the number of distinct fingerprints ever measured against this set.** One is an
honest verification. Six is de-facto tuning, visible to any reader without taking anyone's word for it.

### 2.4 C1 needs a protocol, and the protocol may reveal that 1.000 was luck

`1.000` came from n=26 with **one sample per item**. Making it a zero-tolerance, non-tradeable threshold
without saying what "1.000" means over repeated sampling would produce either a gate that fails on noise or a
number quietly taken from the friendliest run.

**Recommended reading of C1:** k = 5 samples per item; an item missed on **any** sample counts as a miss.
That is the safety-conservative reading and matches §2's *"recall wins any conflict."*

**The risk this creates, named before it happens rather than discovered as a surprise:** the *current merged*
configuration may not achieve 1.000 under k-sampling. If it does not, then the honest baseline is below 1.000,
Phase 6's figure was an n=1 artifact — a correction this phase would owe regardless — and C1 must attach to
the measured baseline under the same protocol rather than to a number that never survived repetition. The
merged baseline is therefore k-sampled **first** (Stage 2), before any candidate exists to be flattered by
the comparison. This costs one fingerprint in the ledger and is legitimate under §2.3: nothing is changed in
response to it.

**This is the one decision in the plan that needs Marco's word at approval**, because it interprets his
constraint rather than merely implementing it.

### 2.5 It amends a Phase 1 metric, and that has to be explicit

`SUCCESS-METRICS.md` §2 deliberately left held-out recall **OBSERVED with no threshold**, on the stated
grounds that *"a guessed threshold on a safety metric is exactly the kind of invented number constraint 13
forbids… It becomes a TARGET only once a real baseline exists."* C1 promotes it to a threshold. That is
allowed by §2's own escape clause — a real baseline now exists, and the threshold is measured, not guessed —
but it is a change to a Phase 1 document and gets an explicit, dated, argued edit, not a silent one. Phase 6's
standing rule applies: *"amended by an explicit, argued edit — not quietly dropped."*

---

## 3. Stages

A mid-phase gate after Stage 4, matching Phase 6's rhythm: report, stop, wait.

### Stage 0 — forensics on data already paid for ($0.00, no model calls)

`D25` claims three metrics share one root cause. That claim is **plausible from the aggregate numbers and has
not been checked at the item level.** Phase 6's per-item results are already on disk.

- Are the ten benign turns classified `InjuryEscalation` the **same turns** as the false escalations? If they
  are, `D25` is literally true and the ablation ladder is the right experiment. If they overlap only
  partially, there are two defects and the plan needs a second one.
- Does `safety_flag: true` co-occur with `intent: InjuryEscalation` at a rate materially above chance?
- Which of the 34 must-not-escalate cases fired, grouped by shape?

**A cheap falsification opportunity taken before spending anything on the remedy.** If Stage 0 refutes `D25`,
Stage 1's ADR says so and the plan changes before it is built.

**✅ Done 2026-08-12. `D25` confirmed at the item level** — 27/28 vs 3/50, Fisher p < 10⁻⁸. Marco's
refutation condition is not met, so the rungs are green-lit. Stage 0 also found four write-up errors in
`RESULTS.md` §3 and that `make lint`/`make typecheck` had never covered `evals/` or `scripts/` (`D28`).

### Stage 0.5 — temperature, measured then fixed (unplanned; added by what Stage 0 found) ✅ 2026-08-12

Not in the original plan. Stage 0's re-run differed from Phase 6's by 0.149 macro-F1 on identical inputs,
which made every planned comparison meaningless until the variance was characterised. 5 runs × 78 turns at
each of two settings, 780 real calls, $0.0303:

- **Temperature 0.7** (shipped through Phase 6, Nova's default — no `temperature` was ever sent): macro-F1
  0.488–0.551, **35/78 turns with an unstable intent, 13/78 with a different `safety_flag` verdict**.
- **Temperature 0.0**: 0.518 on all five runs, **0/78 unstable**, sd 0.000.
- `ROUTER_TEMPERATURE = 0.0` shipped (`D27`). **It buys reproducibility, not accuracy** — 0.518 sits inside
  the 0.7 range — and it likely makes false escalation slightly *worse* (flag fires on 39.7% vs 34.1%),
  recorded before the ladder so it cannot be banked as a gain.
- **A causal attribution withdrawn** (`D29`): temperature does not explain Phase 6's 0.623, which sits ~4.3
  sd outside the distribution five later runs describe. Left unexplained rather than attributed.
- The **dropped-`safety_flag` pre-registration** was written and committed before the result was opened.
  Measured 0 in 780; the pre-registered expectation of 0.3–1% was wrong, and the C1 rule stands unused
  rather than relaxed.

### Stage 1 — `ADR-014`, written before any code ✅ 2026-08-12

`docs/adr/ADR-014-router-l2-split.md`. Supersedes **`ADR-004` §1 only** — the merge. ADR-004 §2's
generation-tier flag, its Q10 separation and its forced-tool-use mechanism are re-asserted as invariants.

**It does not decide the split, and that is deliberate.** Two explanations fit every number equally well
(the merge; the label space), one of them is a one-line enum deletion, and no measurement in hand separates
them. Recording "we split the call" before the ladder runs would make the ladder ceremonial — the failure
mode this phase has already corrected three times. So ADR-014 decides what the evidence supports and
pre-commits the rest:

- **The merge loses its default status.** Its stated deciding factor is void — ADR-004 rejected separate
  *sequential* calls and never evaluated separate *parallel* ones, while `SUCCESS-METRICS.md` §2 had
  already specified L2 as a parallel single-purpose call. The burden is now symmetric; rung A must earn its
  place like every other rung.
- **A decision rule fixed before the numbers exist** (§4): admissibility (C1 + the invariants), selection
  (false-escalation must improve by **≥ 2 sd measured at k=5**, macro-F1 must not degrade by the same
  standard), and **ties go to the simplest configuration — B beats C beats D**. Written down now because
  when the numbers land, the split will be the interesting result and the enum deletion the boring one.
- **Pre-committed readings** of each outcome, including the two that embarrass the hypothesis: *B recovers
  and C adds nothing* → ship B, the merge was innocent; *C ≈ A* → the injury instruction is the cause,
  report a refutation and stop.
- **Five invariants** (`I1`–`I5`) binding whichever rung wins. `I3` — the construction-time dominance check
  on the detector — is the one the split *creates*: merged, the safety verdict was structurally inseparable
  from routing, an ugly property that made bypass impossible. Two calls make bypass expressible for the
  first time.
- **Latency and cost analysed**: +$0.0003 per conversation (0.2% of marginal cost, derived from this
  project's own bill), so cost decides nothing; `max(t₁, t₂)` is a hypothesis with a **pre-committed
  fallback** — if concurrency measures closer to the sum, B wins even on a quality tie.
- **One verified implementation constraint**: boto3 clients are thread-safe, but the docs warn that calling
  `boto3.client()` *inside* a concurrent context risks response-ordering and SSL failures — which is
  exactly what `get_bedrock_runtime_client()` does today. One client is created before the fork and shared;
  this also keeps `ADR-009`'s SnapStart rule intact.

**Requires `ADR-015`** to record which rung won and the rule applied to it, including the case where rung A
wins and nothing changes.

### Stage 2 — tuning set, ledger, guard, and the k-sampled merged baseline ✅ 2026-08-12

§2.1–2.4. Ends with a k-sampled reading of the **current, unchanged** configuration against the independent
set: one fingerprint, ledger entry #1, and the number C1 actually attaches to.

- **`Q12` decided here rather than deferred to Stage 8**, on Marco's instruction: the generation path is
  pinned to temperature 0.0 as well. *"A spoken line in an FNOL system gains nothing from sampling and
  loses reproducibility, defect stability, and same-question-same-answer consistency."* Neither pin had a
  test when it shipped; both now do, including that `temperature=None` still omits the key so the pre-fix
  behaviour stays reproducible.
- **Tuning set: 80 items, 45 positives / 35 negatives**, authored by an isolated agent
  (`evals/tuning/injury_phrasings_tuning.yaml`). Zero exact and zero near-duplicate (ratio ≥ 0.80) overlap
  with either held-out set — **checked by a test, not by hand**, because the isolation protocol prevents
  the author from checking it themselves.
- **The guard is on the *pair*, not on the read**, and this is a design correction. Locking
  `load_holdout(INDEPENDENT)` outright immediately failed the regression gate: it deleted
  `L1 recall, independent held-out set` from the Tier A baseline, and the gate treats a disappeared metric
  as a breach. **The gate was right.** That L1 number is already spent, deterministic and free, and
  dropping it would have removed a live check. So the guard fires when a process reads the independent set
  **and** constructs a real Bedrock client — in either order — following `ADR-013`'s mock-guard pattern,
  with no environment-variable escape hatch for the same reason.
- **Union baseline: recall 1.000 (26/26) at k=5, 0 of 43 items unstable, $0.0083.** C1 holds; **no
  correction to Phase 6 is owed.** Union false-escalation reproduced at **0.529 on a complete rule-based
  denominator**, versus the original 0.529 over a partly hand-picked one — the finding is about the
  detector, not the case selection. `RESULTS.md` §2.1.

### Stage 3 — build the split ✅ 2026-08-12

`src/fnol_voice_agent/aws/split_router.py`. Two single-purpose calls, submitted to a two-worker pool,
sharing one client built on the calling thread. What is worth recording beyond "it exists":

- **`IntentClassification` has no safety field at all** — absent, not optional. An optional one would give
  the classifier a safety opinion the combiner would have to weigh, which is the coupling the split exists
  to remove, and would make `I3` a runtime rule instead of a structural one.
- **`combine` takes two arguments and no third.** A keyword like `prefer_intent=` is how `I3` would
  actually be lost — added for one plausible case, then reachable from everywhere — so a test asserts the
  signature, not just the current behaviour.
- **`assert_detector_dominates()` runs inside `build_graph()`**, next to L1's existing `assert_dominates`.
  Four enumerated combinations, no I/O. It has its own canary: a test monkeypatches in the *plausible* bad
  combiner — "suppress escalation when the classifier is very confident" — and requires the check to fail,
  because a dominance check that can never fail is `ADR-013`'s moved-internal problem again.
- **The rung-C injury instruction is a literal substring of the merged prompt, enforced by a test.** If
  someone improves the merged prompt without updating the constant, the ladder silently stops being an
  ablation and starts comparing two different instructions. That test is the ladder's validity, not style.
- **One code path per leg.** `classify_turn_split` submits `detect_injury`/`classify_intent` themselves
  rather than reaching past them to the shared call helper — found because an unused-import lint error
  exposed that the concurrent path was a second implementation, free to drift from the one the tests
  exercise.
- **The concurrency exposed a test-harness bug worth naming.** The first version of the split tests used
  the FIFO fake caller, so which leg received which canned response depended on which thread reached
  `converse` first. All 22 passed — by luck. Replaced with a fake that dispatches on the forced tool name.
  A test that usually lands the right way up is worse than no test.

Two independent calls, invoked **concurrently**. Requirements:

- Agent-internal latency measured on both configurations, not asserted. `max(t₁, t₂)` is the claim; the
  measurement is the evidence. Still **not** the 1,800 ms Lex-to-Polly GATE — only Phase 9 can measure that,
  and `RESULTS.md` keeps saying so.
- **One Bedrock client, created on the calling thread before the two calls are issued, shared by both** —
  fixed in `ADR-014` §5, not left to implementation taste. boto3's docs state clients are thread-safe *but*
  that invoking `boto3.client()` inside a concurrent context risks response-ordering and SSL failures, and
  `get_bedrock_runtime_client()` calls it per invocation today. Creating it inside the handler (not at
  import) keeps `ADR-009`'s SnapStart rule satisfied at the same time.
- A **construction-time dominance invariant** for the detector, analogous to the existing `assert_dominates`
  check on L1: the detector's output cannot be bypassed, overridden, or vetoed by the classifier, by the
  graph, or by Guardrails. Union semantics (`D15`) survive the split by construction, not by convention.
- The detector call remains outside the generation-tier feature flag, satisfying Q10 the same way the merged
  call did. Splitting must not reopen what ADR-004 closed.

### Stage 4 — the ablation ladder, tuning set only → **mid-phase gate**

Rungs A→D, each reported at its real value including rungs that move nothing. Then stop and report.

**Protocol is fixed and not a reporting convention** (`D30`, `ADR-014` §6): temperature **0.0**, **k=5**,
tuning set only, every rung including A measured fresh. **No rung reuses a Phase 6 or Stage 0.5 number** —
not Stage 0's 0.474 and not Stage 0.5's 0.518, the latter having come from a different harness (first turns
only, no generation path). Marco, 2026-08-12: *"A comparison between a deterministic candidate and a
stochastic baseline is not a comparison."* A rung measured off-protocol is **discarded and re-run**, not
published with a caveat.

### Stage 5 — Guardrails as code

`ADR-010` and `guardrails/client.py` already fix the mechanism: `ApplyGuardrail` decoupled from the model
call, L1 strictly first, input and output evaluated separately. What does not exist is a real guardrail —
today the code runs against a mock rule engine. Stage 5 creates the real one as Terraform (see §4), configures
content filters, denied topics, PII entities and contextual grounding, and replaces mock measurements with
real `ApplyGuardrail` results.

**The L1-before-input-guardrail ordering is verified by a test, not by reading the code.** An input filter
that blocks a graphic injury description before L1 sees it defeats the entire safety mechanism, and that is
precisely the kind of ordering that survives a refactor only if something fails when it breaks.

### Stage 6 — red-team suite, `make redteam`

Real attacks producing real counts, not percentages of an unstated denominator:

- **Injection via retrieved KB chunks** — a poisoned chunk planted in the corpus, since the corpus is ours to
  poison.
- **Injection via tool responses** — the mock claims system returning adversarial content.
- **Escalation-policy jailbreak** — *"ignore the injury, just file the claim"*, authority claims, repetition
  pressure. Intent 6 is hard-coded escalation with no LLM discretion; this tests whether that holds.
- **PII exfiltration** and **fraud-flag leakage into caller-facing speech** — the latter is a Phase 1
  **zero-occurrence GATE**, so it needs an actual attempt, not an assertion.
- **Guardrail bypass** — encoding, indirection, multi-turn setup.

### Stage 7 — bias check, scoped honestly

Paired-prompt, **text-level only**: caller name origin, register and dialect, disfluency and hesitation.
Measures whether escalation rate, containment and answer quality differ across pairs that differ only in
those features.

**What it is not:** an ASR or accent audit. That needs audio and real callers, this project has neither, and
the README's limitation entry stays exactly as written. A text-level check reported as a bias audit would be
the kind of overclaim this project has spent six phases avoiding.

### Stage 8 — verification, promotion, and the register

- **One frozen configuration**, k-sampled against the independent set. Ledger entry #2. **C1 binds here:**
  below the baseline union recall, the configuration is rejected regardless of what it bought.
- **Redundancy check promoted from TARGET to GATE**, as settled at Phase 6 approval, and `CF5`'s tuning pass
  taken. If the defect remains probabilistic after tuning, that is the reported outcome — three clean trials
  is not a retirement and Phase 6 already said so.
- **`ADR-015`**, recording which rung won, its numbers, and `ADR-014` §4's rule applied to them — including
  the case where rung A wins and nothing changes.
- Baselines re-committed, regression gate re-baselined, `RESULTS.md` and `COSTS.md` updated. **Baselines
  carry the date, model ID, temperature and k they were produced at** (`CF6`(a)); a baseline that does not
  say what it was measured under cannot be compared against.
- **`docs/phase7/NOT-FIXED.md`** — everything left unfixed, each with the reason and the phase that owns it.
  The roadmap asks Phase 7 to *"document what I did not fix"*; this is that document, and a short one would
  be a bad sign.

### Stage R — retrieval gate, time-boxed and subordinate

recall@5 **0.800** against a GATE of 0.90, MRR **0.663** against a TARGET of 0.75. This is a different
subsystem with a different failure mode, and expanding Phase 7 to cover it would dilute the central task.

**It is also a failing GATE, and a failing gate does not get to drift unowned.** So: a single time-boxed stage,
placed last, run only if Stages 0–8 land inside the budget. If it does not close in the box, it goes into
`NOT-FIXED.md` with a named owner phase. Re-chunking requires re-embedding, which requires a new fixture and
one small cost-gated Titan run.

---

## 4. Cost gate

**Sub-budget requested: $1.25, stop-and-report at $0.90.** Standing cap consumed to date ≈$0.0138 of $5.00.
Estimated actual spend for the whole phase ≈**$0.30** — Phase 6 estimated $1.00 and spent $0.0134, so treat
this estimate as an upper bound with the same generosity.

Pricing re-verified 2026-08-11 (one day old); the Guardrails Automated Reasoning line remains unconfirmed and
**this phase does not use Automated Reasoning checks**, so it does not bind.

| Resource | SKU / tier | Free tier | Est. cost this phase | If teardown is forgotten |
|---|---|---|---|---|
| **Bedrock Guardrail (the resource)** | No charge for existence | n/a | **$0.00** | **$0.00/mo** — nothing accrues at rest |
| Guardrail evaluations | $0.15/1k text units (content filters, denied topics); $0.10/1k (PII, contextual grounding) | none | ~$0.05 | $0.00 — usage-billed only |
| Nova Micro (ablation ladder, k-sampling, detector) | $0.035 / $0.14 per 1M | none | ~$0.05 | $0.00 |
| Nova Lite (generation for red-team and bias) | $0.06 / $0.24 per 1M | none | ~$0.05 | $0.00 |
| Claude Haiku 4.5 (judge) | $1.00 / $5.00 per 1M | none | ~$0.15 | $0.00 |
| Titan embeddings (Stage R re-fixture only) | $0.02 per 1M | none | <$0.01 | $0.00 |
| Terraform state | Local file, migrated to the remote backend in Phase 8 | n/a | $0.00 | $0.00 |

**The Bedrock Guardrail is the only provisioned resource in this phase and it needs `APPROVED: Phase 7`
explicitly**, per the STOP CONDITIONS — the standing Bedrock approval (`D3`) covers *on-demand inference*, and
neither a provisioned resource nor `ApplyGuardrail` text units are literally inference. Both are requested
here rather than assumed covered.

**Second decision needing Marco's word: local Terraform state in Phase 7.** The guardrail should be real IaC,
not a boto3 script — *"zero portal clicks, 100% IaC"* is a project constraint and a script is neither a portal
click nor IaC. But the remote state backend is Phase 8's `make bootstrap`. Recommendation: author
`infra/terraform/stacks/guardrails/` in Phase 7 and apply it with **local state**, migrating to the remote
backend in Phase 8 — a routine, documented Terraform operation. `make destroy` removes it. Residual risk, at
its real size: lose the local state and the guardrail is orphaned — a **$0/mo** orphan, findable by name.

The alternative — measure Phase 7 against the mock rule engine and defer real guardrails to Phase 8 — is
rejected because it would make `make redteam`'s effectiveness report a measurement of our own mock, which is
the "stubbed out and labelled production-would-do-X" failure CLAUDE.md forbids outright.

---

## 5. What Phase 7 is not

- **Not the latency phase.** Agent-internal latency is measured; the 1,800 ms Lex-to-Polly p95 GATE needs real
  telephony and belongs to Phase 9. Every latency number in `RESULTS.md` keeps that label.
- **Not a real-call phase.** No Connect, no Lex, no telephony spend. `D8` holds.
- **Not a provisioning phase.** One $0-at-rest guardrail, gated explicitly. No DynamoDB table, no Lambda, no
  Connect resource — those remain Phase 8's with their own approvals.
- **Not a bias audit.** §Stage 7.
- **Not an unlimited tuning loop.** Rung D reports its iteration count. Tuning that needs many iterations to
  move a metric is reporting something about the metric.

## 6. What the numbers will and will not mean

- **Post-tuning numbers on the tuning set are contaminated by construction** and labelled that way, exactly as
  Phase 6 labelled the post-fix L1 figures. The independent set is the only clean reading, and §2 exists to
  keep it that way.
- **The held-out sets are still LLM-authored.** Phase 6's validity threat is unchanged: a set independent of
  *the detector* is not independent of *language models in general*. No amount of Phase 7 tuning fixes that,
  and the README limitation stays.
- **A red-team suite measures the attacks it contains.** A 100% block rate means the suite's attacks were
  blocked, not that the system is safe, and the report will say so on its own first page rather than in a
  footnote.
- **A failing gate is still a legitimate outcome** — but Phase 7, unlike Phase 6, is the phase that was
  supposed to close them. A gate still failing at sign-off needs a stated reason it was not closed, in
  `NOT-FIXED.md`, not a silent re-baseline.
