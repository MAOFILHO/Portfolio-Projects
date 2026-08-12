# Phase 6 Build Plan — Eval Harness

Same shape as `docs/phase5/BUILD-PLAN.md`, for the same reason: the build order has to make a mid-phase gate
possible, and the cost gate has to name which specific steps touch real AWS. Phase 6 needs both more than
Phase 5 did — it is **the first phase that spends a non-trivial share of the $5 standing cap**, and it is the
phase whose output is a set of numbers, which makes it the phase where a shortcut is hardest to see later.

Roadmap line: *"Eval harness **before tuning**: ≥60 golden conversations, component + conversation evals,
judge + human sample, CI regression gate, cost/latency alongside quality."* Phase 1's `SUCCESS-METRICS.md`
already fixed **what** is measured, which kind each metric is (GATE / TARGET / OBSERVED) and the anti-gaming
rules. Phase 6 does not get to redefine any of that; it builds the thing that produces the numbers.

---

## 0. The one framing that governs everything below

**A failing GATE at the end of Phase 6 is a legitimate, expected outcome of Phase 6.**

This phase is explicitly *before tuning*. If intent macro-F1 comes in at 0.84 against a 0.90 GATE, the correct
Phase 6 result is "gate failed, reported, here is the number" — not a relaxed threshold, not a narrowed golden
set, not a re-run until a good sample appears. Phase 7 tunes; Phase 6 measures. Writing this down first,
because the pressure to make one's own phase look complete is exactly how a metric set quietly becomes
decorative, and `SUCCESS-METRICS.md` §9's anti-gaming table already predicts most of the routes.

---

## 1. Build order — eight stages, one natural mid-phase gate

| Stage | Deliverable | Depends on | Real AWS? |
|---|---|---|---|
| **1** | **Mock-scope rule + guard** (`ADR-013`, `docs/TESTING-CONVENTIONS.md`) — Marco's carry-in 2, generalised from the Stage 8 moto bug. Written first because every stage after it writes tests that mix mocked and real backends, which is precisely the condition that produced the bug | Nothing | No |
| **2** | **Golden set** — schema (`evals/schema.py`), ≥60 labelled conversations under `evals/golden/`, per-category minimums enforced by a schema test, plus a **separately-stored held-out injury-phrasing set** (`SUCCESS-METRICS.md` §2's OBSERVED metric) | Phase 4's taxonomy/slots/policies | No — data only |
| **3** | **Tier A harness** — the deterministic runner and every metric computable with no live model, plus `make eval`. This is the CI gate's actual body | Stages 1–2, Phase 5's graph | No — fake-LLM harness |
| **4** | **Response-quality detectors** — length discipline and the **redundancy-by-restatement** check (Marco's carry-in 1), unit-tested against the committed real Stage 8 output that exhibits the defect | Stage 3 | No |
| — | **← natural gate here.** Everything deterministic is done, $0.00 spent, and the next three stages are the ones that cost money and need a judge-model decision | | |
| **5** | **Embedding fixture** — one real Titan run over the 21-chunk corpus and the golden set's coverage queries, vectors committed to `evals/fixtures/`. Makes retrieval recall@5 / MRR **real numbers that are also reproducible offline and free**, instead of either fake-vector nonsense or a per-run charge | Stage 2 | **Yes — once.** ≈$0.0003 |
| **6** | **Tier B harness + judge** — everything needing a live model: intent macro-F1, groundedness, answer relevance, abstention, compound-case correctness, per-conversation cost and agent-internal latency, `CF3`'s repeated tight-turn sampling, and the **independent injury set** (§3.3, Marco's addition at approval) with L1/L2 recall reported separately | Stages 3–5 | **Yes — the bulk of Phase 6's spend** |
| **7** | **Baseline + `docs/RESULTS.md`** — first full run, baseline committed as a reviewed artifact, results written up including whatever failed | Stage 6 | Yes — one full run |
| **8** | **CI regression gate** — workflow authored in `.github/workflows-for-monorepo-root/`, the prompt-changed-without-baseline check, and the **deliberately-bad-PR demonstration** (`SUCCESS-METRICS.md` §9: "an untested gate is not a gate") | Stage 7 | No |

Stages 2 and 4 are the plausible subagent candidates (bulk authoring; a self-contained detector with a
committed fixture). Stages 3, 6, 7 want the main thread — they are where a measurement mistake would be
invisible and would then be *published as a number*.

---

## 2. Where the cost gate applies

| Component | Real AWS in Phase 6? | Estimated spend |
|---|---|---|
| Mock-scope guard, golden set, Tier A harness, detectors | No | $0.00 |
| Embedding fixture (Stage 5) | **Yes, once** — `amazon.titan-embed-text-v2:0`, 21 chunks + ~70 golden queries ≈ 15k tokens | ≈$0.0003, then never again |
| Tier B run — router | **Yes** — `us.amazon.nova-micro-v1:0`, ~375 turns × ~950 tokens | ≈$0.015 / full run |
| Tier B run — generation | **Yes** — `us.amazon.nova-lite-v1:0`, ~25 generated answers | ≈$0.001 / full run |
| Tier B run — judge | **Yes** — model choice below | ≈$0.055 / full run |
| **Full Tier B run, all in** | | **≈$0.07** |

**Proposed Phase 6 sub-budget: $1.00** of the $5.00 standing cap — roughly 14 full runs, which is a realistic
number for a phase that will iterate on the harness itself, not just run it once. **Stop and report at
$0.75**, rather than discovering the overrun at the phase boundary. Every run logged in `COSTS.md` as usual.
Cap consumed to date is ≈$0.00037, so this would bring Phase 6's cumulative position to ≈$1.00 of $5.00, with
Phase 7's red-teaming still to come out of the same cap — worth stating now rather than being surprised by it.

**Never created in Phase 6, regardless of the cap** — unchanged from Phase 5's reasoning, since the cap covers
*inference*, not *provisioning*: no DynamoDB table, no Bedrock Guardrail resource, no Connect/Lex/Lambda
resource. All still Phase 8's, each with its own `APPROVED:` moment.

### The judge-model decision — recommendation, not a silent default

| Option | Cost / full run | Argument |
|---|---|---|
| **`us.anthropic.claude-haiku-4-5` (recommended)** | ≈$0.055 | Different vendor and family from both models under test, so a judge preference for its own generation style cannot inflate the score. $1/$5 per 1M is ~17× Nova Lite's rate and still rounds to nothing at this volume |
| `us.amazon.nova-lite-v1:0` | ≈$0.003 | Nova Lite judging Nova Lite's own output is a textbook self-preference setup. Saves $0.05 per run and costs the credibility of every judge-scored number in `RESULTS.md` |

The saving is not worth it. Recommending Claude Haiku 4.5, and either way `SUCCESS-METRICS.md`'s standing rule
holds: **a judge score is never the sole evidence for a claim about quality**, and every judge metric carries a
human-reviewed sample.

---

## 3. Marco's two carry-ins, designed rather than noted

### 3.1 `RentalTowingEntitlement` redundancy — a known failing case with real evidence

Stage 8 produced the evidence: with the Phase 4 prompt fix in place, one real trial returned a clean two-sentence
answer and another returned three sentences whose third restated "8 days remaining" already given in the second.
The fix is probabilistic, not deterministic. Both trials also volunteered the general 20-day cap alongside the
caller-specific answer, against the prompt's "no general mechanics" instruction.

The check is therefore built to catch **that specific output**, not a generic notion of verbosity:

1. **`evals/fixtures/known_bad/rental_redundant_20260811.txt`** — the actual real model output from Stage 8,
   committed verbatim as a fixture. Real evidence, not a hand-written approximation of the defect.
2. **A deterministic detector**, not a judge: extract the fact-bearing tokens per sentence (numeric quantities
   with their units, currency amounts, entitlement nouns) and flag any value asserted in more than one sentence.
   The known-bad fixture must be flagged; the known-good trial from the same session must not. A judge would be
   the wrong instrument here — the defect is mechanically visible, and a judge would make a cheap, exact check
   both expensive and arguable.
3. **A separate "general mechanics leaked" check** for the second half of the divergence: a caller-specific
   entitlement answer that also states corpus-level cap figures the caller did not ask for.
4. **It will be red on real output today, and that is the point.** Proposed handling: **TARGET for Phase 6,
   promoted to GATE at Phase 7 sign-off** once tuning has had its pass. Making it a GATE now leaves `main`
   permanently red on a known-open defect, which trains everyone to ignore a red gate — the specific failure
   mode `SUCCESS-METRICS.md` §2 already argued against for the recall gate. **This is a judgment call and it is
   Marco's to overrule**; if he wants it gated immediately, it gates immediately.

What is *not* negotiable either way: the detector's teeth are proven by a passing unit test against the
committed known-bad fixture, so the check cannot be quietly green-by-construction, and `RESULTS.md` reports the
real failure rate over repeated trials rather than a single sample.

### 3.2 The mock-scope rule — Marco's carry-in 2, generalised

The Stage 8 bug: a real Bedrock `Converse` call made inside a `with mock_aws():` block opened to seed a moto
DynamoDB table was intercepted by moto and answered with a fabricated 404. **The call never reached AWS and the
script would have happily reported on the response.** That is a false-verification pattern, not merely a bug —
the dangerous property is that it fails *silently in the direction of looking like it worked*.

`ADR-013` states the rule and `docs/TESTING-CONVENTIONS.md` makes it operational:

- **`mock_aws()` is process-wide within its context, for every service, not just the one being faked.** Stated
  as the primary fact, since the bug came from assuming otherwise.
- **No real-AWS call may be made inside a `mock_aws()` scope.** Mock scopes are opened as narrowly as possible
  and closed before any real client is constructed or used.
- **Any test or script mixing both must state which backend each call reaches**, in a comment at the mock
  boundary.
- **Enforcement, not just convention.** Intended mechanism: a guard inside the real client factories
  (`get_bedrock_runtime_client` and the Stage 5/6 real-run paths) that refuses to hand back a client while
  moto's botocore stubber is active. **Whether moto exposes a reliable, version-stable way to detect that it is
  patching is not yet verified** — if it does not, the honest fallback is a documented convention plus a
  CI grep that flags a real-client construction lexically inside a `mock_aws()` block, and `ADR-013` will say
  plainly that enforcement is partial rather than implying a guarantee it does not provide.

Marco assigned the application of this to Phase 9's integration tests. Recording it as **`CF4`** so the rule,
once written here, is actually applied there rather than existing as a doc nobody re-reads.

---

### 3.3 The independent injury set — Marco's addition at approval

§5's fourth bullet named the weakly-held-out injury set as a known soft number. Marco's response at approval
was that a soft number attached to the safety gate is not good enough, and that the phase should produce one
genuinely independent recall figure. Criterion 14.

- **Generated by an isolated subagent with a clean context** that never reads `agents/lexicon.py` and never
  reads `INTENT-TAXONOMY.md` §2.4 — the latter excluded because it is what the lexicon was built *from*, so a
  set derived from it would be circular in the same way. Seeded instead from external injury-description
  vocabulary and Marco's three examples (*"my neck feels funny"*, *"she isn't moving"*, *"there's a lot of
  blood"*), which are independent of the lexicon because Marco wrote them.
- **Deliberately weighted toward indirect and euphemistic phrasing**, since clean keyword variants are exactly
  what the lexicon already handles and would produce a flattering, uninformative number.
- **Frozen on generation. `agents/lexicon.py` is not modified in response to it during Phase 6.** A held-out
  set used to tune the detector is no longer held out. Misses are the finding; fixing is Phase 7's, and the
  set is spent the moment Phase 7 tunes against it.
- **L1 and L2 recall reported separately**, and separately again from criterion 3's weak set — never blended
  into one figure, because the L1-misses/L2-catches case is the layered design working and is worth showing.
  Both layers missing is the most important finding this phase can produce and goes at the top of `RESULTS.md`'s
  safety section with the missed phrasings quoted verbatim.

---

## 4. What Phase 6 does not build

Guardrail tuning and the red-team suite (Phase 7). Real Connect/Lex/Lambda anything (Phase 8). The load test,
cold-start measurement, and LocalStack integration suite (Phase 9). Installing the CI workflow at the monorepo
root — **the workflow file is authored inside `PROJECT_ROOT` this phase and copied to
`/Users/marco/K21/Real-world/.github/workflows/` in Phase 10, under its own separate approval by absolute
path.** Named here so the scope-rule boundary is visible in advance rather than arriving as a surprise request.

Also not built: the call simulator (`make simulate`). It is adjacent and tempting, but it is a Phase 9 e2e
concern and folding it in would be exactly the quiet scope widening this project keeps refusing.

---

## 5. What Phase 6's numbers will and will not mean

Written before the numbers exist, so the caveats cannot be tuned to fit them.

- **Latency measured here is agent-internal turn latency** — graph entry to response text — **not** the
  1,800 ms Lex-STT-to-Polly-audio GATE, which includes telephony, ASR and TTS legs this phase never touches.
  `RESULTS.md` must label it as such and must not print it next to the 1,800 ms figure without that label.
  Phase 9 owns the real measurement.
- **Task success, containment and repair rates are computed over author-generated conversations.** They measure
  the system against this project's own model of caller behaviour. `SUCCESS-METRICS.md` §10 already says no
  number here predicts real-caller behaviour; Phase 6 is where that caveat stops being hypothetical.
- **The held-out injury-phrasing set is only weakly held out.** It is authored by the same person who wrote
  `agents/lexicon.py`. Mitigation is procedural — author the held-out phrasings before re-reading the lexicon,
  and draw from external injury-description vocabulary rather than introspection — and the residual weakness is
  reported alongside the number, not omitted.
- **Retrieval metrics use real Titan vectors** (Stage 5), so recall@5 and MRR are genuine. Every other Tier A
  metric is structural and says nothing about model quality.
