# Success Metrics — Phase 1

Defined **before** anything is built, so tuning cannot quietly redefine success.

## How to read this document

Every row is labelled with a **kind**, and the distinction is load-bearing:

| Kind | Meaning |
|---|---|
| **GATE** | A threshold that fails CI. Non-negotiable. A PR that breaches it does not merge |
| **TARGET** | An aspiration for this prototype. Missing it is reported honestly, not hidden or quietly relaxed |
| **OBSERVED** | Measured and reported with **no threshold**. Recording a distribution is the point |

**Every threshold below is a target or gate that this project sets for itself. None is a measured result, and
none is an industry benchmark.** Nothing here may be presented as achieved performance until `make eval` has
produced it. Per constraint 13, unmeasured numbers stay labelled as unmeasured.

**Standing caveat:** LLM-as-judge scores are **proxies, never ground truth**. Every judge-scored metric is
accompanied by a human-reviewed sample, and a judge score is never the sole evidence for a claim about
quality.

---

## 1 · The decision rule

The system is "working" when **all four** hold:

1. Every **GATE** passes.
2. **Task success rate ≥ 80%** across the golden set.
3. **Safety-critical escalation recall = 100%.** No exceptions, no rounding, no "one flaky case".
4. Cost and latency are reported alongside quality on the same run — **a quality gain that doubles cost or latency is not automatically a win.**

If gates pass but targets are missed, that is reported as a partially working system with named weaknesses.
If a gate fails, the system is not working, regardless of how good the other numbers look.

---

## 2 · Safety metrics — the non-negotiable ones

| Metric | Kind | Threshold | Measurement |
|---|---|---|---|
| **Safety-critical escalation recall, labelled set** | **GATE** | **100%** | Of golden conversations containing a KABCO **K** or **A** indication, the fraction where escalation fired within one turn. Denominator includes adversarial phrasings and mid-slot-filling mentions. **Enforceable because detection is deterministic — see below for the precise claim** |
| **Safety-critical escalation recall, held-out novel phrasings** | OBSERVED → TARGET once baselined | **No threshold at first.** Reported as a number, never rounded up, never omitted | A held-out set of injury phrasings **not** used to build either detector, refreshed each red-team cycle. This is the honest measure of real-world recall |
| Escalation latency | **GATE** | ≤ 1 turn | Turns between the trigger utterance and transfer initiation |
| Safety guidance given before transfer | **GATE** | 100% | The 911 instruction precedes the transfer on every route-1 escalation |
| Agent-request honoured | **GATE** | 100% | Every "agent"/"human" barge-in reaches a human without gatekeeping, from any state |
| Silent partial write (contact update) | **GATE** | **0 occurrences** | Post-condition assertion: the record matches what was confirmed, or is unchanged. Any partial write is a critical defect |
| Fraud flag in caller-facing speech | **GATE** | **0 occurrences** | Response text asserted free of flag content |
| Recording enabled in any contact flow | **GATE** | **0 occurrences** | Static check on flow JSON (constraint 18) |
| Injury severity discrimination (K/A escalate; B/C flag only) | TARGET | ≥ 90% | Deliberately separate from recall — the system must not escalate every scraped knee, but recall wins any conflict |

**Why recall is a gate and precision is not:** a wasted transfer costs one human minute. A missed injury
escalation is the failure this system must not have. The bias is toward over-escalation, and
false-escalation rate (§4) exists to keep that bias from becoming useless behaviour — not to trade against
recall.

### Why the recall gate is split in two

The original single "100% recall" gate was **not achievable and therefore dishonest**. No detector achieves
100% recall against unbounded natural language; a caller can always say something like *"my neck feels
funny"* that no rule anticipated. A gate everyone knows is unachievable gets quietly excepted the first time
it fails, which is worse than not having it.

The split fixes this without weakening the commitment:

- **On the labelled safety set, 100% is an enforceable gate, not a guaranteed property.** Detection is a deterministic pre-node (D12), which means a failure is **discoverable and fixable as a code defect** — a missing lexicon entry, a regex that doesn't match a phrasing already in the labelled set — rather than a stochastic model-quality shortfall that tuning might or might not resolve. That is what "achievable by construction" should have meant and didn't: determinism makes the gate *debuggable to zero*, on a *closed, known set*, through a normal fix-and-re-run cycle. It does not make the mechanism infallible, and it says nothing about phrasings outside that set — an incomplete lexicon can still miss a labelled case on first write, and *that miss is exactly what CI is supposed to catch*.
- **On held-out novel phrasings, the number is reported, not gated.** A threshold would be a guess, and a guessed threshold on a safety metric is exactly the kind of invented number constraint 13 forbids. It becomes a TARGET only once a real baseline exists, and it is **never omitted from a report because it looks bad** — that is the whole reason it is measured separately.

**This is the honest framing, not a relaxation.** The labelled gate got stricter (a failure is now a defect,
not a tuning problem) and a previously hidden weakness became a standing reported metric.

### The layered detector is an architectural requirement, not a mitigation

Committed now rather than deferred, because a single detector demonstrably cannot carry this:

| Layer | Mechanism | Purpose |
|---|---|---|
| **L1** | Deterministic lexical/pattern pre-node, runs **before the model sees the input** and before Guardrails input filtering | High precision, near-zero latency and cost, fully testable. Carries the labelled gate |
| **L2** | Cheap dedicated classifier (Nova Micro tier), single-purpose binary "injury indicated?" call on every turn | Catches phrasings L1 has no rule for. Recall-biased: **an ambiguous case escalates** |
| **L3** | Caller-request route — the hard "agent" barge-in, always available | The caller's own override when both detectors miss |

**Union semantics: any layer firing escalates.** No layer can veto another, and nothing downstream —
including the main graph and Guardrails — can suppress the result.

L2's cost is deliberate and small: one Nova Micro classification per turn is a fraction of a cent per
conversation against telephony's ~92% share of marginal cost. **Paying it is not a budget question.** L2's
latency sits inside the 1,800 ms budget as a parallel call, not a serial one, and Phase 9 measures that
rather than assuming it.

Consequences that now bind Phase 2: **L1 must precede Guardrails input filtering** (an input filter blocking a
graphic injury description before L1 sees it defeats the whole mechanism — this becomes its own ADR), and L2's
per-turn invocation must survive the model-tier feature flag, i.e. **it cannot be switched off by a config
change** that was only meant to change the generation tier.

---

## 3 · Component metrics

| Metric | Kind | Threshold | Measurement |
|---|---|---|---|
| Intent classification accuracy (macro-F1) | GATE | ≥ 0.90 | Across the six intents plus out-of-scope, on the golden set |
| Out-of-scope detection rate | TARGET | ≥ 0.85 | Correctly routed to capability escalation rather than forced into an intent |
| Slot F1 (`FileAutoClaim`) | GATE | ≥ 0.85 | Per-slot exact/normalised match, macro-averaged; the 11-slot intent is the hard case |
| `loss_datetime` parse accuracy | TARGET | ≥ 0.90 | Fuzzy expressions ("yesterday about 5:30", "last Tuesday evening") resolved to the correct instant |
| Identifier capture accuracy | TARGET | ≥ 0.95 | Policy/claim number captured correctly, including via DTMF fallback |
| Retrieval recall@5 | GATE | ≥ 0.90 | Gold passage present in top 5 |
| Retrieval MRR | TARGET | ≥ 0.75 | |
| **Groundedness / faithfulness** | **GATE** | **≥ 0.95** | Every claim in a coverage answer supported by a retrieved passage. **The primary target for intent 3** |
| Answer relevance | TARGET | ≥ 0.85 | Judge-scored, human-sampled |
| Abstention correctness | TARGET | ≥ 0.90 | Out-of-corpus questions declined rather than answered. **Correct abstention scores as success** |
| Tool-selection accuracy | GATE | ≥ 0.95 | Right tool, right arguments, on the golden set |
| Compound-case correctness (intent 4) | GATE | ≥ 0.90 | **Both** policy retrieval and claim-state tool consulted, and the conjunction reasoned correctly. Answering from the policy alone fails **even when the coverage statement is true** |

---

## 4 · Conversation metrics

| Metric | Kind | Threshold | Measurement |
|---|---|---|---|
| **Task success rate** | **GATE** | **≥ 0.80** | Per-intent success criteria from `PROBLEM-FRAMING.md`, weighted equally across intents |
| **Appropriate containment** | TARGET | ≥ 0.65 | Resolved without transfer ÷ calls where transfer was **not** warranted. **Mandatory escalations (routes 1–2) are excluded from the denominator entirely** |
| Escalation appropriateness | GATE | ≥ 0.90 | Correct decisions ÷ all escalation decisions, scored **in both directions** |
| False-escalation rate | TARGET | ≤ 0.10 | Transferred when the agent could have resolved it. Exists so safety cannot be bought by transferring everything |
| Context-handover completeness | TARGET | ≥ 0.95 | Slots captured before transfer are present in the handover payload. **A caller who repeats themselves to the human has been failed even if the transfer was correct** |
| Turns to completion — `FileAutoClaim` | TARGET | median ≤ 10 | Excluding escalated calls |
| Turns to completion — other intents | TARGET | median ≤ 4 | |
| Repair success rate | TARGET | ≥ 0.80 | Recovery after a no-match, no-input, or misrecognition |
| Repeat-question rate | TARGET | ≤ 0.05 | Agent re-asks something the caller already answered — the clearest signal that state tracking is broken |

### Why containment is decomposed

Naive containment (calls not transferred ÷ total) rewards refusing to escalate, which is a safety hazard.
Three structural guards:

1. **Mandatory escalations are outside the denominator.** A correctly escalated injury call is a success; counting it against containment would create pressure to suppress the behaviour the system exists to guarantee.
2. **Escalation appropriateness is scored in both directions**, so neither over- nor under-escalating is free.
3. **Safety-critical recall is a separate 100% gate** that no containment number can offset.

---

## 5 · Latency metrics

| Metric | Kind | Threshold | Measurement |
|---|---|---|---|
| **Turn latency p95** | **GATE** | **≤ 1,800 ms** | Lex STT completion → Polly audio stream start (constraint 14) |
| Turn latency p50 | TARGET | ≤ 900 ms | |
| Cold-start turn latency p95 | TARGET | ≤ 1,800 ms | Measured explicitly in Phase 9. **The hard case on a low-traffic demo line** |
| Interim-filler trigger correctness | TARGET | ≥ 0.95 | A filler plays whenever a tool call is projected to exceed 1,000 ms |
| Time to first audio after answer | TARGET | ≤ 1,000 ms | Greeting responsiveness |
| Dead-air incidents > 3 s | GATE | **0** | The failure mode repo 1 shipped by design |

---

## 6 · Cost metrics

| Metric | Kind | Threshold | Measurement |
|---|---|---|---|
| **Monthly spend** | **GATE** | **≤ $25.00** | Hard ceiling. Budget alarm from the first provisioning phase |
| Cost per conversation | TARGET | ≤ $0.25 | Reported on every eval run alongside quality |
| Bedrock spend, Phases 3–7 | GATE | ≤ $5.00 cumulative | Standing approval cap, logged per run in `COSTS.md` |
| Footprint after `make destroy` | GATE | **$0.00** | Excluding the protected DID |
| Bedrock cost share of marginal cost | OBSERVED | — | Expected to be small: telephony is ~92% of the ~$0.20/conversation estimate. Worth reporting precisely because it inverts the usual intuition |
| Tokens per conversation, by tier | OBSERVED | — | Router effectiveness |
| Real calls placed per month | OBSERVED | — | Simulator-first is the primary cost control; ~100 real calls would nearly exhaust the budget |

---

## 7 · Reliability and quality metrics

| Metric | Kind | Threshold | Measurement |
|---|---|---|---|
| Unhandled error rate | GATE | ≤ 0.01 | Turns ending in an exception or fallback-of-last-resort |
| Unit test coverage, agent core | GATE | ≥ 0.80 | Constraint from Phase 9 |
| MCP tool contract tests | GATE | 100% pass | Every tool |
| Smoke suite post-deploy | GATE | exit 0 | Non-zero fails the deploy |
| State durability across turns | GATE | 100% | Checkpoint survives Lambda cold start mid-conversation |

---

## 8 · Observed-only measures

Reported with no threshold. Thresholds here would be guesses, and their **distributions** are the useful
artifact — several become Phase 11 SLO baselines and Phase 13 drift signals.

ASR confidence distribution · intent confidence distribution · NLU n-best margin (top-1 vs top-2) ·
guardrail intervention rate by category · retrieval score distribution · reranker contribution to recall
(**measure whether it earns its latency**) · barge-in frequency · DTMF fallback usage rate · caller
sentiment proxy · intent distribution over time (drift signal) · turn count distribution · abandonment rate ·
model-tier selection distribution.

---

## 9 · The regression gate

CI fails a PR that breaches **any GATE**, or that degrades **any TARGET by more than 3 percentage points**
against the current baseline, on the golden set of ≥60 labelled conversations.

Deliberate properties:

- **Cost and latency are reported on the same run as quality.** A change improving groundedness by 1 point while doubling cost per conversation is surfaced as a regression to be argued about, not merged silently.
- **Baselines are committed artifacts**, updated only by an explicit, reviewed commit — so the baseline cannot drift downward one PR at a time.
- **The gate is demonstrated to work** by opening a deliberately bad PR and showing it blocked (Definition of Done item 6). An untested gate is not a gate.
- **Judge-scored metrics carry a human-reviewed sample.** A judge regression is investigated before it is trusted, in either direction.

> ### Addendum, 2026-08-12 — the 3-point rule is insufficient for model-dependent metrics
>
> Written in Phase 1, before any measurement existed. Phase 7 measured the variance the rule has to work
> against and it is **larger than the tolerance**: five identical runs of the intent harness at the shipped
> sampling temperature spread macro-F1 by 0.063, and Phase 6's published figure sits ~4.3 sd outside the
> distribution five later runs describe, for reasons this project cannot explain from the client side
> (`PROJECT_STATE.md` `D29`).
>
> Two failure modes follow, and the second is the dangerous one:
>
> 1. A 3-point tolerance against a metric that moves 6 points on identical input **fires on luck**.
> 2. If the serving side moves under a committed baseline, a real regression **hides inside the drift** —
>    the gate stays green while the system gets worse.
>
> **The rule above stands unchanged for deterministic metrics** — L1 recall, retrieval, corpus checks, cost
> — which is most of the per-PR gate and the part with teeth today. For model-dependent metrics it is
> **superseded by `CF6`**, which requires baselines stamped with date/model/temperature/k, a **same-run
> control** re-measuring the unchanged configuration in the same CI job, and tolerances expressed in
> measured standard deviations rather than fixed points. Phase 10 owns the implementation.
>
> Recorded here rather than only in `PROJECT_STATE.md` because this is the document the gate is built
> from, and a constraint discovered after the spec was written is worth exactly nothing if it lives
> somewhere the implementer will not look.
>
> **Implemented 2026-08-14, Phase 10, `evals/regression.py`.** `CF6`(a) (provenance + max-age) was built
> ahead of schedule at Phase 7 Stage 8 and is exercised on every gate run via `load_baseline()`. `CF6`(b)
> (`same_run_compare`) and `CF6`(c) (`sd_tolerance`, backed by `load_measured_sd`'s read of the real,
> committed `temperature_variance_20260812.json`) are built and unit-tested
> (`tests/unit/test_cf6_gate.py`), and demonstrated against real committed data by
> `scripts/demonstrate_cf6_gate.py`, wired into `fnol-eval-gate.yml` as a $0 offline step run on every PR.
> **Not yet true of this repository:** no Tier B metric is actually gated on a live PR run — that still
> requires AWS credentials in CI, which this workflow deliberately does not carry, for the same cost/
> flakiness reason stated at the top of this section. What is proven is that the mechanism is correct
> against real data (it reproduces the exact drift measured above — a real ~0.105 macro-F1 gap between
> the committed Tier B baseline and every deterministic re-run since — and reads it as drift, not a
> regression, while still catching a synthetic regression injected on top of the same real reading) and
> that a future PR which does wire in a live Tier B measurement gets this comparison, not `compare()`'s
> flat tolerance, for free.

### Anti-gaming notes

Recorded now because these are the specific ways this metric set could be satisfied while the system got worse:

| Gaming route | Counter |
|---|---|
| Suppress escalations to raise containment | Safety recall is a 100% gate; mandatory escalations excluded from the containment denominator |
| Escalate everything to raise safety recall | False-escalation rate and appropriate containment are tracked |
| Abstain on everything to raise groundedness | Abstention correctness and task success rate both fall |
| Shorten answers to cut cost and latency | Answer relevance and task success rate both fall |
| Narrow the golden set to easy cases | The set requires happy paths, edge cases, ambiguity, adversarial prompts and out-of-scope, with per-category minimums; changes to it are reviewed as code |
| Tune the judge prompt until scores rise | Human-reviewed sample accompanies every judge metric; judge prompt changes are reviewed and versioned |

---

## 10 · Not yet measurable

Stated plainly rather than left as an implied capability:

- **Bias across name, accent and dialect variation** — Phase 7 designs the check; a real assessment needs speaker diversity this project does not have. The gap will be reported, not papered over.
- **Accessibility for callers with speech differences or hearing loss** — a genuine equity gap in a voice-only system, with no audit planned.
- **Anything requiring real callers** — real-world containment, satisfaction and abandonment cannot be established from author-generated traffic, and no number from this project should be read as predicting them.
- **Behaviour at scale** — every figure here is at demo volume. Phase 13 documents what would change at 100×.
