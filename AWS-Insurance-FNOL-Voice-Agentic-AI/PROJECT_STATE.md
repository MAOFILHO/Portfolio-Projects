# PROJECT_STATE.md

### STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and my explicit approval.
- No billable AWS resource is created without me typing `APPROVED: <phase name>`.
- The Amazon Connect instance and DID already exist. Never create either.
- `PROJECT_STATE.md` is updated before any session ends.
- Restate these four conditions verbatim at the top of every session summary and after every `/compact`.

---

**Last updated:** 2026-08-11
**Current phase:** Phase 5 — Agent implementation — **in progress, Stages 1–5 of 8 complete, gated here at
Marco's explicit instruction** (Stages 6–7 are the LangGraph wiring; hitting that with clean context rather
than mid-compact was the point of the gate). Phase 4 signed off 2026-08-11.
**Progress:** Phase 2 signed off; Connect Customer Basic tier switch approved, executed, and verified same day. Phase 3: Ontario-specific policy corpus, coverage logic, endorsements, 6 policyholders/7 vehicles/8 claims (machine-validated), data card, and the ingestion pipeline (chunking → embedding → DynamoDB, tested) all complete and signed off. Phase 4: conversation design (taxonomy, slots, dialogue policies incl. barge-in×L1 ordering and the retry ceiling, prompt registry with a real-Bedrock length-discipline verification, persona) — signed off. Phase 5: `ADR-012` (MCP transport) plus Stages 1–5 (foundations, MCP servers, knowledge retrieval, Bedrock router, guardrails) built by four parallel subagents plus the main thread, integrated, 145/145 tests green, ruff/black/mypy strict clean, zero real AWS calls across all five stages.
**Running spend attributable to this project:** **$0.00** provisioned by us.
Pre-existing accrual only: the claimed Canada DID (rate unverified, est. $0.90–$3.00/mo).
Bedrock standing-approval budget consumed: **$0.0001161 of $5.00**.

---

## Phase status

| Ph | Name | Status |
|---|---|---|
| 0 | Repo archaeology, workspace setup, merge strategy | ✅ **Signed off** 2026-08-11 |
| 1 | Problem framing and success criteria | ✅ **Signed off** 2026-08-11 (two corrections applied) |
| 2 | Architecture and ADRs | ✅ **Signed off** 2026-08-11 |
| 3 | Data engineering and knowledge base | ✅ **Signed off** 2026-08-11 |
| 4 | Conversation design | ✅ **Signed off** 2026-08-11 |
| 5 | Agent implementation | 🟡 In progress — Stages 1–5/8 complete, gated 2026-08-11 |
| 6 | Evaluation harness | ⬜ Not started |
| 7 | Responsible AI and red-teaming | ⬜ Not started |
| 8 | Integration and telephony | ⬜ Not started |
| 9 | Testing | ⬜ Not started |
| 10 | CI/CD and progressive delivery | ⬜ Not started |
| 11 | Observability and operations | ⬜ Not started |
| 12 | Documentation and demo | ⬜ Not started |
| 13 | Continuous improvement design | ⬜ Not started |

---

## Phase 0 exit criteria — for sign-off

| # | Criterion | Status |
|---|---|---|
| 1 | All eight source repos read; per-repo purpose, stack, license, quality, reusability assessed | ✅ `docs/phase0/MERGE-MATRIX.md` |
| 2 | Merge matrix produced with per-module verdict and reason; discard rate computed and justified | ✅ 100 modules: 20 KEEP / 22 REFACTOR / 5 REWRITE / 53 DISCARD. **53% by module count (58% counting REWRITE as code discarded); ~97% by lines of code.** Justified per row |
| 3 | Dependency conflict report with resolutions | ✅ `docs/phase0/DEPENDENCY-CONFLICTS.md` |
| 4 | License incompatibilities flagged | ✅ All eight are MIT-0 — none |
| 5 | Domain artifact inventory, separate from the code matrix | ✅ `docs/phase0/DOMAIN-ARTIFACTS.md` |
| 6 | Real (non-synthetic) customer/policy data gate | ✅ Cleared — 3 named exclusions, see `SECURITY-FINDINGS.md` |
| 7 | Target monorepo layout + old→new path mapping | ✅ `docs/phase0/TARGET-LAYOUT.md` |
| 8 | `CLAUDE.md` opening with STOP CONDITIONS verbatim | ✅ |
| 9 | `PROJECT_STATE.md` seeded with phases, decisions, open questions | ✅ this file |
| 10 | `.claude/settings.json` auto-approving read-only commands only | ✅ |
| 11 | No application code written | ✅ |
| 12 | No billable resource created; $0.00 new spend | ✅ Cost Explorer confirms $0.00 |

### Verification results — including one criterion knowingly violated

Phase 0's plan carried nine mechanical verification items. Eight passed. **Item 1 was violated knowingly**
and is recorded as such rather than marked passed.

| # | Criterion | Result |
|---|---|---|
| 1 | `git status` clean after the commit; **nothing outside `PROJECT_ROOT` touched** | ⚠️ **VIOLATED — knowingly.** See below |
| 2 | Source repos unmodified | ✅ 0 files changed under `/Users/marco/K21/Temp/CallCenter/AWS` |
| 3 | `CLAUDE.md` reproduces STOP CONDITIONS verbatim | ✅ Byte-diffed against Section 2 of the brief |
| 4 | `.claude/settings.json` parses; no allow-entry matching `apply\|create\|delete\|destroy\|put\|invoke\|deploy` | ✅ 28 entries, 0 matches |
| 5 | Every merge-matrix row cites a real file path | ✅ Spot-checked |
| 6 | Discard rate computed, stated and justified per row — **no target** | ✅ 53% by module count / ~97% by LOC, both reported |
| 7 | Grep for the three named exclusions and leaked account IDs | ✅ Present only in the do-not-propagate docs, as intended |
| 8 | $0.00 new spend | ✅ |
| 9 | Exit criteria written for sign-off | ✅ |

#### ⚠️ Item 1 — violated knowingly, with justification

**What:** commit `210b875` modified **`/Users/marco/K21/Real-world/.gitignore`** — the monorepo root,
outside `PROJECT_ROOT`. Additive only (11 lines appended; nothing existing altered).

**Why it was necessary:** the monorepo root `.gitignore` excluded `.claude/` globally, so no Claude config
was tracked in any project. **Constraint 15 and the Definition of Done require `.claude/mcp.json` to reach a
fresh clone** so the local MCP servers are invocable without extra setup. Satisfying that requires a
tracked file, which requires the negation.

**Why it stands:** the change is correct and necessary for the Definition of Done. Reverting it to satisfy a
criterion that was **too narrowly written** would be the wrong trade — the criterion assumed no legitimate
reason to touch a shared file would arise, and that assumption was wrong. Marco's ruling, 2026-08-11.

**Scoping verified:** `settings.local.json` remains ignored; sibling projects that keep `.claude` local-only
are unaffected — both confirmed by `git check-ignore`.

**Process failure, separately from the change itself:** the edit *was* covered by an approval (the selected
`AskUserQuestion` option previewed these exact lines), but it was described only as "the root `.gitignore`"
rather than by absolute path, and the contradiction with item 1 was never surfaced — the criterion was
allowed to lapse silently instead of being reported as broken. Approval of a change's *intent* is not licence
to go quiet about its *scope*. This produced decision **D9** below.

---

## Phase 1 exit criteria — for sign-off

**No code written. No billable resource created. $0.00 new spend.** Artifacts only.

| # | Criterion | Status |
|---|---|---|
| 1 | Business domain scenario defined | ✅ `docs/phase1/PROBLEM-FRAMING.md` — fictional carrier "Example Mutual", P&C personal auto only |
| 2 | **Exactly six** intents specified, no additions | ✅ Six, each with slots, success criteria and failure definitions. Additions listed as explicitly deferred future work |
| 3 | Containment target defined | ✅ ≥65% of **non-mandatory** calls, with mandatory escalations excluded from the denominator |
| 4 | Escalation policy defined | ✅ Four routes in priority order; human reachable from every state; never gated behind slot filling |
| 5 | Non-goals defined | ✅ Anchored on the authority matrix: $0 settlement authority, cannot deny, never adjudicates |
| 6 | AI use-case card written | ✅ `docs/phase1/AI-USE-CASE-CARD.md` — intended use, users, out-of-scope uses, 12 failure modes, human oversight model, and what oversight is *absent* |
| 7 | Metrics defined **before** building | ✅ `docs/phase1/SUCCESS-METRICS.md` — 60+ measures across safety/component/conversation/latency/cost/reliability, each labelled GATE, TARGET or OBSERVED |
| 8 | Containment shown to be non-gameable | ✅ Three structural guards plus an explicit anti-gaming table covering six gaming routes |
| 9 | No invented metrics (constraint 13) | ✅ Every threshold labelled a target or gate, never a result; a "not yet measurable" section states four gaps openly |

### Key Phase 1 design decisions

- **Injury escalation is not a classifier decision.** Detection runs as a deterministic pre-node on every turn, before the model sees the input, and is not overridable downstream. This makes intent 6 a property of the graph rather than a behaviour the model is asked to exhibit.
- **Correct abstention scores as success.** "I don't have that in your policy — let me get you to someone who does" is a win, not a containment failure.
- **Escalation recall is a gate; escalation precision is not.** A wasted transfer costs a human minute; a missed injury escalation is the failure this system must not have. False-escalation rate keeps the bias from becoming useless behaviour, but does not trade against recall.
- **Intent 4 fails if answered from the policy alone**, even when the coverage statement is true — the compound case requires both sources.
- **A silent partial write on contact update is a critical defect**, not a missed target: 0 occurrences, gated.

---

## Phase 2 exit criteria — **signed off 2026-08-11**

**No application code, no Terraform apply, no billable resource created. $0.00 new spend.** Artifacts only —
every deliverable below is documentation/ADRs, verified against live sources rather than memory throughout.

| # | Criterion | Status |
|---|---|---|
| 1 | Written exit criteria and explicit approval before this phase began | ✅ Marco: *"Proceed with Phase 2, ADR-008 and ADR-007 first"* — explicit authorization to begin artifact-only Phase 2 work, distinct from a billable-resource approval |
| 2 | All 11 required ADRs drafted and accepted | ✅ `docs/adr/ADR-001` through `ADR-011`, all dated 2026-08-11, all sourced |
| 3 | Region selection (ADR-008) | ✅ `us-west-2` retained; residency caveat on `us.*` disclosed, not glossed over |
| 4 | IaC tool selection, three-way (ADR-007) | ✅ Nested CFN `AWS::Lex::Bot`, all three options assessed on the merits; not pre-decided by the Phase 0 proposal |
| 5 | Safety-detection ordering visible in architecture (ADR-010, promoted from Q8) | ✅ Verified mechanism (`ApplyGuardrail` decoupling), diagrammed in `docs/phase2/ARCHITECTURE.md`'s sequence diagram |
| 6 | Mermaid architecture diagram, in-repo | ✅ `docs/phase2/ARCHITECTURE.md` |
| 7 | Full cost model, zero free-tier/zero-credits assumption, free-tier table, per-resource teardown-risk column | ✅ `docs/phase2/COST-MODEL.md` — surfaced the Connect Customer vs. Basic pricing-tier finding (Q11, flagged for Marco, not executed) |
| 8 | Threat model — prompt injection, tool abuse, PII leakage, toll fraud, denial-of-wallet | ✅ `docs/phase2/THREAT-MODEL.md`, seeded from `docs/phase0/SECURITY-FINDINGS.md`, each threat class mapped to a specific ADR/decision |
| 9 | No invented metrics or capabilities (constraint 13, extended to engineering claims) | ✅ Every unverified figure explicitly labelled ("unconfirmed," "engineering estimate pending benchmark") rather than asserted — e.g. `ADR-009`'s cold-start latency, `ADR-002`'s cosine-similarity latency |
| 10 | Pricing verified against current sources, never memory | ✅ Three parallel research passes (region/IaC facts; Bedrock/Guardrails/Agents facts; full pricing sweep), all cited with URLs and fetch date; corrected two carried-forward errors (Nova Micro/Lite pricing in `CLAUDE.md`; the "no DynamoDB checkpointer exists" assumption in `ADR-005`) |
| 11 | No billable resource created; $0.00 new spend | ✅ Documentation and artifacts only throughout |
| 12 | **Marco's explicit sign-off** | ✅ **`APPROVED: Phase 2`, typed 2026-08-11**, with two follow-up asks resolved same day: Q11's tier-switch mechanism, and an explicit $25-ceiling verdict (see session log below) |

### Key Phase 2 findings worth flagging explicitly at sign-off

- **Two corrections to carried-forward assumptions**, surfaced rather than left standing: (a) Nova Micro/Lite
  pricing in `CLAUDE.md` was materially wrong (now corrected, both came in cheaper than assumed); (b) the
  Phase 0/1 assumption that no maintained DynamoDB LangGraph checkpointer existed is no longer true —
  `ADR-005` adopts `langgraph-checkpoint-aws` instead of writing one from scratch, after running down a
  real CVE chain found in the same research pass.
- **One live cost-saving option surfaced, not executed:** switching the Connect instance from "Connect
  Customer" to "Connect Customer Basic" pricing would roughly halve the dominant telephony cost, since this
  project doesn't use Connect Customer's bundled AI anyway (`ADR-001`). Recorded as **Q11**, explicitly
  Marco's decision.
- **One Phase 0 guidance item is formally reversed**, not silently: `ADR-011` blanket-redacts `DATE_TIME` from
  transcripts/logs, reversing `docs/phase0/DOMAIN-ARTIFACTS.md`'s original taxonomy note. The Phase 0 artifact
  itself is left unedited (historical record); the reversal is stated by name in `ADR-011`.

---

## Phase 3 exit criteria — proposed 2026-08-11, **approved same day (`APPROVED: Phase 3`)**

Per the STOP CONDITIONS, no Phase 3 work starts until this table is approved. Scope, per the Phase 0 roadmap
and the open items it already named as Phase 3's: a synthetic policy corpus internally consistent enough
that groundedness evals mean something, the two intents with **zero prior art anywhere in the source corpus**
(rental/towing entitlement, `R5`), policyholder/vehicle/claim records, an ingestion pipeline into the
DynamoDB vector store (`ADR-002`), and a data card. No application/agent code (that's Phase 5); no billable
resource beyond the already-approved $5 Bedrock standing cap if embeddings generation is exercised here
(`ADR-002`'s Titan Embed v2, on-demand, effectively free at this corpus size).

| # | Criterion | Notes |
|---|---|---|
| 1 | Synthetic policy wordings authored for all six intents' coverage needs, **internally consistent** (same policy numbers/limits/deductibles referenced consistently across documents) | ✅ `data/synthetic/policy/example-mutual-oap-policy-wording.md` — anchored to **Ontario** specifically (OAP 1 section structure, SABS, DCPD), not generic NA boilerplate, per Marco's explicit steer. Grounding + per-claim citation audit in `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` — a real error (DCPD deductible claimed as universally absent) was caught and corrected during that audit, not just decorated with citations |
| 2 | Rental/towing entitlement sections authored from scratch, consistent with the rest of the corpus | ✅ Resolves `R5` — `data/synthetic/policy/endorsements.md`. Rental modeled on real OPCF 20 ($50/day, 20-day/$1,000 cap); towing modeled as a bundled $150/incident allowance inside the DCPD/Collision claim itself, not a separate OPCF 35 roadside product — scope decision named, not silent |
| 3 | Deductible logic, total-loss threshold, and injury-severity→coverage mapping (BI/PIP/MedPay) authored | ✅ Resolves `Q5` — `data/synthetic/policy/coverage-logic.md`. Total-loss threshold stated as Example Mutual's explicit 80%-of-ACV policy rule (Ontario sets no single legislated %). KABCO (scene severity) and SABS's MIG/non-cat/catastrophic tiers kept as two distinct axes, never conflated. §4 (new) decides how "am I entitled to X" is answered for the SABS optional elections: by question type (election-fact vs. eligibility-determination), not benefit type |
| 4 | Claim-number format finalized and documented | ✅ Resolves `Q3` — `docs/phase3/DATA-CONTRACTS.md`: `CLM-YYMM-NNNNN-C`, Luhn mod-10, worked example `CLM-2608-00042-4` |
| 5 | Synthetic policyholder, vehicle, and claim records created, matching the ID formats and PII taxonomy corrections from Phase 0 (VIN/plate/policy#/claim# added; `DATE_TIME` **not** exempted per `ADR-011`'s reversal) | ✅ `data/synthetic/{policyholders,vehicles,claims}/*.json` — 6 policyholders, 7 vehicles, 8 claims, machine-validated against `docs/phase3/DATA-CONTRACTS.md` and `coverage-logic.md`'s formulas by `scripts/validate_synthetic_records.py` (checked in, re-runnable, not a one-off manual check). Deliberate variation in optional-benefit elections and Section 7 selections per Marco's instruction, so `CoverageQuestion` has real ground truth to evaluate in Phase 6 |
| 6 | Deliberately invalid VIN check digit used throughout — never the structurally-valid VIN flagged in Phase 0 archaeology | ✅ All 7 synthetic VINs use WMI `9SY` (unassigned) with a position-9 check digit machine-verified as deliberately wrong, not accidentally valid |
| 7 | Ingestion pipeline: chunks corpus, embeds via Titan Embed v2, writes to DynamoDB per `ADR-002`'s schema | ✅ `src/fnol_voice_agent/knowledge/ingest.py` + `tests/unit/test_ingest.py` (8/8 passing) + `Makefile`'s `ingest` target. Section-based chunking (21 chunks/3 files), Marco-required MANIFEST (`data/synthetic/.ingest-manifest.json`, gitignored — generated artifact), idempotent via a `STATE#<file>` hash check. Ran end-to-end against the real corpus with `--embeddings mock --vector-store local` (the safe defaults) — **no real Bedrock/AWS call made**, `$0.00` logged in new `COSTS.md` |
| 8 | Data card written: what's synthetic, what's derived from real regulatory/domain sources (KABCO, NHTSA MMUCC), what's authored with no external grounding at all (rental/towing, deductible logic) | ✅ `docs/phase3/DATA-CARD.md` — as-of-date warning carried prominently at the top per Marco's instruction; provenance graded per-document, with the corpus-construction-choice reframing (§3, Marco's own language) restated here too, not just upstream |
| 9 | No real customer/policy PII introduced; no images vendored from any source repo | ✅ All names/phones/emails/addresses fabricated (555 exchange, `@example.com`, generic Ontario streets); no images anywhere in Phase 3 output |
| 10 | No application/agent code written (Phase 5's scope, not this one) | ✅ The ingestion pipeline is data-engineering (chunk/embed/write), not agent/orchestration code — no LangGraph, no tool-calling, no conversation state anywhere in `src/`. This distinction was scoped explicitly before writing any code, not asserted after the fact |
| 11 | No billable resource created beyond exercising the already-approved $5 Bedrock standing cap (Phases 3–7), logged per-run in `COSTS.md` | ✅ `COSTS.md` created; **$0.00 of $5.00 consumed** — every run this phase used mock embeddings and a local moto-backed table, never real Bedrock or a real DynamoDB table (which doesn't exist yet — Phase 8 not approved) |
| 12 | Marco's explicit approval to begin, per the STOP CONDITIONS | ✅ `APPROVED: Phase 3`, typed 2026-08-11 |

---

## Phase 4 exit criteria — approved 2026-08-11, content complete, awaiting closing sign-off

**Marco typed `APPROVED: Phase 4`** and added one requirement above the original scope: given R4 (barge-in
has zero prior art anywhere in the source corpus), the barge-in/repair criterion (6) needed two things
designed explicitly rather than left implicit — (a) how a mid-prompt barge-in interacts with L1's safety
ordering (`ADR-010`'s constraint, applied to the interruption path, not just the normal turn path), including
what happens to a barge-in cut off mid-word; and (b) a named no-input/no-match retry ceiling with a stated
terminal behavior, since an IVR that loops on no-match is the most common way these systems become unusable,
and `D13` means the terminal behavior must be escalation, not a hang-up. Both are now `DIALOGUE-POLICIES.md`
§6 and §7 respectively — load-bearing sections, not appendices.

Per the STOP CONDITIONS, no Phase 4 work starts until this table is approved. Scope, per the Phase 0 roadmap:
taxonomy, slots, utterances (incl. adversarial), prompt registry, dialogue policies, barge-in/repair, persona,
escalation triggers — flagged at Phase 0 as having **zero prior art in any of the eight source repos** (R4:
no `AllowInterrupt`, no `PromptAttemptsSpecification`, no `DTMFSpecification`, no `WaitAndContinueSpecification`,
no streaming/interim-audio pattern anywhere in the corpus). This is design/artifact work only — no LangGraph
graph, no MCP servers, no tool implementations (that's Phase 5). No billable resource beyond an optional,
separately cost-gated closing verification (see criterion 12), mirroring how Phase 3 closed.

Five deliverables, mapped to the eight roadmap components:

| File | Roadmap components covered |
|---|---|
| `docs/phase4/INTENT-TAXONOMY.md` | taxonomy; utterances incl. adversarial |
| `docs/phase4/SLOT-DESIGN.md` | slots |
| `docs/phase4/DIALOGUE-POLICIES.md` | dialogue policies; barge-in/repair; escalation triggers |
| `docs/phase4/PROMPT-REGISTRY.md` | prompt registry |
| `docs/phase4/PERSONA.md` | persona |

| # | Criterion | Status |
|---|---|---|
| 1 | Intent taxonomy finalized for all **six** intents (no additions), each with a canonical utterance set plus adversarial/ambiguous phrasings (multi-intent in one turn, out-of-scope requests, low-confidence phrasing) and a stated disambiguation policy | ✅ `docs/phase4/INTENT-TAXONOMY.md` — 6 canonical sets, 6 adversarial categories (multi-intent, out-of-scope, low-confidence, injury-phrasing-as-lexicon-seed, `CoverageQuestion` sub-question-type pairs, injury barge-in mid-elicitation), disambiguation policy §3 |
| 2 | Full slot specification for every slot-bearing intent — `FileAutoClaim`'s ~11 slots and `UpdateContactInfo` — covering elicitation prompt, validation rule, confirmation requirement, retry/reprompt ladder, and DTMF fallback grammar for digit-bearing slots (claim/policy number, matching `DATA-CONTRACTS.md`'s digits-only formats) | ✅ `docs/phase4/SLOT-DESIGN.md` — 11-slot priority order + per-slot table for `FileAutoClaim`, 3-slot table for `UpdateContactInfo`, brief specs for the remaining three intents, DTMF policy scoped to exactly the three digits-only identifier slots |
| 3 | **`CoverageQuestion` (intent 3) dialogue policy authored per `coverage-logic.md` §4's question-type split** — an explicit decision path showing how the dialogue manager distinguishes election-fact sub-questions (mandatory: pure RAG; optional: RAG + a policyholder-election lookup) from eligibility/amount sub-questions (always deflected to a human) *before* generating a response, not after. Names the tool surface this requires (a `GetPolicyholderElections`-shaped call) as a forward requirement for Phase 5, not built here | ✅ `docs/phase4/DIALOGUE-POLICIES.md` §2. **Marco's requirement — designed now, not discovered in Phase 5** |
| 4 | Rental/towing (intent 4) dialogue policy authored, consistent with `endorsements.md`'s existing RAG+tool compound shape | ✅ `docs/phase4/DIALOGUE-POLICIES.md` §3 |
| 5 | Injury/fatality (intent 6) hard-escalation dialogue behavior specified: exact scripted language, preemption from any state, and its relationship to the deterministic pre-node (D12/D15) made explicit at the dialogue-design level, not just the architecture level | ✅ `docs/phase4/DIALOGUE-POLICIES.md` §5 |
| 6 | Barge-in and repair policy: explicit "agent" barge-in intent reachable from every state; no-input/no-match retry ladder with a stated max-retry count and escalation-on-exhaustion, not an infinite loop. **Extended by Marco mid-phase**: the L1×barge-in ordering (incl. mid-word cutoff) and the retry ceiling's terminal behavior both designed explicitly | ✅ `docs/phase4/DIALOGUE-POLICIES.md` §6 (barge-in reuses the exact per-turn pipeline, no second code path; mid-word cutoff handled by an open re-prompt drawn from the *same* retry ladder, not a separate loop) and §7 (ceiling = 2 consecutive no-input/no-match per slot/question; terminal state is always escalation, never hang-up — stated as an explicit negative rule) |
| 7 | Write-path confirmation policy for `UpdateContactInfo` — explicit read-back-and-confirm step required before any write | ✅ `docs/phase4/DIALOGUE-POLICIES.md` §4, mechanics in `SLOT-DESIGN.md` §2 — one retry only (tighter than the general 2-attempt ceiling), matching the "critical defect, not missed target" framing already set in Phase 1 |
| 8 | Prompt registry drafted for every model-calling node (the merged Nova Micro router+L2 call per `ADR-004`; the generation node) | ✅ `docs/phase4/PROMPT-REGISTRY.md` §1, §3 — full tool schema and system prompt for the merged call, system prompts + suggested `max_tokens` for both generation-node use cases |
| 9 | **Response-length discipline made an explicit, structured part of every prompt spec** — a per-intent/per-turn-type tolerance table, tied to the 1,800ms p95 turn-latency budget, motivated by the observed Nova Micro pre-flight padding case, with a named enforcement mechanism | ✅ `docs/phase4/PROMPT-REGISTRY.md` §2 — extended beyond the two generative nodes: the registry's own structural finding is that most spoken lines are fixed/templated, not generated at all (§1), which is itself the primary length-discipline mechanism; the tolerance table (§2.1) covers both generated and templated turns, with per-category enforcement (§2.2). **Marco's requirement — explicit, not left as an implicit prompting habit** |
| 10 | AI disclosure script for the greeting, and persona/tone spec (formality, empathy phrase bank — refactored from repo 6 per the Phase 0 merge matrix) | ✅ `docs/phase4/PERSONA.md` — greeting + direct-question disclosure scripts (§2), tone rules (§3), a single budgeted (once-per-call, not per-turn) empathy phrase rather than a rotating bank, reasoned explicitly against the same padding concern as criterion 9 |
| 11 | Full escalation-trigger enumeration — every trigger mapped to a specific routing action, cross-checked against Phase 1's four escalation routes so nothing is added or dropped silently | ✅ `docs/phase4/DIALOGUE-POLICIES.md` §8 — 11 triggers mapped to routes 1–4, explicit rule that no trigger may be tuned to trade recall for containment optics (`D13`) |
| 12 | No application/agent code written — the LangGraph graph, MCP servers, and tool implementations are Phase 5's scope. No billable resource created; $0.00 new spend, **except** an optional closing verification (same pattern as Phase 3's real-embedding check): a small number of real Bedrock calls against the drafted prompts to confirm the length-discipline instructions hold empirically, cost-gated separately, not assumed here | ✅ No code written this phase — five Markdown design documents only. **Optional closing verification not yet run** — remains available, not exercised without separate cost-gate approval |
| 13 | Marco's explicit approval to begin, per the STOP CONDITIONS | ✅ `APPROVED: Phase 4`, typed 2026-08-11, with the two barge-in/retry additions folded into criterion 6 before work began |

### Carried-forward risks and open items this phase must respect, not resolve

- **R4** (zero prior art for barge-in/DTMF/timeouts/streaming) is what this phase exists to close at the
  design level — Phase 9 still measures the real cold-start/latency numbers against it.
- **R1's residual gap** (unconfirmed `PromptAttemptsSpecification` behavior under nested CFN for multi-slot
  intents) stays a Phase 8 proof-of-concept; Phase 4 only fixes the *policy* (retry counts, ladder shape), not
  the CFN mechanics.
- **Q7** (does a reranker earn its latency) and **Q9** (free-text location redaction is hard) remain open,
  owned by Phase 6/7 respectively — not blocking Phase 4 sign-off.
- Phase 1's non-gameable containment definition and escalation-recall-as-gate (D13) constrain how the
  escalation-trigger table in criterion 11 may be written — a trigger that quietly narrows recall to improve
  containment optics would violate D13, not just be bad design.

---

## Phase 5 exit criteria — approved 2026-08-11 to begin; **Stages 1–5 complete, gated here per Marco's instruction**

`APPROVED: Phase 5` authorized the phase to begin, with Marco's requested build order/dependency sequence and
per-component cost gate answered in `docs/phase5/BUILD-PLAN.md`. Marco also directed: subagents for Stages
1–5, main thread as integrator for Stages 6–7, and **an explicit gate after Stage 5** — Stages 6–7 are the
wiring, to be hit with clean context rather than mid-compact. That gate is where this table now stands.

| # | Criterion | Status |
|---|---|---|
| 1 | Build order specified as dependency-ordered stages, each a clean gate point, with an explicit note on which stages could be delegated to isolated subagents vs. which need the main thread as integrator | ✅ `docs/phase5/BUILD-PLAN.md` §1 |
| 2 | MCP transport (in-process vs. wire protocol) resolved as a short ADR **before** the MCP servers are built, not left implicit | ✅ `ADR-012` — in-process at runtime, wire protocol proven servable via a falsifiable test, not assumed |
| 3 | Foundational typed contracts: `models/`, `validation/`, `config/` | ✅ Stage 1 — validated directly against the real Phase 3 corpus; caught and fixed 3 real schema mismatches plus a real gap in the rental total-loss exception |
| 4 | MCP servers, one per backend domain, wrapping Phase 3's synthetic records as typed tool calls; `.claude/mcp.json` registered | ✅ Stage 2 — **`ADR-012`'s falsifiable test passes for all four servers**, not just the required minimum: real subprocess, real `mcp` SDK client, wire-protocol result matches the in-process call exactly, no handler modified to make it work |
| 5 | Knowledge retrieval — the read half of `ADR-002`'s design | ✅ Stage 3 — real measured cosine-similarity latency: **0.036 ms** average over 1,000 calls against the real 21-chunk corpus, confirming (not just estimating) `ADR-002`'s "negligible against the 1,800 ms budget" claim |
| 6 | Bedrock router implementing `PROMPT-REGISTRY.md` §1's two call paths; fake-LLM harness | ✅ Stage 4 — `ADR-004`/Q10's structural separation is now a passing assertion (flip the generation flag, prove the router's requested model ID never moves), not a docstring claim |
| 7 | Guardrails + PII redaction module, built and tested against a mocked `ApplyGuardrail` client | ✅ Stage 5 — honest about limits: no name detection (assigned to Bedrock Guardrails, per `ADR-011`), date/time and location redaction catch plain phrasing only, creative phrasing (`ADR-011`'s own example) is a named, un-closed gap |
| 8 | LangGraph nodes for all six intents plus the L1 safety pre-node | ⬜ Stage 6 — **not started, per the Stage 5 gate** |
| 9 | Graph assembly, DynamoDB checkpointer, integration tests | ⬜ Stage 7 — **not started, per the Stage 5 gate** |
| 10 | Cost gate named per component | ✅ `docs/phase5/BUILD-PLAN.md` §2 — and now empirically confirmed, not just planned: **zero real AWS calls across all five stages** |
| 11 | Mock-by-default holds for every stage | ✅ Stages 1–5, confirmed by 145/145 passing tests with no real AWS credentials touched |
| 12 | No billable resource created; $0.00 new spend | ✅ $0.00 across Stages 1–5. Stage 8's optional real-Bedrock verification remains unexercised, pending its own separate cost-gate approval when Stages 6–7 are done |
| 13 | Marco's explicit approval to begin | ✅ `APPROVED: Phase 5`, typed 2026-08-11 |

**Phase 5 is not signed off — it is mid-phase, at the requested gate.** Stages 6–7 (LangGraph nodes, graph
assembly, checkpointer) have not started. No exit criteria beyond this table exist for them yet; per the
STOP CONDITIONS, that work does not begin without Marco's separate go-ahead.

---

## Decisions to date

| # | Decision | Rationale | Date |
|---|---|---|---|
| D1 | Docs are `PROJECT_STATE.md` + `CHANGELOG.md` only — no `PLAN.md`/`TASKS.md` | STOP CONDITIONS make PROJECT_STATE the single source of truth; three overlapping status files would drift | 2026-08-11 |
| D2 | Make targets: `bootstrap/deploy/destroy/eval/redteam` canonical, `provision`/`teardown` as aliases | Satisfies the Definition of Done verbatim while preserving sibling-project vocabulary | 2026-08-11 |
| D3 | Bedrock on-demand inference pre-approved for Phases 3–7, **$5 hard cap**, logged per-run in `COSTS.md` | Avoids a gate prompt on every eval run; provisioned resources still gated individually | 2026-08-11 |
| D4 | **Discard rate is an output to report and justify, not a target to hit** | A threshold on a descriptive statistic invites gaming the statistic instead of doing honest analysis. Low rates get challenged on the merits | 2026-08-11 |
| D5 | Python `>=3.12,<3.13`; ruff line-length 100, `select=["E","F","I","UP","B","SIM"]`; mypy strict | Matches sibling project `AWS-Bedrock-FineTuning-LangGraph-MCP-Agentic-Platform` | 2026-08-11 |
| D6 | Workflows authored in `.github/workflows-for-monorepo-root/`, prefixed `FNOL_*` repo variables | GitHub Actions ignores workflows inside project subfolders silently; established monorepo convention | 2026-08-11 |
| D7 | Vendor **no images** from any source repo | Redaction/console screenshots and DMV specimens are an accidental-PII and likeness vector | 2026-08-11 |
| D8 | **Simulator-first**; real calls reserved for demo/verification | Telephony is ~92% of the ~$0.20 marginal cost per conversation; ~100 real calls would nearly exhaust the $25 budget | 2026-08-11 |
| D9 | **Out-of-`PROJECT_ROOT` scope rule** — reproduced verbatim in `CLAUDE.md` | Shared monorepo files affect ~15 sibling projects, so blast radius exceeds the project being worked on. Being in the same git repo does not make a file in scope | 2026-08-11 |
| D10 | Commit `210b875` stands; item 1 recorded as knowingly violated rather than marked passed | The change is correct and necessary for the Definition of Done; reverting it to satisfy a too-narrowly-written criterion is the wrong trade | 2026-08-11 |
| D11 | Fictional carrier named **"Example Mutual"** | Deliberately synthetic so the public portfolio artifact cannot be confused with, or mistaken for, a real insurer. Upstream repo 5 used "AnyInsurance"; a plausible-sounding invented name risks colliding with a real carrier | 2026-08-11 |
| D12 | Injury detection is a **deterministic pre-node**, not an intent classified by the model | Makes intent 6 a property of the graph rather than a model behaviour, so 100% recall is structurally achievable and not overridable downstream | 2026-08-11 |
| D13 | Mandatory escalations excluded from the containment denominator; safety recall a separate 100% gate | Naive containment rewards refusing to escalate. Prevents the metric creating pressure against the behaviour the system exists to guarantee | 2026-08-11 |
| ~~D14~~ | ~~**Loss date/time is NOT redacted**~~ — **SUPERSEDED by D16** | Original rationale was a utility argument only, which was insufficient and produced the wrong design | 2026-08-11 |
| D15 | **Layered injury detection (L1+L2+L3) is an architectural requirement**, and the recall gate is split: 100% GATE on the labelled safety set, held-out novel phrasings reported with no threshold | Resolves Q6 instead of deferring it. A single detector cannot achieve 100% recall against unbounded natural language, and a gate known to be unachievable gets quietly excepted the first time it fails. The labelled gate got *stricter* (a failure is now a code defect, not a tuning problem) and a hidden weakness became a standing reported metric | 2026-08-11 |
| D16 | **Loss date/time and loss location get identical treatment: both retained in the structured claim record, both redacted from transcripts and logs.** VIN/plate/policy/claim number added as redaction targets | Date + time + location is a **quasi-identifier close to uniquely identifying**, because a collision at a given place and time is often externally recorded (police reports, news, traffic/roadside logs). Redacting `NAME`/`PHONE` while keeping the tuple is not de-identification. Splitting a quasi-identifier across two policies protects nothing. The utility need is met by the structured record, so utility and privacy only conflicted while both lived in the same store | 2026-08-11 |
| D17 | **The generation node (feature-flagged tier, `ADR-004`) is invoked for exactly two cases** — `CoverageQuestion` election-fact synthesis and `RentalTowingEntitlement` compound synthesis. Every other spoken line (elicitation, confirmation, retry, escalation, greeting) is a fixed string or a deterministic template substitution, never free generation | This is the primary mechanism behind the voice length-discipline requirement: a line that was never generative cannot pad itself. It also narrows the generation-tier feature flag's real blast radius to two prompts, both fully specified in `docs/phase4/PROMPT-REGISTRY.md` | 2026-08-11 |
| D18 | **No-input/no-match retry ceiling fixed at 2 consecutive attempts per slot/question; the terminal state is always escalation (route 3), never a hang-up** | Makes concrete what `PROBLEM-FRAMING.md`'s escalation route 3 already numbered but didn't operationalize. Stated as an explicit negative rule ("hang-up is never a fallback state") because a missing terminal branch is exactly the kind of defect that's easy to leave implicit and hard to notice until a real call falls through it | 2026-08-11 |
| D19 | **Barge-in reuses the identical per-turn pipeline as any other turn — no `is_barge_in` branch anywhere.** An inconclusive barge-in (no safety trigger detected, including one cut off mid-word) triggers exactly one open re-prompt, drawn from the *same* retry ladder as D18, not a separate uncounted loop | Marco's addition, given R4's zero prior art. Keeps the barge-in-ordering question answerable by pointing at `ADR-010`'s existing mechanism (L1 runs first on raw input, unconditionally) rather than inventing new ordering machinery for the interruption path specifically. Prevents the repair mechanism itself from becoming the unbounded-loop failure mode it exists to close | 2026-08-11 |
| D20 | **"The majority of this system's spoken output is deterministic and cannot hallucinate" is a stated architectural claim**, not just an implementation detail of `D17` — checkable because `PROMPT-REGISTRY.md` §1 names the entire generative surface area (exactly two prompts). Elevated to Phase 12's README as a claim to make explicitly, not left buried under D17 | Marco: "D17 is more consequential than its placement suggests." A structural absence-of-hallucination-surface property is a stronger and more honest claim than a tuned mitigation, and belongs in the portfolio narrative once Phase 12 exists to state it | 2026-08-11 |

### Carried forward to future phases — named now so they aren't rediscovered later

| # | Item | Owner phase | Source |
|---|---|---|---|
| CF1 | State explicitly in the README: only two prompts in the entire system invoke generation (`CoverageQuestion`, `RentalTowingEntitlement`); everything else is fixed/templated and cannot hallucinate | Phase 12 | `D20`, `docs/phase4/PROMPT-REGISTRY.md` |
| CF2 | Load testing should concentrate on the two generation paths rather than distributing effort uniformly across all six intents — every other intent's latency is fixed-string/template latency, not model latency | Phase 9 | Marco, 2026-08-11 |
| CF3 | The Nova Micro tight-turn result from Phase 4's closing verification is **n=1** — a smoke test, not evidence the pre-flight padding behaviour is absent. The length check must sample **repeatedly** on that specific path, since it's the one with a known prior failure | Phase 6 | Marco, 2026-08-11 |

### Proposed, pending Phase 2 ADR

P1 is **resolved** — accepted as `docs/adr/ADR-007-iac-tool-selection.md` (2026-08-11). Nothing pending here.

---

## Pre-provisioned resources — never create, never destroy

| Resource | Identifier |
|---|---|
| Connect instance | `eba56246-0368-4f1c-8b97-e2ab3b0e8246` (`marcos-ivr-demo`), ACTIVE, `CONNECT_MANAGED`, inbound-only, created 2026-08-11 |
| Connect access URL | `https://marcos-ivr-demo.my.connect.aws` |
| DID | `+14169871547` — id `55cba0a6-3f67-4982-b3d8-6943d3b07054`, **`PhoneNumberCountryCode: CA`**, type DID, status CLAIMED |
| DID ARN | `arn:aws:connect:us-west-2:759316130780:phone-number/55cba0a6-3f67-4982-b3d8-6943d3b07054` |
| DID tags | `Project=AWS-Insurance-FNOL-Voice-Agentic-AI`, `Owner=marcos`, `Protected=true` |

**The `Protected=true` tag is load-bearing.** The `infra/terraform/stacks/telephony` import guard asserts its
presence before proceeding (Phase 8). The number lives in separate Terraform state with
`prevent_destroy = true` and `make destroy` must not touch it — releasing and re-claiming risks a **180-day
claim block**.

---

## Risks and blockers

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **Terraform `aws_lexv2models_*` resources are known-broken exactly where we need them** — `prompt_specification` updates silently dropped ([#42147], confirmed **still open** 2026-08-11), `prompt_attempts_specification` / `message_selection_strategy` "inconsistent result after apply" ([#36845], confirmed **fixed** in provider v5.66.0), **intent↔slot circular dependency via `slot_priority`** ([#39948], confirmed **still open** 2026-08-11 — structural, not a pending patch) | Hits the barge-in/DTMF config (constraint 14) and the 9-slot FNOL intent (the showcase) | **Resolved by ADR-007** (accepted 2026-08-11): single nested CFN `AWS::Lex::Bot` resource, structurally immune to the cycle. Residual gap (unconfirmed `PromptAttemptsSpecification` behavior under CFN for multi-slot intents) carried forward as a mandatory Phase 8 proof-of-concept, not asserted as resolved |
| R2 | Canada DID rate unverified — pricing appendix 404s, Connect telephony usage types not exposed in the Pricing API | Unknown fixed monthly floor against a $25 ceiling | Read actuals from Cost Explorer in Phase 2, once ≥1 day of accrual exists |
| R3 | The 12-month free tier no longer exists; **Lex V2 has no perpetual free tier** ($0.004/speech request from turn one) | Cost model cannot assume free Lex or credits | Cost model built on always-free tiers + pay-per-use only; simulator-first (D8) |
| R4 | **Zero prior art in all eight repos** for barge-in, DTMF, no-input/no-match, timeouts, streaming, or interim audio fillers — the combined corpus contains only `MaxRetries: 2` | Constraint 14's 1,800 ms p95 must be engineered from docs, not adapted | Budget real time in Phase 4; measure cold-start impact in Phase 9 |
| ~~R5~~ | ~~Two of the six intents (rental/towing entitlement) have no source material anywhere in the corpus~~ | **RESOLVED** | `data/synthetic/policy/endorsements.md` — rental (OPCF 20-modeled) and towing (bundled DCPD/Collision allowance) both authored, grounded against real Ontario reference products |
| R6 | Repo 7 — nominally the "richest agentic source" — **contains no Bedrock at all** (self-hosted Ollama on GPU Karpenter) and its LangGraph code is partly non-functional | The entire Bedrock, checkpointer, guardrails, RAG, eval, MCP and observability layer is greenfield | Accepted and planned for; only the *patterns* and domain model were harvested |

[#42147]: https://github.com/hashicorp/terraform-provider-aws/issues/42147
[#36845]: https://github.com/hashicorp/terraform-provider-aws/issues/36845
[#39948]: https://github.com/hashicorp/terraform-provider-aws/issues/39948

---

## Open questions

| # | Question | Needed by | Owner |
|---|---|---|---|
| Q1 | Exact Canada DID per-day and inbound per-minute rate | Phase 2 cost model | Read from Cost Explorer under the service key **`Contact Center Telecommunications (service sold by AMCS, LLC)`** — verified present but at $0.00 as of 2026-08-11, since the number was claimed the same day. Re-read after ≥1 full day of accrual. **Still open** — Cost Explorer needs ≥1 day of accrual, not yet available |
| Q2 | Does `us.anthropic.claude-haiku-4-5` earn its cost over `us.amazon.nova-lite` on the generation node? | Phase 6 | Decided by evals, not preference. `ADR-004` fixes the mechanism (feature-flagged) and prunes Claude 3 Haiku from the matrix, but **does not pre-decide the winner** — still open, as intended |
| ~~Q3~~ | ~~Claim-number format~~ | **RESOLVED** by `docs/phase3/DATA-CONTRACTS.md` | `CLM-YYMM-NNNNN-C`, digits-only (not the Phase 0 draft's alphanumeric idea — refined for DTMF-fallback compatibility), Luhn mod-10 check digit. Worked example: `CLM-2608-00042-4` |
| ~~Q4~~ | ~~Vector store choice~~ | **RESOLVED** by `ADR-002` | DynamoDB + in-process brute-force cosine similarity, not S3 Vectors, not FAISS-in-Lambda — with an explicit corpus-size threshold for revisiting |
| ~~Q5~~ | ~~Deductible logic, total-loss threshold and injury-severity→coverage mapping have no prior art~~ | **RESOLVED** by `data/synthetic/policy/coverage-logic.md` | Deductible formula, 80%-of-ACV total-loss rule (stated explicitly, not implied), and the KABCO-vs-SABS severity-track boundary, all with worked examples |
| ~~Q6~~ | ~~Lexical injury detection will miss novel phrasings~~ | **RESOLVED** by D15 | Layered L1+L2+L3 detection committed as an architectural requirement; recall gate split into a labelled-set GATE and a held-out OBSERVED measure |
| Q7 | Does the reranker earn its latency against the 1,800 ms budget? | Phase 6 | Measured, not assumed — recall@5 gain vs added p95 |
| ~~Q8~~ | ~~Where does the safety pre-node sit relative to Guardrails input filtering?~~ | **RESOLVED** by `ADR-010` | Verified: `ApplyGuardrail`/`InvokeGuardrailChecks` run decoupled from model invocation — L1 sequenced first by never attaching `guardrailIdentifier` to a model call |
| Q9 | Free-text location redaction is genuinely hard — "right outside my kids' school on Maple" embeds a location a location-entity redactor may miss | Phase 7 | Reported as a limitation, not claimed as solved. Bounded by the fact that structured capture already holds the authoritative value. Restated in `ADR-011` |
| ~~Q10~~ | ~~L2's per-turn classifier must not be switchable off by the model-tier feature flag~~ | **RESOLVED** by `ADR-004` | L2 is merged into the fixed-tier routing call (Nova Micro, never flag-controlled); the generation-tier flag lives in a separate namespace with no code path to the safety call |
| ~~Q11~~ | ~~Should the Connect instance switch from "Connect Customer" to "Connect Customer Basic"?~~ | **RESOLVED AND DONE — 2026-08-11.** Instance-level toggle, not fixed at creation, no DID risk, console-only (no IaC path); recorded as the fourth CLAUDE.md-permitted manual step, `docs/runbooks/MANUAL-STEPS.md`. **Marco executed the switch via the console and confirmed by screenshot** — `marcos-ivr-demo` now runs Connect Customer Basic. The documented console path was corrected against the actual screenshot (nav item is "Customer" not "Connect Customer"; action is a "Change" button on the "Confirm Amazon Connect Customer" card, not "Disable"). Live worst case is now ≈$14–16/mo at 100 calls/month vs. ≈$21–23/mo pre-switch — the ceiling margin is real, not thin |

---

## Phase 2 — required ADRs

All eleven **accepted** 2026-08-11. ADRs are immutable once accepted; supersede, never edit. Full text in
`docs/adr/`.

| ADR | Decision | Notes |
|---|---|---|
| ADR-001 | Lex V2 remains turn-manager; Bedrock via LangGraph codehook — not Nova Sonic S2S, not Connect Customer's managed agentic bundle, not a hand-rolled streaming pipeline | Both live 2026 alternatives (Nova Sonic S2S, Connect Customer's ACXD) assessed on the merits and rejected — the first as scoped/reversible, the second on portfolio-intent grounds, not primarily cost |
| ADR-002 | Vector store — DynamoDB + in-process brute-force cosine, not S3 Vectors, not FAISS-in-Lambda | Resolves Q4. Explicit corpus-size threshold stated for revisiting; avoids conflicting with `ADR-009`'s package-size-first cold-start posture |
| ADR-003 | LangGraph orchestrates the agent | Bedrock Agents Classic confirmed **closed to new customers** as of today — not a live option regardless of technical merit. AgentCore rejected on regional fragmentation (`ADR-008`) and framework fit |
| ADR-004 | Fixed Nova Micro for a **merged** routing+L2 call (forced tool-use); feature-flagged Nova Lite/Claude Haiku 4.5 for generation only, winner left to Phase 6 evals | Resolves Q10 structurally — the safety call has no code path to the generation-tier flag. Claude 3 Haiku pruned from the eval matrix (dominated on both cost and quality) |
| ADR-005 | **Adopt `langgraph-checkpoint-aws`'s DynamoDB backend, not a hand-written `BaseCheckpointSaver`** | **Corrects the Phase 0/1 carried-forward assumption** that no maintained DynamoDB checkpointer existed — one now does (`langchain-ai`-org maintained, DynamoDB + S3 overflow). A checkpoint-deserialization CVE chain (CVE-2026-28277) was found and run down: confirmed to affect SQLite/Redis backends only, already patched in the `langgraph` version this project pins; `LANGGRAPH_STRICT_MSGPACK` adopted as defense-in-depth regardless |
| ADR-006 | Post-call processing is fully async, triggered by Connect's `DISCONNECTED`/`COMPLETED` EventBridge contact events (not Contact Lens) | Single Lambda + SQS DLQ, not Step Functions, at current pipeline complexity. Best-effort event delivery accepted as a risk since nothing safety-critical depends on this path |
| ADR-007 | Nested CFN `AWS::Lex::Bot` wrapped by Terraform's `aws_cloudformation_stack`; native `aws_lexv2models_*` and CDK both rejected | Resolves R1. Two of three previously-flagged provider bugs confirmed still open (#42147, #39948); one confirmed fixed (#36845). Mandatory Phase 8 POC carried forward for one unconfirmed CFN gap |
| ADR-008 | `us-west-2` retained; `ca-central-1` and AgentCore formally rejected; residency caveat on `us.*` cross-region inference documented, not glossed over | `us.*` profiles called from `us-west-2` can process in `us-east-1`, per AWS's own docs — accepted (synthetic data, CloudTrail-audited), not eliminated |
| ADR-009 | Cold-start order: smaller package → **Python SnapStart** (confirmed available, GA Nov 2024) → scheduled warmer (documented fallback) → provisioned concurrency (cost-gated last resort) | Corrects the assumption that SnapStart was Java-only. Hard constraint found: SnapStart and provisioned concurrency are mutually exclusive on the same function |
| ADR-010 | **L1 runs before Guardrails input filtering — implemented by never attaching `guardrailIdentifier` to a model call; `ApplyGuardrail` driven explicitly, sequenced after L1** | Resolves Q8. Verified this is the AWS-documented decoupled pattern, not a workaround fighting the platform |
| ADR-011 | PII redaction boundary formalised: two-layer redaction (in-call deterministic+Guardrails, then async cross-turn defense-in-depth) | Formalises D16. Explicitly reverses one named piece of Phase 0 guidance ("`DATE_TIME` must NOT be blanket-redacted") — reversal stated, not left implicit |

### Other Phase 2 requirements

- **Cost model assumes zero free tier and zero credits** — ✅ `docs/phase2/COST-MODEL.md`. Surfaced a material finding along the way: **Amazon Connect now prices "Connect Customer" ($0.038/min) separately from "Connect Customer Basic" (~$0.0202/min)** — this project's architecture (`ADR-001`) doesn't use Connect Customer's bundled AI, making Basic the tier that matches actual usage. Flagged as **Q11**, not executed.
- **Rental/towing is core scope, not a gap.** (Phase 1, carried forward, unchanged.)
- ✅ Mermaid architecture diagram — `docs/phase2/ARCHITECTURE.md`, including the per-turn safety-ordering sequence diagram `ADR-010` requires be visible.
- ✅ Full cost model with free-tier table and per-resource teardown-risk column — `docs/phase2/COST-MODEL.md`.
- ✅ Threat model covering prompt injection, tool abuse, PII leakage, toll fraud and denial-of-wallet, seeded by `docs/phase0/SECURITY-FINDINGS.md` — `docs/phase2/THREAT-MODEL.md`. Each threat class maps to a specific ADR/decision, not a narrative assurance.
- **Not yet done, and deliberately not attempted before sign-off:** propose `.claude/skills/ai-sdlc-phase-gate/SKILL.md` — this is explicitly a **post**-sign-off action per the existing plan, so it is not attempted here.

---

## Session log

### 2026-08-11 — Phase 0
- Read all eight source repos via three parallel archaeology agents. Produced merge matrix (100 modules: 20 KEEP / 22 REFACTOR / 5 REWRITE / 53 DISCARD — 53% by module count, 58% counting REWRITE, ~97% by LOC — both framings reported and justified per row), dependency conflict report, domain artifact inventory, security findings, target layout.
- Verified live environment rather than trusting the brief: confirmed the Connect instance and, notably, that **the DID is Canadian (`CountryCode: CA`), not US** — the assumed US rates do not apply.
- Extracted the **modern recording-block ground truth** from the instance's own `Sample recording behavior` flow: the 2019-10-30 schema has no `RecordingBehaviorOption`; recording state is the `RecordedParticipants` array, empty = off. The constraint-18 CI check is now written against verified JSON rather than a guess.
- Confirmed Bedrock inference profiles and that `amazon.nova-micro-v1:0` is **`INFERENCE_PROFILE`-only**, making constraint 17's `us.*` rule mandatory rather than stylistic.
- Discovered R1 (Terraform Lex V2 provider bugs) and R3 (free-tier replacement) — both materially change Phase 2.
- Scaffolded workspace: `CLAUDE.md`, `PROJECT_STATE.md`, `.claude/settings.json`, `docs/phase0/*`, `.gitignore`, `CHANGELOG.md`, `README.md`.
- **No application code written. No billable resource created. $0.00 new spend.**
- Marco re-tagged the DID to `Project=AWS-Insurance-FNOL-Voice-Agentic-AI`, `Owner=marcos`, `Protected=true`; recorded above and wired into the Phase 8 import guard.
- Marco ruled that commit `210b875` stands and that verification item 1 be recorded as knowingly violated rather than marked passed (D10). Added the out-of-`PROJECT_ROOT` scope rule to `CLAUDE.md` (D9) — three known future instances, **none pre-approved**.
- **`APPROVED: Phase 0`.**

### 2026-08-11 — Phase 1
- Wrote `docs/phase1/{PROBLEM-FRAMING,AI-USE-CASE-CARD,SUCCESS-METRICS}.md`. **No code, no spend.**
- Specified exactly six intents with slots, success criteria and explicit failure definitions. `FileAutoClaim` carries 11 slots and one conditional; safety precedes collection.
- Defined containment so it cannot be gamed (D13) and recorded an anti-gaming table covering six routes by which this metric set could be satisfied while the system got worse.
- Made injury detection a deterministic pre-node rather than a classified intent (D12), which is what makes a 100% recall gate structurally achievable.
- Anchored non-goals on the Phase 0 authority matrix: $0 settlement authority, cannot deny, never adjudicates. **AI advises; a licensed human decides.**
- Surfaced Q6–Q8, including an **ordering constraint discovered while writing the metrics**: a Guardrails input filter that blocks a graphic injury description *before* the safety node sees it would be a critical bug. Safety detection must run first — this now binds the Phase 2 architecture.
- Named the system's most serious residual risk plainly in the use-case card (lexical injury detection missing novel phrasings) rather than implying it is solved.
- **`APPROVED: Phase 1`**, with two corrections applied the same day:
  1. **Q6 resolved rather than deferred (D15).** The unqualified "100% recall" gate was unachievable and therefore dishonest. Split into a labelled-set GATE — enforceable to zero via fix-and-re-run because detection is deterministic, which makes a labelled failure a debuggable *code defect* rather than a stochastic shortfall, **not** a claim that the mechanism is infallible — and a held-out novel-phrasing measure reported with no threshold. Layered L1+L2+L3 detection with union semantics committed as an architectural requirement.
  2. **D14 superseded by D16.** The exemption had only a utility argument. Adding the re-identification argument changed the design: date + time + location is a quasi-identifier close to uniquely identifying, so **both** fields now get identical treatment — retained in the structured claim record, redacted from transcripts and logs. Splitting a quasi-identifier across two policies protects nothing.
- Q8 promoted from an open question to **required ADR-010** at Marco's instruction — safety-detection ordering is architecture, not an implementation note.
- Recorded the Phase 2 ADR list (11 ADRs) and Phase 2 requirements, incl. a **three-way** IaC comparison (ADR-007) so the Phase 0 proposal is not pre-decided, a zero-free-tier cost model, and rental/towing reframed as **core scope rather than a gap**.
- ⚠ Flagged to Marco that three items he referred to as "sent earlier" (zero-free-tier cost model, three-way Lex IaC ADR, rental/towing not a gap) do **not** appear anywhere in this session's history. Proceeding on a stated reconstruction rather than pretending receipt; awaiting correction.

### 2026-08-11 — Phase 2 (in progress)
- Marco confirmed all three reconstructed items were correct, and separately corrected the framing of D15/Q6's labelled recall gate: "achievable by construction" overclaimed — deterministic detection makes a labelled failure *debuggable and fixable*, not *impossible*, since an incomplete lexicon can still miss a labelled case. Corrected in `SUCCESS-METRICS.md` (×2), `AI-USE-CASE-CARD.md` (F1 row), and this file's own Phase 1 log entry — commit `dae2de5` plus this session's edits. Precise claim now stated: enforceable-to-zero-on-a-closed-set via fix-and-re-run, not infallible-on-first-write.
- Corrected a stale "84% discard" figure in this file's own Phase 0 log entry (line 241) that had already been superseded elsewhere in the same document but never fixed at that specific line — now reads the same 53%/58%/97% figures as the exit-criteria table above it.
- **Marco instructed: "Proceed with Phase 2, ADR-008 and ADR-007 first."** Launched two parallel background research agents rather than relying on memory (per `CLAUDE.md`'s "verify against current AWS sources, never from memory" rule) — one for region-selection facts (AgentCore region tiers, `us.*` cross-region routing/residency, `ca-central-1` support matrix), one for Terraform Lex V2 provider bug status (issues #42147/#36845/#39948, provider version, CDK L1-vs-L2 support, CFN `AWS::Lex::Bot` known limitations). Both completed with sourced, dated findings.
- **Accepted `docs/adr/ADR-007-iac-tool-selection.md`.** Nested CFN `AWS::Lex::Bot` wrapped by Terraform's `aws_cloudformation_stack`, chosen over native `aws_lexv2models_*` (two of three provider bugs confirmed still open, including a structural intent↔slot cycle with no fix in sight) and over CDK (forbidden by existing constraint, and on the merits has no L2 construct for Lex V2 — functionally identical to CFN authorship). Disclosed openly that the chosen option's advantage rests on *absence of a confirmed defect*, not positive confirmation, and carried a mandatory Phase 8 proof-of-concept forward to close that gap before real provisioning.
- **Accepted `docs/adr/ADR-008-region-selection.md`.** `us-west-2` retained for Connect/Lex/Lambda/DynamoDB/S3/Step Functions; Bedrock via `us.*` unchanged. Documented, rather than glossed over, that a `us.*` profile called from `us-west-2` can be processed in `us-east-1` per AWS's own docs — accepted because the data is synthetic and audited via CloudTrail's `inferenceRegion` field, not eliminated. Formally rejected `ca-central-1` (no technical gap, but the CA DID is a telephony attribute, not a residency driver — no requirement exists to justify moving) and Bedrock AgentCore (region-tiered feature fragmentation, corroborating the existing LangGraph-over-AgentCore choice).
- **No application code, no Terraform, no billable resource created. $0.00 new spend.**

### 2026-08-11 — Phase 2 (continued): all remaining ADRs, architecture, cost model, threat model

- Marco typed `APPROVE Phase 2` — flagged rather than accepted at face value, for two reasons: it doesn't
  match the STOP CONDITIONS' exact required phrase (`APPROVED: <phase name>`), and Phase 2 was nowhere near
  done at that point (2 of 11 ADRs, no diagram/cost model/threat model, no exit-criteria table). Asked via
  `AskUserQuestion`; Marco confirmed intent was **"keep working — not a sign-off."** Proceeded on that basis.
- Launched three parallel background research agents rather than relying on memory: (1) Bedrock model/Guardrails
  pricing and call semantics, Bedrock Agents Classic capability check; (2) Lambda cold-start/SnapStart language
  support and the LangGraph checkpointer ecosystem; (3) a full per-service AWS pricing sweep for the cost model.
  All three completed with sourced, dated findings; none asserted from memory.
- **Drafted and accepted the remaining nine ADRs** (ADR-001, 002, 003, 004, 005, 006, 009, 010, 011), bringing
  all 11 required ADRs to accepted status. Notable findings surfaced along the way, not assumed:
  - Amazon Connect now offers Nova Sonic Speech-to-Speech and a broader "Connect Customer" agentic-AI bundle
    (enabled by default on all new instances, including ours) — both real 2025–2026 alternatives, both
    assessed and rejected in `ADR-001`, the second explicitly on portfolio-intent grounds rather than cost.
  - **`ADR-005` corrects a carried-forward Phase 0/1 assumption**: a maintained DynamoDB LangGraph checkpointer
    (`langgraph-checkpoint-aws`) now exists and is adopted instead of hand-writing one. A real CVE chain
    (CVE-2026-28277, checkpoint-deserialization RCE) was found in the same search and run down rather than
    cited uncritically — confirmed to affect only SQLite/Redis backends, already patched in the pinned
    `langgraph` version, with `LANGGRAPH_STRICT_MSGPACK` adopted as defense-in-depth regardless.
  - **`ADR-009` corrects the assumption that Lambda SnapStart is Java-only** — Python 3.12 support GA'd
    November 2024. Hard constraint found and designed around: SnapStart and provisioned concurrency are
    mutually exclusive on the same function.
  - **`ADR-010` resolves Q8 with a verified mechanism**, not just a stated intention: Bedrock's `ApplyGuardrail`
    API is confirmed decoupled from model invocation, so L1-before-Guardrails is implemented by never attaching
    `guardrailIdentifier` to a model call and driving Guardrails explicitly, sequenced after L1.
  - **`ADR-003` confirms Bedrock Agents Classic is closed to new customers** as of today — moot as an
    alternative regardless of technical merit; corroborates the existing LangGraph choice.
  - **`ADR-004`** merges the per-turn router and L2 safety classifier into one forced-tool-use Nova Micro call,
    fixed and never flag-controlled, resolving Q10 structurally rather than by convention; prunes Claude 3
    Haiku from the Phase 6 eval matrix as strictly dominated.
  - **`ADR-002`** chooses DynamoDB + in-process brute-force cosine over S3 Vectors and FAISS-in-Lambda, with an
    explicit corpus-size revisit threshold — resolves Q4.
  - **`ADR-006`** makes post-call processing fully async off Connect's native `DISCONNECTED`/`COMPLETED`
    EventBridge contact events (confirmed distinct from the banned Contact Lens), single Lambda + SQS DLQ.
- **Corrected `CLAUDE.md`'s Bedrock pricing table** — Nova Micro/Lite were both materially overstated in the
  original figures; corrected, with Claude Haiku 4.5 and Titan Embed v2 pricing added, all re-verified live.
- **Wrote `docs/phase2/COST-MODEL.md`.** Surfaced a material, previously-unknown finding: Amazon Connect now
  splits into "Connect Customer" ($0.038/min, the default on our instance) and "Connect Customer Basic"
  (~$0.0202/min, no bundled AI) — since this project doesn't use the bundled AI (`ADR-001`), Basic is the
  tier that matches actual usage and would roughly halve the dominant cost line. **Flagged as Q11, not
  executed** — recorded as Marco's decision, including whether the switch is even IaC-expressible.
- **Wrote `docs/phase2/ARCHITECTURE.md`** — full system Mermaid diagram plus the per-turn safety-ordering
  sequence diagram `ADR-010` requires be visible in the architecture, not buried in code.
- **Wrote `docs/phase2/THREAT-MODEL.md`** — seeded from `docs/phase0/SECURITY-FINDINGS.md`'s observed failure
  modes, covering prompt injection, tool abuse, PII leakage, auth bypass, toll fraud, denial-of-wallet, and
  supply chain, each mapped to a specific ADR/decision with residual risk stated honestly, not narrated away.
- **Added a Phase 2 exit-criteria table** (see above), mirroring the Phase 0/1 pattern the earlier
  clarifying question had noted was missing. **Not self-marked as signed off** — presented for Marco's
  explicit `APPROVED: Phase 2`, consistent with the STOP CONDITIONS restated at the top of every session.
- **No application code, no Terraform apply, no billable resource created. $0.00 new spend throughout.**

### 2026-08-11 — Phase 2 signed off; Q11 mechanism resolved; cost-ceiling verdict stated

- **Marco typed `APPROVED: Phase 2`** — the exact STOP CONDITIONS phrase this time. Phase 2 exit-criteria
  item 12 marked ✅. Phase 2 is complete. **Phase 3 has not begun** — no exit criteria written for it, no
  approval given; nothing beyond this entry proceeds without that.
- Alongside sign-off, Marco gave two explicit conditions before any Q11 action: **research the tier-switch
  mechanism from AWS documentation first**, and **do not change the tier on the protected instance without
  explicit approval by name.** Both honored — no console or API action taken against the live instance.
- **Q11 mechanism resolved**, via a live fetch of
  `docs.aws.amazon.com/connect/latest/adminguide/enable-nextgeneration-amazonconnect.html`: the Connect
  Customer / Customer Basic tier is an **instance-level toggle** ("Enable Connect Customer across your
  entire instance" → Enable/Disable), **not fixed at creation**. Switching does **not** require a new
  instance and carries **no DID release/re-claim risk** — Marco's stated blocking concern does not apply.
  However, it **is console-only**: neither the `UpdateInstanceAttribute` API's documented attribute types
  nor Terraform's `aws_connect_instance` resource cover this toggle. This makes the switch a **new
  manual-step candidate outside the three CLAUDE.md-permitted manual steps** (instance, admin user, DID) —
  named explicitly rather than treated as a routine config change, since it touches the protected instance.
  Recorded in `PROJECT_STATE.md` Q11 and `docs/phase2/COST-MODEL.md`. **The switch itself remains
  unexecuted, pending Marco's named approval of this specific console action.**
- **$25 ceiling verdict stated plainly in `docs/phase2/COST-MODEL.md`**, not left implicit in the scenario
  tables: the ceiling **holds** under the zero-free-tier assumption already baked into the cost model from
  its first line, on both pricing tiers, at both modeled volumes (20 and 100 calls/month) — worst case is
  ≈$21–23/mo (Customer tier, 100 calls), ≈$2–4 of headroom. The one still-open input that could move this
  (Q1, the exact Canada DID rate, pending Cost Explorer accrual) is called out by name as the one thing that
  could change the verdict, rather than leaving that caveat buried in a table.
- No application code, no Terraform apply, no billable resource created, no console action taken. $0.00 new
  spend.

### 2026-08-11 — Q11 approved and documented as 4th manual step; cost-ceiling re-stated post-switch; Phase 3 exit criteria proposed

- **Marco approved the Connect Customer Basic switch by name**, to be done via the console, and asked it be
  documented as a **fourth permitted manual step** with the `ADR-001` reasoning (this project deliberately
  doesn't use Connect Customer's bundled AI, so Basic matches actual usage) — and asked the cost model note
  explicitly that the pre-switch Customer tier was the unexamined instance-creation default, not a choice
  this project made.
- **Created `docs/runbooks/MANUAL-STEPS.md`** (the runbook `CLAUDE.md` already referenced but that didn't
  yet exist) — all four permitted manual steps in one place: instance, admin user, DID (all pre-existing,
  no action), and the new tier switch with its exact six-step console path, rollback note, and post-switch
  verification step. **Updated `CLAUDE.md`'s "Only permitted manual steps" line** to name the fourth step
  and point at the runbook, keeping the constraint document and the procedure doc in sync.
- **Claude does not have AWS console/browser access in this session** — no MCP tool here provides
  interactive console UI actions, and the API surface (`aws-mcp`) doesn't expose this toggle either (same
  finding as Q11's original research). Stated this plainly in the runbook rather than attempting a workaround;
  **Marco performs the six console steps directly**, matching his stated preference on a protected resource.
  **The switch has not been executed by either party as of this entry** — runbook and cost model describe it
  as approved and ready, not as done.
- **Cost model updated**: the pre-switch Customer-tier figures are now labeled explicitly as reflecting an
  unexamined default rather than a decision. Added the recalculated post-switch worst case (**≈$14–16/mo at
  100 calls/month, ≈$9–11 of headroom**, roughly 3x the pre-switch ≈$2–4) as the number that actually creates
  usable margin against Q1 (Canada DID rate) still being open — matching Marco's instruction to treat the
  switch as margin-creating, not a nice-to-have.
- **Proposed Phase 3 exit criteria** (see table above) — data engineering and knowledge base scope: synthetic
  policy corpus, rental/towing sections with zero prior art (`R5`), deductible/total-loss/injury-severity
  logic (`Q5`), claim-number format (`Q3`), policyholder/vehicle/claim records, ingestion pipeline into
  `ADR-002`'s DynamoDB vector store, and a data card. **Not started** — presented for Marco's
  `APPROVED: Phase 3`, per the STOP CONDITIONS, same as every prior phase.
- No application code, no Terraform apply, no billable resource created, no console action taken by Claude.
  $0.00 new spend.

### 2026-08-11 — Tier switch confirmed done; runbook corrected against real console; `APPROVED: Phase 3`

- **Marco executed the Connect Customer Basic switch and confirmed it with a screenshot**: the instance
  `marcos-ivr-demo`'s Customer page shows the banner *"This instance is now Amazon Connect Customer Basic -
  some capabilities may no longer be available"* and the **Confirm Amazon Connect Customer** card shows
  **Amazon Connect Customer Basic** selected. Marked done in `docs/runbooks/MANUAL-STEPS.md`, `PROJECT_STATE.md`
  Q11, and `docs/phase2/COST-MODEL.md`.
- **Corrected the documented console path against the real UI**, per Marco's explicit instruction not to let
  the predicted path stand uncorrected: the left-nav item is **"Customer"**, not "Connect Customer" as the
  cited AWS doc page's own labels implied; the action is a **"Change"** button on a **"Confirm Amazon Connect
  Customer"** card, not the "Disable" button the doc page described. `docs/runbooks/MANUAL-STEPS.md` now
  carries the corrected path, with the one still-unobserved step (the tier-selection prompt after "Change")
  explicitly labeled as inferred, not confirmed — not papered over as fact.
- **`docs/phase2/COST-MODEL.md` updated to make the Basic-tier figures the active/live numbers** throughout
  (per-conversation cost, scenario table, ceiling verdict), with Customer-tier figures relabeled as
  historical-only. Live worst case: **≈$14–16/mo at 100 calls/month, ≈$9–11 headroom** under the $25 ceiling —
  roughly 3x the pre-switch margin, resolving Marco's "not comfortable" concern about the pre-switch $2–4
  headroom against Q1 still being open.
- **Marco typed `APPROVED: Phase 3`** — the exact STOP CONDITIONS phrase. Phase 3 (data engineering and
  knowledge base) is now **in progress**. Phase status table and header updated accordingly.
- No application code yet written this entry; no Terraform apply; no billable resource created beyond what
  was already approved (the $5 Bedrock standing cap, untouched so far). $0.00 new spend.

### 2026-08-11 — Ontario-specific policy corpus authored; resolves Q5, R5

- **Marco redirected the policy corpus from generic North American to Ontario-specific**, before coverage
  values were locked: OAP 1 structure, Accident Benefits as a distinct mandatory coverage, DCPD, $500/$1,000
  deductibles, an explicit stated total-loss rule, and rental as an optional endorsement with a daily cap and
  day limit. Explicit instruction: where Ontario specifics complicate the six intents, name the simplification
  rather than silently generalizing.
- **Researched live rather than from memory** (multiple `WebSearch`/`WebFetch` passes): OAP 1's six-section
  structure (3 Liability, 4 Accident Benefits, 5 Uninsured Auto, 6 DCPD, 7 Loss or Damage, 8 Statutory
  Conditions); SABS benefit caps (MIG $3,500, non-catastrophic $65,000, catastrophic $1,000,000; IRB 70%/
  max $400/week/104 weeks); Ontario Fault Determination Rules (O. Reg. 668, fixed 0/25/50/75/100% bands);
  real OPCF 20 (rental) and OPCF 35 (roadside) reference terms; Ontario's insurer-discretion total-loss
  threshold (no single legislated %, typically 70–80% ACV).
- **Caught a live regulatory change memory would have missed**: Ontario's SABS reform took effect
  **2026-07-01** — five weeks before this session — making Income Replacement, Caregiver, Housekeeping/Home
  Maintenance, Dependent Care, Death & Funeral, and Indexation benefits **optional elections** rather than
  automatically bundled. Corroborated across multiple independent sources (FSRA's own page 403'd on direct
  fetch, corroborated via RIBO, law firms, insurance-broker publications). Reflected as the corpus's current
  state, not the pre-reform assumption a training-data-only answer would have given.
- **Named three deliberate simplifications explicitly, per Marco's instruction not to smooth them over**:
  (1) fault-percentage apportionment (O. Reg. 668) is never computed by the agent — intake, not adjudication;
  (2) no synthetic policyholder has opted out of DCPD (OPCF 49); (3) intent 4's "towing" is the accident-scene
  allowance bundled into the DCPD/Collision claim itself, not OPCF 35's separate non-accident roadside product
  — named, not built.
- **Created:**
  - `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` — verified grounding, citations, all named simplifications
  - `data/synthetic/policy/example-mutual-oap-policy-wording.md` — the OAP-structured policy wording (main
    `CoverageQuestion` RAG corpus), explicitly labeled as original synthetic wording, not a reproduction of
    FSRA's copyrighted OAP 1 form
  - `data/synthetic/policy/coverage-logic.md` — resolves `Q5`: deductible arithmetic, 80%-of-ACV total-loss
    formula (Example Mutual's own stated rule, since Ontario sets no single legislated %), and the KABCO-
    vs-SABS injury-severity boundary (scene severity vs. clinical benefit-eligibility tier — kept distinct,
    with an explicit statement that the agent never performs the clinical determination)
  - `data/synthetic/policy/endorsements.md` — resolves `R5`: rental (OPCF-20-modeled, $50/day, 20-day/$1,000
    cap, with a worked days-remaining example anchoring intent 4's compound RAG+tool case) and towing (bundled
    $150/incident allowance, not a separate endorsement)
- No application/agent code written (data-engineering/content authoring only, per Phase 3's own exit
  criterion 10). No billable resource created. $0.00 new spend.

### 2026-08-11 — Optional-benefit entitlement policy decided; citation audit catches and fixes a real error

- **Marco asked two things before records: (1) decide how the agent answers "am I entitled to X" for the
  now-optional SABS benefits, baked into record variation; (2) verify every citation in
  `ONTARIO-INSURANCE-REFERENCE.md` actually resolves, since FSRA had 403'd on direct fetch and a broken
  citation on a regulatory claim in a public repo is worse than none.**
- **Decision on (1), `data/synthetic/policy/coverage-logic.md` §4**: reframed the question — the split isn't
  by benefit type (mandatory vs. optional), it's by **question type**. "Is X part of my coverage" is an
  election-fact lookup, answered from the structured policyholder record (mandatory coverages: pure RAG,
  true for everyone; optional elections: RAG+tool, since the answer varies by policyholder — a new scope
  note that `CoverageQuestion` isn't pure-RAG for every sub-question, flagged for Phase 4/5). "Will I actually
  get paid, and how much" is always deflected to a human, regardless of benefit type, since it depends on a
  clinical/fault/repair-estimate determination this agent never makes anywhere else in the architecture either.
- **Verification on (2) — actually tested with `curl`, not re-trusted from search-engine summaries.** Found
  and fixed a real error in the process, not just added citations after the fact: the corpus claimed **"no
  deductible applies to a DCPD claim"** as an absolute rule. FSRA's own page (fetched successfully via `curl`
  with a browser user-agent, where `WebFetch` had been blocked) states verbatim: *"Some policies don't have a
  direct compensation property damage deductible, but you can add one to lower your premium."* Corrected in
  `example-mutual-oap-policy-wording.md` and `coverage-logic.md` §1 — DCPD is deductible-free in this corpus
  **by construction** (no synthetic policyholder added the optional deductible), not by universal regulatory
  default.
- **Also caught: one candidate citation (`fsrao.ca/media/5156/download`, the actual OAP 1 PDF) returned HTTP
  200 but an "Access denied" body** — a genuine false-positive that a status-code-only check would have
  missed. Flagged this explicitly as the discipline point: **a 200 status was not treated as proof of a
  working citation anywhere in this audit.**
- **`docs/phase3/ONTARIO-INSURANCE-REFERENCE.md` §8 (new)**: a full per-claim citation-grade table (🟢
  primary+quoted / 🟡 primary URL resolves but client-rendered, unreadable to automated fetch / 🔴 secondary
  sources only / ⚫ tested and broken). **Honest net finding, stated plainly rather than smoothed over**: the
  two most consequential claims — OAP 1's section numbering and the exact SABS dollar caps — rest on the
  *weakest* citation grade, because the two strongest primary sources for them (the OAP 1 PDF, and CanLII's
  regulation mirror) were both tested and found inaccessible to automated verification (CanLII: HTTP 403 and
  a bot-detection challenge even with full browser headers). What *did* verify cleanly and get directly
  quoted: the $200,000 TPL minimum, DCPD's mechanics including the deductible correction, and the July 2026
  SABS reform itself — all confirmed against FSRA's own live pages.
- **As-of-date warning added prominently** at the top of `ONTARIO-INSURANCE-REFERENCE.md`, flagged to also
  appear in the still-pending data card (task 6): this document reflects a regulatory reform five weeks old
  at time of writing and will go stale on Ontario's own schedule, independent of this project.
- No application/agent code written. No billable resource created. $0.00 new spend.

### 2026-08-11 — Reframed the two weakest-cited claims as corpus construction choices, not regulatory fact

- **Marco: the 🔴 secondary-only claims (SABS caps, OAP 1 section numbering) are exactly what a knowledgeable
  reader checks first — restate them as corpus construction choices rather than unverified regulatory
  assertions, keep §8's grading table exactly as-is.** Done: `docs/phase3/ONTARIO-INSURANCE-REFERENCE.md`
  §1 and §3 rewritten with an explicit "corpus parameters, not verified regulatory citations" framing
  (Marco's own suggested language, used near-verbatim for the SABS caps). §8's grading table is unchanged.
  The document's opening paragraph updated to match — it no longer implies uniform verification across every
  claim below it.
- This keeps the structural fidelity that made the corpus worth building while removing any claim the repo
  can't back — ground truth for Phase 6 evals is the corpus's own internal consistency, not an assertion that
  every dollar figure matches current Ontario regulation exactly.
- No application/agent code written. No billable resource created. $0.00 new spend.

### 2026-08-11 — Synthetic policyholder/vehicle/claim records generated and machine-validated

- **6 policyholders, 7 vehicles, 8 claims** in `data/synthetic/{policyholders,vehicles,claims}/*.json`.
  Deliberate variation in the six 2026-07-01 optional SABS elections and the Section 7 (Loss-or-Damage)
  selection across policyholders — one has elected almost nothing beyond mandatory coverage (`PY1103`), one
  has multiple elections plus two vehicles (`PY4821`) — so `CoverageQuestion`'s election-fact-lookup path
  (`coverage-logic.md` §4) has real, differing ground truth for Phase 6 evals, not a uniform corpus.
- **Claims cover the full status range** (`Reported` not used yet, `UnderReview`, `RepairInProgress`,
  `Settled`, `Closed`) and the fault/coverage space (pure DCPD at 0% fault, mixed DCPD+Collision at 75%,
  single-vehicle 100%-at-fault total loss, single-vehicle 100%-at-fault repairable, two Comprehensive perils
  with no fault question at all). One claim (`CLM-2608-00042-4`) is built to exactly match
  `endorsements.md`'s rental worked example (12 of 20 days used, $400 of $1,000 remaining); one
  (`CLM-2607-00042-5`) exactly matches `coverage-logic.md`'s total-loss worked example ($16,000/$18,000 =
  88.9%, settlement $17,000).
- **Wrote and ran `scripts/validate_synthetic_records.py`** rather than hand-checking arithmetic — verifies
  every claim number's Luhn check digit, every VIN's check digit is deliberately (not accidentally) invalid,
  full referential integrity across the three files, and every claim's total-loss flag and settlement amount
  against `coverage-logic.md`'s formulas exactly. **All checks passed on the first fully-corrected run** —
  one dataset design error was caught and fixed *during* this process (an early draft reused a just-totaled
  vehicle for a second claim; fixed by giving that policyholder a second vehicle instead, which is now also
  a deliberate two-vehicle-policy test case). Script is checked into the repo, re-runnable, intended as a
  Phase 9/10 CI fixture check, not a one-off.
- No fatal/K-tier KABCO claims included as live scenarios — noted explicitly in the file header that L1
  hard-escalation fixtures belong to Phase 6/7's eval and red-team suites, not this baseline corpus. One
  KABCO A (suspected serious, non-fatal) claim included as a historical-record field only.
- All PII fabricated (555-exchange phones, `@example.com` emails, generic Ontario street addresses,
  placeholder-style names); no images. WMI `9SY` used for every VIN, unassigned per Phase 0/3 research.
- No application/agent code written (data generation + a standalone validation script, no agent/orchestration
  logic). No billable resource created. $0.00 new spend.

### 2026-08-11 — Data card written

- `docs/phase3/DATA-CARD.md` — as-of-date staleness warning carried verbatim at the top, per Marco's
  instruction that it needs to be visible wherever the corpus is described, not only upstream in
  `ONTARIO-INSURANCE-REFERENCE.md`. Organizes provenance per-document (what's 🟢-verified, what's a corpus
  construction choice restated in Marco's own suggested language, what has no external grounding at all) and
  per PII/image gates, without re-deriving the underlying citation grading — points to
  `ONTARIO-INSURANCE-REFERENCE.md` §8 as the authoritative source for that.
- Exit criterion 8 (Phase 3 exit-criteria table) marked done.
- No application/agent code written. No billable resource created. $0.00 new spend.

### 2026-08-11 — Ingestion pipeline: first application code in the repo

- **Marco's one requirement above defaults**: the pipeline must emit a MANIFEST per run (corpus file hashes,
  chunk count per document, embedding model ID and dimension, corpus as-of date), and `make ingest` must be
  idempotent — unchanged file hash means no re-embed, so re-running costs nothing. Also: the as-of date
  travels as chunk metadata and is retrievable, but the pipeline enforces nothing based on it — expiry
  behavior is explicitly Phase 13, not this phase.
- **Bootstrapped the Python project for the first time**: `pyproject.toml` (deps pinned: `boto3`, dev-only
  `pytest`/`moto`/`ruff`/`black`/`mypy`/`boto3-stubs`, each justified in a one-line comment per `CLAUDE.md`'s
  rule), `src/fnol_voice_agent/knowledge/` package, `tests/unit/`. **System Python was 3.13; `CLAUDE.md`
  requires `>=3.12,<3.13`** — found `pyenv`-managed 3.12.10 already on the machine and built the venv against
  that explicitly, rather than loosening the pin.
- **`src/fnol_voice_agent/knowledge/ingest.py`** — chunks the policy corpus, embeds it, writes to DynamoDB
  per `ADR-002`'s schema (single table, `CHUNK#<file>#<index>` and `STATE#<file>` items, no new AWS service).
  **Chunking strategy, documented in the module docstring as asked**: markdown section-based (split on `## `
  headings), with a secondary paragraph-boundary split for any section over 4,000 characters. Chosen over
  fixed-size sliding-window chunking because the corpus's own sections (Third Party Liability, Accident
  Benefits, DCPD...) are already the right retrieval granularity for `CoverageQuestion` — a fixed window
  risks splitting a table or a worked example in half. Verified live that AWS's own Titan Embed V2 guidance
  recommends exactly this ("logical segments, such as paragraphs or sections"), rather than assuming it.
  Rejected sentence-level chunking as too granular for this corpus's document size.
- **Two independent safety axes, both defaulting to zero-cost/zero-AWS**: `--embeddings {mock,bedrock}` and
  `--vector-store {local,aws}`. `make ingest` runs mock+local — deterministic fake vectors, an in-memory
  `moto` DynamoDB table, no credentials, no network. Real Bedrock/real DynamoDB require explicit flags and
  were **not** invoked this session — real DynamoDB would fail today regardless, since that table is Phase 8
  scope and doesn't exist yet.
- **Idempotency**: a `STATE#<relative_path>` item per source file stores its last-ingested SHA-256; a run
  recomputes each file's current hash and skips (no embed calls, no writes) any unchanged file. Documented
  one honest limitation: the default `moto` backend is in-memory and doesn't persist across separate CLI
  invocations, so cross-run skipping is only observable end-to-end against a persistent backend (`aws`, once
  provisioned) — the skip *logic* itself is fully exercised and tested within a single run regardless.
- **`MANIFEST` (Marco's requirement)**: written to `data/synthetic/.ingest-manifest.json` (gitignored — a
  generated artifact, never committed, per `CLAUDE.md`). Contains exactly the four required fields
  (per-file SHA-256 + chunk count, embedding model ID + dimension, corpus as-of date) plus run timestamp and
  backend label. Verified live: Titan Embed V2's default output dimension is 1024 (256/512 also available),
  cited rather than assumed.
- **TDD, for real this time**: wrote `tests/unit/test_ingest.py` alongside the implementation; one test
  (`test_chunk_markdown_drops_empty_chunks`) **failed on first run and caught a real bug** — a heading-only
  section (no body) wasn't actually empty text, because the heading line itself was still part of the
  chunk's text. Fixed by stripping the heading line into `section_title` only, not duplicating it into the
  chunk body (also saves embedding tokens on every chunk). All 8 tests pass after the fix.
  `ruff`/`black`/`mypy --strict` all clean (two real mypy findings fixed: untyped `dict` → `dict[str, Any]`,
  `boto3` stubs added as a dev dependency rather than suppressing the import-untyped error).
- **Ran the full pipeline against the real corpus**: 21 chunks across 3 files, correct hashes, correct
  as-of-date pulled from a new single-source-of-truth file (`data/synthetic/policy/corpus-metadata.json`).
  **Zero real AWS calls made** — created `COSTS.md` and logged this explicitly: $0.00 of the $5.00 Bedrock
  standing cap consumed. A real Titan Embed V2 run over this corpus would cost a small fraction of a cent
  (`$0.02/1M tokens`), but wasn't triggered without Marco's explicit go-ahead to spend real money, even
  pre-approved money.
- **`Makefile` created** — only genuinely functional targets (`ingest`, `test`, `lint`, `format`,
  `typecheck`); the Definition of Done's other canonical targets are deliberately absent until the phases
  that build what they need, rather than stubbed and labeled as if they work.
- All 12 Phase 3 exit-criteria rows now checked (see caveat above about item 12's wording). **Phase 3 content
  is complete — presented for Marco's closing sign-off, not self-marked closed.**

### 2026-08-11 — Phase 3 signed off; first real Bedrock call verifies the manifest's assumptions

- **Marco typed `APPROVED: Phase 3`**, then set one condition before Phase 4 opens: the pipeline had only
  ever run against `MockEmbedder` — the manifest's recorded model ID and dimension were asserted, never
  observed. Cost-gate approved explicitly: one real Titan Embed V2 call, one chunk, `us-west-2`, logged as
  the first real spend in `COSTS.md`.
- **Ran it** — real `bedrock-runtime.invoke_model`, `amazon.titan-embed-text-v2:0`, `us-west-2`, against the
  actual DCPD section chunk from `example-mutual-oap-policy-wording.md` (2,193 chars / 515 input tokens),
  using the already-built, already-tested `BedrockEmbedder` class unmodified — this was the real code path,
  not a throwaway script.
- **Findings, all confirmed rather than assumed:**
  - **Dimension**: response returned exactly **1024** floats — matches `TITAN_EMBED_V2_DIMENSION` and what
    the manifest has been recording all along. No mismatch.
  - **Normalization**: requested `"normalize": true`; the returned vector's L2 norm computed to
    **1.000000** — genuinely unit-length, not just labeled as such. This means a future Phase 5 retrieval
    implementation can safely use a plain dot product as a cosine-similarity shortcut (mathematically
    equivalent to full cosine similarity only when both vectors are already unit-normalized) — a real,
    now-verified option for `ADR-002`'s brute-force retrieval, not previously confirmed.
  - **Response shape**: `payload["embedding"]` parsed exactly as `BedrockEmbedder.embed()` already assumed —
    no code change needed. **New information, not previously known**: the real response also carries
    `inputTextTokenCount` (515, used for the cost calculation below) and an `embeddingsByType: {"float": [...]}`
    field mirroring the top-level `embedding` array exactly — likely there to support future non-float
    embedding types. Noted for whoever builds Phase 5's retrieval code; not currently consumed.
- **Cost logged in `COSTS.md`**: 515 input tokens × $0.02/1M = **$0.0000103** — the project's first real AWS
  spend. Bedrock standing-approval cap consumption: **$0.0000103 of $5.00**.
- **Phase 3 is now signed off.** Phase 4 has not begun — no exit criteria written, no approval given, per the
  STOP CONDITIONS.

### 2026-08-11 — Phase 4 exit criteria proposed

- **Marco asked Phase 4 be scoped with exit criteria**, with two things made explicit in the plan rather than
  discovered later:
  1. The `coverage-logic.md` §4 finding that `CoverageQuestion` is not pure-RAG for every sub-question
     (mandatory-benefit election facts: pure RAG; optional-benefit election facts: RAG+tool; eligibility/amount
     questions: always deflect) changes intent 3's dialogue policy and must be designed in Phase 4, not
     discovered while building Phase 5.
  2. The prompt library needs an explicit response-length discipline for voice: Nova Micro padded a one-word
     answer into a full sentence during Marco's own pre-flight testing, and every unnecessary clause spends
     Polly synthesis time against the 1,800ms p95 turn-latency budget. Length constraints must be a named part
     of the prompt spec, with tight-vs-relaxed turns distinguished by intent (slot confirmation vs. coverage
     explanation), not left as an implicit prompting habit.
- **Proposed exit-criteria table added above** (5 deliverables — `docs/phase4/{INTENT-TAXONOMY,SLOT-DESIGN,
  DIALOGUE-POLICIES,PROMPT-REGISTRY,PERSONA}.md` — mapped against all eight roadmap components: taxonomy,
  slots, utterances incl. adversarial, prompt registry, dialogue policies, barge-in/repair, persona,
  escalation triggers). Both of Marco's requirements are load-bearing criteria (3 and 9), not folded quietly
  into general scope. Carried forward, not re-litigated: R4 (zero prior art for barge-in/DTMF — this phase
  exists to close the design gap, Phase 9 still measures the real numbers), R1's residual CFN gap (stays
  Phase 8's), Q7/Q9 (stay Phase 6/7's), and D13 (escalation recall is a gate — the escalation-trigger table
  may not quietly narrow recall to improve containment optics).
- **No application/agent code written this entry** — the table itself is the only artifact. No billable
  resource created. $0.00 new spend. **Phase 4 has not started** — presented for Marco's `APPROVED: Phase 4`,
  per the STOP CONDITIONS, same as every prior phase.

### 2026-08-11 — Phase 4 approved and built: taxonomy, slots, dialogue policies, prompt registry, persona

- **Marco typed `APPROVED: Phase 4`**, adding one requirement to criterion 6 before work began: given R4
  (zero prior art anywhere in the source corpus for barge-in), the L1×barge-in ordering and the no-input/
  no-match retry ceiling both needed to be **designed explicitly, not discovered later** — specifically, what
  happens when a caller barges in mid-prompt with an injury disclosure that's cut off mid-word, and what the
  system does at the retry ceiling rather than looping.
- **Wrote all five deliverables:**
  - `docs/phase4/INTENT-TAXONOMY.md` — canonical + adversarial utterance sets for all six intents, including
    a paired adversarial set built directly against `coverage-logic.md` §4's question-type split (§2.5) and
    against the new barge-in design (§2.6), so both land as reusable Phase 6/7 eval material, not just
    documentation.
  - `docs/phase4/SLOT-DESIGN.md` — `FileAutoClaim`'s 11-slot priority order and full per-slot spec (safety
    first, then policy/vehicle context, then narrative, then party/report detail, driver identity last); the
    `UpdateContactInfo` mandatory-confirmation write path; DTMF fallback scoped to exactly the three
    digits-only identifier slots per `DATA-CONTRACTS.md`.
  - `docs/phase4/DIALOGUE-POLICIES.md` — the compound `CoverageQuestion` decision path (§2, Marco's original
    requirement: classify election-fact-mandatory / election-fact-optional / eligibility-amount as part of
    the existing merged router+L2 call, not a new round-trip; names `GetPolicyholderElections` as a forward
    Phase 5 tool requirement); the rental/towing compound policy (§3); the injury hard-escalation script and
    preemption rule (§5); **§6 — barge-in reuses the exact per-turn pipeline with no separate code path, so
    `ADR-010`'s L1-first ordering already covers the interruption path by construction, and a mid-word cutoff
    is answered with one open re-prompt rather than either silent discard or an assumed-safe resumption**;
    **§7 — the retry ceiling (2 attempts, then escalate, never a hang-up), scoped per-slot not per-call, with
    the barge-in repair path in §6 explicitly drawing from this same ladder rather than creating a second
    one**; a full escalation-trigger table (§8) cross-checked against Phase 1's four routes.
  - `docs/phase4/PROMPT-REGISTRY.md` — full tool schema + system prompt for the merged Nova Micro router+L2
    call; system prompts and suggested `max_tokens` for the two generation-node prompts. **Structural finding
    stated as D17**: the generation node is invoked for exactly two cases — every other spoken line in the
    system is fixed or templated, which is the real mechanism behind the length-discipline requirement, not
    just a prompting instruction. The length-tolerance table covers both generated and templated turns with
    per-category enforcement, directly citing the Nova Micro pre-flight padding case as the motivating
    example Marco supplied.
  - `docs/phase4/PERSONA.md` — greeting with AI disclosure inline (not a footer), a fixed truthful response
    if asked directly whether the caller is talking to a person, tone rules, and a **single budgeted empathy
    phrase used once per call** rather than a rotating bank — reasoned explicitly against the same padding
    concern as the prompt registry's length discipline, including a note that the escalation script must
    never be preceded by it.
- **Recorded D17–D19** — the generation-node scope decision, the retry-ceiling/no-hang-up rule, and the
  barge-in-shares-the-same-ladder rule — as standing architectural decisions, not just prose inside the
  design docs.
- **All 13 exit-criteria rows checked** (see table above). **Phase 4 content is complete — presented for
  Marco's closing sign-off, not self-marked closed**, applying the exact lesson Phase 3's own log recorded
  about not letting that distinction go ambiguous.
- **No application/agent code written** — five Markdown documents only; the LangGraph graph, MCP servers, and
  tool implementations remain Phase 5's scope. **No billable resource created; $0.00 new spend.** The
  optional closing verification named in criterion 12 (a small number of real Bedrock calls to empirically
  check the length-discipline prompts) was **not run** — it remains available but was not exercised without a
  separate cost-gate approval, same discipline as every other real-spend decision this project has made.

### 2026-08-11 — Phase 4 signed off; D17 elevated; closing Bedrock verification run

- **Marco typed `APPROVED: Phase 4`** a second time, this one the closing sign-off (content was already
  complete). Three follow-ons given alongside it:
  1. **D17 elevated** — "only two paths invoke generation" is a stated architectural claim (the majority of
     spoken output is structurally incapable of hallucinating, not just unlikely to), to be carried into
     Phase 12's README explicitly. Added to `PROMPT-REGISTRY.md`'s opening section and recorded as `D20`;
     tracked as `CF1` in the new "Carried forward to future phases" table rather than written into a README
     that doesn't exist yet.
  2. **Phase 9 load-testing note** — concentrate effort on the two generation paths, not distributed
     uniformly across all six intents, since every other intent's latency is fixed-string/template latency.
     Tracked as `CF2`.
  3. **Phase 2 cost-model discrepancy** — `docs/phase2/COST-MODEL.md`'s per-conversation Bedrock rows
     implicitly assumed generation-scale output (~1k tokens) on every turn; `D17` establishes that only two of
     six intents ever reach the generation node. **Not rebuilt** (per Marco's explicit instruction) — a
     discrepancy note added directly under the per-conversation table stating the existing ~$0.001 figure is
     a conservative upper bound, directionally overstated by roughly 10–20× for a typical call, with the real
     token counts from the closing verification (next item) cited as the basis for that range. Restates that
     this doesn't move the $25 ceiling verdict — Bedrock was already noise-level before this correction.
- **Ran the approved closing verification**: five real `Converse` calls (`us-west-2`) against
  `PROMPT-REGISTRY.md`'s exact prompts, using real corpus content — the DCPD passage, the IRB optional-benefit
  passage plus policyholder `PY4821`'s real election (`income_replacement_benefit: true`), and claim
  `CLM-2608-00042-4`'s real rental figures (8 days / $400 remaining). Verification script kept in the session
  scratchpad, not the repo, so Phase 4's "no application code" claim stays accurate.
  - **Nova Micro, forced tool-use (`classify_turn`)**: `toolChoice: {"tool": {...}}` confirmed supported by
    Nova Micro via Converse (not assumed). Output was the tool-use block only — no accompanying prose. The
    padding tendency did not leak around a schema-forced call.
  - **Nova Micro, unconstrained tight-turn generation (the ambiguity clarifier, §3.3)** — the closest real
    replication of the pre-flight scenario that originally motivated this whole requirement: one sentence, 20
    words, no restated question. **The padding behavior did not reproduce in this trial** with the
    prompt-registry-style explicit length instruction in place — reported as a single data point, not a claim
    that the underlying tendency is solved.
  - **Nova Lite, `CoverageQuestion` mandatory and optional**: both within the 1–2 sentence target, both
    correctly grounded against the real retrieved text and (for the optional case) the real election record.
  - **Nova Lite, `RentalTowingEntitlement` compound**: within the 2–3 sentence target, but **a real minor
    defect was caught**: the second sentence restated the "8 days remaining" fact in different words instead
    of adding the dollar figure the tool result also carried — sentence-count discipline held, content-level
    redundancy didn't. **Fixed directly in `PROMPT-REGISTRY.md` §3.2's prompt** (added an explicit
    do-not-restate instruction) in response to the observed output, not asserted as fixed pre-emptively.
  - All five results, and the fix, written into `PROMPT-REGISTRY.md` §4 ("Verified against real Bedrock
    calls") rather than left only in this log — the design document now carries its own verification record.
- **Cost**: 1,606 input / 153 output tokens across the five calls, $0.0001058, logged in `COSTS.md` with a
  full per-call breakdown. **Running Bedrock standing-cap total: $0.0001161 of $5.00.**
- **Phase 4 is now signed off.** Phase 5 has not begun — no exit criteria written, no approval given, per the
  STOP CONDITIONS.

### 2026-08-11 — Phase 5 exit criteria proposed

- **Marco approved Phase 4's sign-off** and added `CF3`: the Nova Micro tight-turn result from the closing
  verification is n=1, a smoke test, not evidence the pre-flight padding behaviour is absent — Phase 6's
  length check must sample that path repeatedly, not once. Recorded in the carried-forward table.
- **Asked Phase 5 be scoped with two things visible before approving**: the build order/dependency sequence
  (so a mid-phase gate is possible under context pressure), and exactly where the cost gate applies, naming
  which steps need real Bedrock or real DynamoDB.
- **Wrote `docs/phase5/BUILD-PLAN.md`.** Eight dependency-ordered stages (foundations → MCP servers →
  knowledge retrieval → Bedrock router+fake-LLM harness → guardrails → LangGraph nodes → graph assembly+
  checkpointer → optional real-call verification), each a clean stop/resume point; stages 1–5 flagged as
  independent enough to delegate to isolated subagents if useful, stages 6–7 kept on the main thread as
  integrator per `CLAUDE.md`'s own guidance. **Named one open design decision explicitly rather than
  deferring it implicitly**: MCP transport (in-process calls vs. the wire protocol) needs a short `ADR-012`
  before the MCP servers are built, since it shapes their interface — not drafted yet, committed to as the
  first task once Phase 5 is approved.
- **Cost-gate answer, stated precisely**: mock-by-default holds for every stage; the *only* real spend in the
  entire phase is an optional Stage 8 closing verification against real Bedrock, under the existing $5
  standing cap. **Two things are explicitly never created in Phase 5 regardless of that cap**: a real
  DynamoDB table and a real Bedrock Guardrail — both are provisioned, persistent resources the inference-only
  standing cap doesn't cover, and both stay Phase 8's, with their own approval when that time comes. This
  distinction (stateless inference call vs. persistent resource creation) is the actual answer to "where does
  the cost gate apply," not just a restatement of "mock by default."
- **Scope stated as broader than the original Phase 0 roadmap line** for Phase 5 — `models/`, `validation/`,
  `config/`, `knowledge/retrieve.py`, and `guardrails/` are added as named prerequisites the one-line roadmap
  description didn't spell out, said plainly rather than left to be discovered mid-build.
- **Phase 5 exit-criteria table added to `PROJECT_STATE.md`** (above) — 13 rows, all pointing at
  `BUILD-PLAN.md`'s stages. **Not started** — presented for Marco's `APPROVED: Phase 5`, per the STOP
  CONDITIONS, same as every prior phase. No code written this entry. No billable resource created. $0.00 new
  spend.

### 2026-08-11 — Phase 5 Stages 1–5 built; gate reached per Marco's instruction

- **Marco typed `APPROVED: Phase 5`**, approved `ADR-012` with one added requirement — the ADR must state a
  falsifiable test (same tool schemas servable over the wire without modifying the handlers; no shared state
  reaching around the interface; schemas defined separately from handlers) rather than just asserting the
  in-process decision is honest — and directed that Stage 2 *prove* it via a working `.claude/mcp.json`
  round trip, not assert it. Approved subagents for Stages 1–5, main thread as integrator for Stages 6–7, and
  an explicit gate after Stage 5, reasoning that Stages 6–7 are the wiring and should be hit with clean
  context rather than mid-compact.
- **Wrote `docs/adr/ADR-012-mcp-transport.md`** with Marco's falsifiable test as the ADR's own accept/reject
  criterion, stated in its own words: if the test can't be written without touching handler internals, the
  correct fix is renaming the modules away from the MCP claim, not forcing the test to pass.
- **Built Stage 1 directly** (foundations: `models/`, `validation/`, `config/`) rather than delegating it,
  since it sets the shared contracts every other stage depends on. Validating the real Phase 3 synthetic
  corpus against the new Pydantic models — not a synthetic test fixture — caught three genuine schema
  mismatches (`claim_type` is a free-text claims-processing label, not `FileAutoClaimSlots`' `loss_type`
  enum; rental usage fields are `None` together when the endorsement wasn't elected; `fault_percentage_insured`
  is `None` on pure-Comprehensive claims) and one real arithmetic gap (`rental_days_remaining` didn't encode
  `endorsements.md`'s total-loss exception — a total-loss claim's rental entitlement is zero regardless of
  days used, caught against real claim `CLM-2607-00042-5`, not invented). All fixed, not worked around.
- **Launched four parallel subagents for Stages 2–5**, each scoped to disjoint files, given the exact source
  documents to build from, instructed not to touch `pyproject.toml` or each other's directories, and required
  to run the full test suite (not just their own new tests) before committing. All four landed clean:
  - **Stage 2 (MCP servers)** — `ADR-012`'s falsifiable test **passes for all four domains**, not just the
    required minimum: a real subprocess per server, driven by the real `mcp` SDK client over real stdio,
    result matches the in-process handler call exactly. No handler needed modification to be servable over
    the wire, and no shared state crosses the boundary — confirmed by the wire test and by an automated check
    that no handler module imports `mcp` at all. Caught a real naming mismatch (`ContactField.MAILING_ADDRESS`
    vs. `Policyholder.address`), mapped explicitly rather than silently reconciled, and verified
    `get_claim_status`'s "most recent open claim" resolution against the real multi-claim policyholder
    `PY4821` and the no-open-claim edge case `PY9012`.
  - **Stage 3 (knowledge retrieval)** — the read half of `ADR-002`. Measured, not estimated, the cosine
    similarity computation's real latency: **0.036 ms average over 1,000 calls** against the real 21-chunk
    corpus, confirming `ADR-002`'s "negligible against the 1,800 ms budget" engineering judgment with an
    actual number. Flagged (not fixed, correctly out of its own scope) that `knowledge/__init__.py`'s
    docstring was now stale — fixed directly by the integrator afterward (commit `c0a2bd1`).
  - **Stage 4 (Bedrock router + fake-LLM harness)** — `ADR-004`/Q10's structural separation (the generation-
    tier flag must have no code path to the fixed router+L2 call) is now a passing assertion — flip the flag,
    prove the router's requested model ID never moves while the generation call's does — not just a
    docstring claim. Proved Q10's "not silently omittable" requirement the same way: a canned tool response
    missing `safety_flag` raises a real `pydantic.ValidationError`, not a silent default.
  - **Stage 5 (guardrails + PII redaction)** — built against a mocked `ApplyGuardrail` client throughout, per
    the plan (no real Guardrail resource exists). Honest about limits, matching `ADR-011`'s own stated
    boundary rather than overclaiming: no name detection at all (assigned to Bedrock Guardrails, not this
    module); date/time and location redaction catch plainly-phrased mentions only, `ADR-011`'s own named
    example ("right outside my kids' school on Maple") is explicitly still uncaught. Proved `ADR-010`'s
    ordering by grep-level assertion — no `guardrailIdentifier` anywhere near a model call in this module —
    plus a full 4-step sequencing test.
- **Integration verification, run by the main thread against the merged state of all five stages**:
  `pytest tests/unit -q` → **145/145 passed**, `ruff check` clean, `black --check` clean, `mypy src --strict`
  → **clean across all 34 source files** (one file-specific issue Stage 5 flagged mid-build in Stage 2's
  `escalation_server.py` was already resolved by Stage 2's own completion — confirmed clean at integration,
  not just trusted from an intermediate report). Fixed one small integration-time item (`knowledge/__init__.py`'s
  stale docstring, commit `c0a2bd1`) that no single stage's scope covered.
- **Zero real AWS calls across all five stages — $0.00 new spend**, confirmed empirically (every test run
  used mock/local backends only), not merely planned in `BUILD-PLAN.md`.
- **Phase 5 exit-criteria table updated**: rows 1–7, 10–13 checked; rows 8–9 (LangGraph nodes, graph assembly
  + checkpointer) explicitly left unchecked. **Phase 5 is not signed off — Stages 6–7 have not started**,
  per Marco's own gate instruction. No exit criteria for Stages 6–7 exist yet beyond `BUILD-PLAN.md`'s
  existing stage descriptions; per the STOP CONDITIONS, that work does not begin without Marco's separate
  go-ahead.
