# ADR-014: The merged router+L2 call loses its default — the architecture is decided by a pre-committed rule over an ablation ladder, and five invariants bind whichever rung wins

**Status:** Accepted (Phase 7). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-12
**Supersedes:** `ADR-004` §1 (the merge of routing and L2 safety classification into one call) — **and only
that.** `ADR-004` §2 (feature-flagged generation tier), its Q10 separation, its forced-tool-use mechanism and
its fixed-cheap-tier rule for the safety path all remain in force and are re-asserted as invariants below.

---

## Context

### What is established, without any new measurement

Phase 6 published three failing metrics and Phase 7 Stage 0 showed they are one finding:

| | intent = `InjuryEscalation` | other intent |
|---|---|---|
| `safety_flag` true | **27** | 1 |
| `safety_flag` false | 3 | 47 |

Given `safety_flag`, the intent is `InjuryEscalation` 27 times out of 28; without it, 3 times out of 50.
Fisher exact **p < 10⁻⁸** (`scripts/stage0_forensics.py`, `RESULTS.md` §3.2). The two fields are very nearly
the same decision wearing two names — which is what a model producing **one structured object** does: it
makes the object's fields mutually consistent. The recall bias placed deliberately on `safety_flag`
(*"when in doubt, true"*, verbatim in the system prompt) therefore has a direct path into `intent`.

The consequence is measured, not inferred: union false-escalation **0.529** against a TARGET of ≤ 0.10
(`D24`), intent macro-F1 **0.623** against a GATE of ≥ 0.90, out-of-scope detection **0.200** against 0.85.

Stage 0's refutation condition — *"if the misclassifications are not the same turns as the false
escalations, tell me before building rungs"* — **was not met.** They are the same turns.

### The gap in `ADR-004`'s alternatives table, which is why this ADR exists at all

`ADR-004` rejected **"separate *sequential* calls for routing and L2"** with the deciding factor *"two
round-trips against the same latency budget for no capability gain over one merged, schema-forced call."*

It never evaluated **separate *parallel* calls** — and `SUCCESS-METRICS.md` §2, written in Phase 1 and
therefore available when ADR-004 was drafted, had already specified L2 as a *"single-purpose binary 'injury
indicated?' call"* whose *"latency sits inside the 1,800 ms budget as a parallel call, not a serial one."*

**The latency argument for merging holds only against an alternative the specification never asked for.**
Two concurrent Nova Micro calls cost `max(t₁, t₂)`, not `t₁ + t₂`. This does not make the merge wrong; it
makes ADR-004's *stated deciding factor* void, which is a different and narrower claim. An accepted ADR
carries a presumption in its favour. **This one no longer does, because the reason recorded for it was
never tested against the design the spec actually named.**

`ADR-004` also wrote its own exit, and it is worth quoting because it means this is a planned path rather
than a reversal: *"If Phase 6 ever needs the router and the safety classifier to run on different models …
the merged-call design would need to be split apart — recorded as a design cost of the current
optimization, to be paid only if evidence requires it."*

### What is *not* established, and why this ADR does not simply decide the split

Marco's instruction names unmerging as the **leading hypothesis**, not the conclusion. Two explanations fit
every number above equally well and no measurement in hand separates them:

1. **The merge.** One call cannot be simultaneously paranoid and discriminating, because its output is one
   coherent object.
2. **The label space.** The classifier has an injury-shaped intent in its output enum to fall into. A
   recall-biased instruction anywhere in the prompt makes that label attractive whether or not the safety
   verdict shares the call.

Explanation 2 is repaired by deleting one enum member. Explanation 1 requires a second concurrent Bedrock
call, a dominance invariant, and a new failure mode. **Writing "we split the call" into an accepted ADR
before running the experiment that separates these would make the experiment ceremonial** — the ladder
would exist to confirm a decision already recorded, which is the failure mode this project has now
corrected three times in one phase (`D24`, `D27`, `D29`).

So this ADR decides what the evidence in hand actually supports, and pre-commits everything else.

### One measurement constraint that is not negotiable, from `D27`/`D30`

Through Phase 6 the router sampled at **temperature 0.7** (Nova's default; no `temperature` was sent). Five
runs × 78 turns put the macro-F1 spread at **0.063** and found **13 of 78 turns whose `safety_flag` verdict
changed between identical runs.** At 0.0 the same measurement gives sd 0.000 over 390 calls.

**A comparison between a deterministic candidate and a stochastic baseline is not a comparison.** Every rung
below is measured at temperature 0.0, k=5, identical protocol, or it is not measured.

---

## Decision

### 1. `ADR-004` §1's merge is withdrawn as the default architecture

It is not rejected — it remains rung A and may still win. It no longer holds the position of "the accepted
design that a challenger must displace." The burden is symmetric from here: **every rung, including the
current production configuration, must earn its place against the pre-committed rule in §4.**

### 2. The replacement is chosen by the ablation ladder, under a rule fixed before the numbers exist

| Rung | Configuration | Isolates |
|---|---|---|
| **A** | Current merged call, unchanged | Baseline on the tuning set at temperature 0.0. Without it every later delta is confounded by the change of set *and* the change of temperature |
| **B** | Merged call, `InjuryEscalation` removed from the **classifier's output enum** | **Label-space coupling.** One-line change |
| **C** | Split into two **concurrent** calls; injury instruction copied **verbatim**, no rewording | **The merge itself.** Same words, two prompts |
| **D** | Split + detector prompt revised | The only rung where tuning happens. Reports its iteration count |

Rung B does **not** remove an intent from the system. CLAUDE.md's six intents, the golden labels and the
escalation path are unchanged; `D12` already holds that injury detection is *"a deterministic pre-node, not
an intent classified by the model"*, and rung B makes the implementation match a Phase 1 decision.

### 3. Five invariants bind whichever rung wins

These are the parts of `ADR-004` that were right, plus one the split makes newly necessary. A configuration
that violates any of them is not a candidate, regardless of its metrics.

| # | Invariant | Enforced by |
|---|---|---|
| **I1** | **No code path from the generation-tier feature flag to the safety call.** `ADR-004`/Q10, satisfied structurally rather than by convention | Existing test in `tests/unit/test_bedrock_router.py`; must be extended to the detector call, not merely inherited |
| **I2** | **The safety verdict is a schema-required field of a forced tool-use call.** A missing verdict raises; it is never defaulted, inferred, or filled in downstream | `TurnClassification` / the detector's tool spec. The pre-registration rejected a fail-safe default **in advance** and that rejection carries forward |
| **I3** | **The detector's output cannot be bypassed, overridden or vetoed** — not by the classifier, not by the graph, not by Guardrails. Union semantics (`D15`) survive by construction | A construction-time dominance check, the analogue of the existing `assert_dominates(builder, "l1_safety_check")` in `agents/graph.py` |
| **I4** | **L1 runs first, on raw input, unconditionally** (`ADR-010`). The split adds a node; it does not reorder the pipeline | `assert_dominates`, plus Stage 5's ordering test |
| **I5** | **The safety path stays fixed to Nova Micro.** It is not a tier to tune when a metric disappoints | `ROUTER_MODEL_ID`, no flag reachable from the detector |

**I3 is the one the split creates.** Merged, the safety verdict was structurally inseparable from the
routing decision — an ugly property that happened to make bypass impossible. Two calls make bypass
expressible for the first time: a graph edge could route on `intent` and never consult the detector. The
invariant has to be re-established mechanically, at construction time, because the property the merge gave
away for free is exactly the one the system exists to guarantee.

### 4. The decision rule, pre-committed

Written before any rung has run, for the same reason the dropped-`safety_flag` threshold was written before
its number was opened: otherwise the rule is shaped by the result.

**Scoring.** Intent macro-F1 is scored on the system's **effective** intent (detector fires → effective
intent is `InjuryEscalation`), because that is the system's actual behaviour. The classifier's **raw**
output is reported alongside it, so the split cannot be credited by a scoring convention.

**Admissibility — a rung is a candidate only if:**

- **C1.** Union escalation recall is **not below rung A's k-sampled baseline** on the same protocol. Not
  tradeable, per Marco. A dropped safety verdict is a recall MISS, not a pass (pre-registration §2).
- **I1–I5** all hold.

**Selection, applied in order:**

1. **False-escalation must improve materially** — by **≥ 2 sd** of that metric as measured at k=5 on the
   tuning set. Not a fixed number of points: this project has already been burned by a fixed tolerance
   against an unmeasured variance (`D31`), and setting one here would repeat it in the same phase that
   found it.
2. **Intent macro-F1 must not degrade materially** by the same ≥ 2 sd standard.
3. **Ties go to the simplest configuration: B beats C beats D.** Recorded now because at the moment the
   numbers land, the split will be the interesting result and the enum deletion will be the boring one.
   Boring wins ties.

**Pre-committed readings of specific outcomes:**

| Outcome | Reading | Action |
|---|---|---|
| **B recovers macro-F1; C adds nothing over B** | The label space was the defect. **The merge was innocent** | **Ship B. Do not ship the split.** ADR-015 records the merge as vindicated on a narrower basis than ADR-004 claimed |
| **C improves over B on false-escalation** | The merge itself was a real cause | Proceed to D |
| **C ≈ A on false-escalation** | The injury *instruction* is the cause and neither the merge nor the label space is | **Report as a refutation** of §1's hypothesis. `NOT-FIXED.md` gains an entry. Phase 7 does not quietly try a fifth thing until something moves |
| **Nothing reaches 2 sd** | The defect is not addressed by any configuration on this ladder | Report the ladder at its real values, including the rungs that moved nothing, and stop |

**Rung D is capped at 3 prompt revisions.** Then it stops and reports whatever it has. Tuning that needs
many iterations to move a metric is reporting something about the metric.

### 5. Latency and cost, analysed rather than asserted

**Cost.** From this project's own bill: 34 Nova Micro classification calls cost $0.001326 (`RESULTS.md` §7),
i.e. **$0.000039 per call**. The split adds one call per turn: **+$0.0003 per 8-turn conversation** against
a telephony marginal cost of $0.15–0.20. That is **0.2% of a conversation's cost.** Consistent with
`ADR-004`'s own finding that Bedrock is noise next to telephony, cost does not decide this and no cost
argument will be made for or against the split.

**Latency.** The claim is `max(t₁, t₂)`, not `t₁ + t₂`. It is a hypothesis and Stage 3 measures it —
agent-internal only, never presented against the 1,800 ms Lex-to-Polly GATE, which needs telephony this
phase does not touch (Phase 9 owns it).

**Pre-committed fallback:** if measured concurrent latency lands materially closer to the sum than to the
max, C and D lose the argument that distinguishes them from sequential calls — the alternative `ADR-004`
rejected on grounds that would then be correct — and **B becomes the preferred outcome even if C matches it
on quality.**

**One verified implementation constraint.** boto3's own documentation states that clients *"are generally
thread-safe"* but that **"invoking `boto3.client()` inside of a concurrent context may result in response
ordering issues or interpreter failures from underlying SSL modules."** Today
`get_bedrock_runtime_client()` calls `boto3.client("bedrock-runtime", …)` — the shared-default-session
alias — and returns a fresh caller per invocation. Calling it from inside each of two concurrent branches
is precisely the documented hazard.

**The construction is therefore fixed here, not left to Stage 3:** one client is created on the calling
thread **before** the two calls are issued, and that single client is shared by both. This satisfies
`ADR-009`'s SnapStart rule at the same time — the client is still created inside the handler rather than at
module import — so the two constraints are compatible and neither is being traded away.

### 6. Measurement protocol, fixed (`D30`)

| | Fixed value |
|---|---|
| Temperature | **0.0** on every rung including A. No rung reuses a Phase 6 or Stage 0 number |
| Samples | **k = 5** per item; an item missed on **any** sample counts as a miss (safety-conservative, per `SUCCESS-METRICS.md` §2's *"recall wins any conflict"*) |
| Corpus | The Phase 7 **tuning set** only, frozen before rung A runs. The independent set is untouched until Stage 8 |
| Comparison | Within the ladder only. A rung measured off-protocol is **discarded and re-run**, not caveated |
| Ledger | Every independent-set run appends a config fingerprint to `evals/holdout_ledger.json`; the count of distinct fingerprints is published |

---

## Consequences

**Positive:**

- The architectural question is settled by an experiment whose outcome can embarrass the leading
  hypothesis, and the rule for reading it exists before the numbers do.
- `I3` converts a property the merge provided accidentally into one the system asserts deliberately — a
  net gain in safety guarantees even if rung A ultimately wins, because the check can be added either way.
- Failure isolation improves under C/D: a throttle or malformed response on the classifier no longer takes
  the safety verdict down with it, which was `ADR-004`'s explicitly accepted residual risk.

**Negative / accepted residual risk:**

- **Two concurrent Bedrock calls double per-turn exposure to on-demand throttling.** The failures become
  independent rather than shared — better for safety, worse for availability. Not measured this phase; a
  retry/backoff policy on the detector call is `NOT-FIXED.md` material unless Stage 3 finds it trivial.
- **Bypass becomes expressible.** Mitigated by `I3`, which is a construction-time check and therefore only
  as good as its coverage. A graph edge added later without re-running the check is the realistic failure
  mode, and it is why the check belongs in `build_graph()` rather than in a test.
- **This ADR does not name the winning configuration**, which is unusual for a decision record and is the
  cost of not pre-deciding the experiment. It is paid by requiring `ADR-015` (below) rather than by leaving
  the outcome in a results document.

**Required follow-up, not optional:** **`ADR-015` records which rung won, its numbers, and the rule from §4
applied to them** — including the case where rung A wins and nothing changes. Without it this ADR has no
terminal state, and a decision procedure with no recorded outcome is worse than no ADR at all.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Keep the merged call; tune the shared prompt | Rejected | The coupling is structural (27/28 vs 3/50, p < 10⁻⁸). Prompt wording is what rung D tests *after* the structural question is answered; doing it first would confound both |
| Decide the split now and use the ladder to confirm it | **Rejected — and it was the tempting option** | Two explanations fit the data equally well and one is a one-line change. An experiment run to confirm a recorded decision is not evidence |
| Split into two **sequential** calls | Rejected | `ADR-004`'s original objection stands and is correct: two round-trips against the same latency budget for no capability gain |
| Drop L2; rely on L1 + L3 | Rejected | Violates `D15` and C1. L1 misses ~73% of indirect injury phrasing; the union recall guarantee is L2's contribution |
| Make `safety_flag` optional with a fail-safe default of `true` | **Rejected in advance**, before the dropped-field number was opened | Converts a loud failure into a silent one — the exact property `ADR-004`'s required field was built to obtain — and makes false escalation worse. Recorded in the pre-registration so it could not be reached for later as the path of least resistance |
| A larger model for the merged call | Rejected | Does not address a structural coupling, costs latency on the one path that runs every turn, and violates `I5` |
| **Withdraw the merge's default status; decide by pre-committed rule over rungs A–D; bind I1–I5 regardless** | **Chosen** | Decides exactly what the evidence supports, and fixes in advance the parts most likely to be bent by a result — the reading rule, the tie-break, the refutation condition and the protocol |

## Sources

- `RESULTS.md` §3.2 (item-level merge evidence), §3.3 (temperature), §0.1 (which numbers are single draws)
- `scripts/stage0_forensics.py`, `scripts/measure_temperature_variance.py`; raw data in `evals/baselines/`
- `docs/phase7/PRE-REGISTRATION-dropped-safety-flag.md` §2, §5
- `docs/phase1/SUCCESS-METRICS.md` §2 (L2 specified as a parallel single-purpose call), §9 + addendum
- `PROJECT_STATE.md` `D12`, `D15`, `D24`, `D25`, `D27`, `D29`, `D30`, `D31`, `CF6`
- <https://docs.aws.amazon.com/boto3/latest/guide/clients.html> — client thread-safety and the
  `boto3.client()`-in-a-concurrent-context hazard, fetched 2026-08-12
