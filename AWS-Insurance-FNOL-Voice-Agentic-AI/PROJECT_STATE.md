# PROJECT_STATE.md

### STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and my explicit approval.
- No billable AWS resource is created without me typing `APPROVED: <phase name>`.
- The Amazon Connect instance and DID already exist. Never create either.
- `PROJECT_STATE.md` is updated before any session ends.
- Restate these four conditions verbatim at the top of every session summary and after every `/compact`.

---

**Last updated:** 2026-08-11
**Current phase:** Phase 2 — Architecture and ADRs — **in progress** (documentation/artifacts only; no `APPROVED: Phase 2` typed, no billable resource created)
**Progress:** ADR-007 (IaC tool selection) and ADR-008 (region selection) accepted. Nine ADRs remain (ADR-001–006, 009–011), plus Mermaid diagram, full cost model, threat model.
**Running spend attributable to this project:** **$0.00** provisioned by us.
Pre-existing accrual only: the claimed Canada DID (rate unverified, est. $0.90–$3.00/mo).
Bedrock standing-approval budget consumed: **$0.00 of $5.00**.

---

## Phase status

| Ph | Name | Status |
|---|---|---|
| 0 | Repo archaeology, workspace setup, merge strategy | ✅ **Signed off** 2026-08-11 |
| 1 | Problem framing and success criteria | ✅ **Signed off** 2026-08-11 (two corrections applied) |
| 2 | Architecture and ADRs | ⬜ Not started |
| 3 | Data engineering and knowledge base | ⬜ Not started |
| 4 | Conversation design | ⬜ Not started |
| 5 | Agent implementation | ⬜ Not started |
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
| R5 | Two of the six intents (rental/towing entitlement) have **no source material anywhere** in the corpus | Intent 4 has no ground truth until authored | Phase 3 authors rental + towing coverage sections from scratch, internally consistent with the rest of the corpus |
| R6 | Repo 7 — nominally the "richest agentic source" — **contains no Bedrock at all** (self-hosted Ollama on GPU Karpenter) and its LangGraph code is partly non-functional | The entire Bedrock, checkpointer, guardrails, RAG, eval, MCP and observability layer is greenfield | Accepted and planned for; only the *patterns* and domain model were harvested |

[#42147]: https://github.com/hashicorp/terraform-provider-aws/issues/42147
[#36845]: https://github.com/hashicorp/terraform-provider-aws/issues/36845
[#39948]: https://github.com/hashicorp/terraform-provider-aws/issues/39948

---

## Open questions

| # | Question | Needed by | Owner |
|---|---|---|---|
| Q1 | Exact Canada DID per-day and inbound per-minute rate | Phase 2 cost model | Read from Cost Explorer under the service key **`Contact Center Telecommunications (service sold by AMCS, LLC)`** — verified present but at $0.00 as of 2026-08-11, since the number was claimed the same day. Re-read after ≥1 full day of accrual |
| Q2 | Does `us.anthropic.claude-haiku-4-5` earn its cost over `us.amazon.nova-lite` on the generation node? | Phase 6 | Decided by evals, not preference |
| Q3 | Claim-number format — needs designing. No repo supplies a usable one: repo 5's `PY1234-123450` **embeds the OTP secret**, repo 6 uses an unspeakable bare UUID, repo 8's `CLM-001` is 3 digits | Phase 3 data contracts | Proposal: `CLM-YYMM-XXXXX` + check character |
| Q4 | Vector store choice — S3 Vectors (now GA in us-west-2) vs FAISS/sqlite-vec baked into the Lambda package vs DynamoDB + in-memory cosine | Phase 2 ADR | Trade-off table required before choosing. **Not** OpenSearch Serverless |
| Q5 | Deductible logic, total-loss threshold and injury-severity→coverage mapping (BI/PIP/MedPay) have no prior art | Phase 3 | Author from the KABCO scale harvested in Phase 0 |
| ~~Q6~~ | ~~Lexical injury detection will miss novel phrasings~~ | **RESOLVED** by D15 | Layered L1+L2+L3 detection committed as an architectural requirement; recall gate split into a labelled-set GATE and a held-out OBSERVED measure |
| Q7 | Does the reranker earn its latency against the 1,800 ms budget? | Phase 6 | Measured, not assumed — recall@5 gain vs added p95 |
| ~~Q8~~ | ~~Where does the safety pre-node sit relative to Guardrails input filtering?~~ | **PROMOTED** to a required Phase 2 ADR (ADR-010) | No longer an open question or an implementation note — it is a safety-critical ordering constraint that must be visible to anyone reading the architecture |
| Q9 | Free-text location redaction is genuinely hard — "right outside my kids' school on Maple" embeds a location a location-entity redactor may miss | Phase 7 | Reported as a limitation, not claimed as solved. Bounded by the fact that structured capture already holds the authoritative value |
| Q10 | L2's per-turn classifier must not be switchable off by the model-tier feature flag | Phase 5 | A config change meant to alter the generation tier must not be able to disable a safety detector. Needs an explicit test |

---

## Phase 2 — required ADRs

Carried in from Phase 1 and from Marco's Phase 1 sign-off. ADRs are immutable once accepted; supersede,
never edit.

| ADR | Decision | Notes |
|---|---|---|
| ADR-001 | Lex as turn-manager vs. direct Bedrock streaming | |
| ADR-002 | Vector store choice (cost-driven) | Q4. Trade-off table required. **Not** OpenSearch Serverless. S3 Vectors is now GA in us-west-2 |
| ADR-003 | LangGraph vs. Bedrock Agents vs. AgentCore | |
| ADR-004 | Model tier and router strategy | Must account for L2's per-turn safety classifier as non-optional (Q10) |
| ADR-005 | State persistence — DynamoDB checkpointer keyed on Connect contact ID | No official `langgraph-checkpoint-dynamodb` exists; we write a `BaseCheckpointSaver` |
| ADR-006 | Sync vs. async post-call pipeline | |
| **ADR-007** | ✅ **Accepted** 2026-08-11 — `docs/adr/ADR-007-iac-tool-selection.md`. Nested CFN `AWS::Lex::Bot` wrapped by Terraform's `aws_cloudformation_stack`; native `aws_lexv2models_*` and CDK both rejected, on the merits, with sourced current findings | Resolves R1. Two of three previously-flagged provider bugs confirmed still open (#42147, #39948); one confirmed fixed (#36845). CDK rejected both by existing constraint and on the merits (no L2 construct for Lex V2). Mandatory Phase 8 POC carried forward for the one unconfirmed gap |
| ADR-008 | ✅ **Accepted** 2026-08-11 — `docs/adr/ADR-008-region-selection.md`. `us-west-2` retained; `ca-central-1` and AgentCore formally rejected; **residency caveat on `us.*` cross-region inference documented and accepted, not glossed over** | Verified live: `us.*` profiles called from `us-west-2` can process in `us-east-1`; CA DID is a telephony attribute, not a residency driver; AgentCore's "4-region" limit is full-parity-only, narrower tiers exist including a reduced Canada presence |
| ADR-009 | Cold-start vs. latency budget | How the 1,800 ms p95 survives Lambda cold starts, and what it would cost not to |
| **ADR-010** | **Safety-detection ordering: L1 runs before Guardrails input filtering** | Promoted from Q8 at Marco's instruction. Safety-critical ordering constraint — an input filter blocking a graphic injury description before L1 sees it defeats the detector. Must be visible in the architecture, not buried in code |
| ADR-011 | PII redaction boundary — which store holds which field | Formalises D16: the quasi-identifier analysis and the structured-record-vs-transcript split |

### Other Phase 2 requirements

- **Cost model assumes zero free tier and zero credits** — always-free tiers plus pay-per-use only. The 12-month free tier was replaced (Jul 2025) and Lex V2 has no perpetual free tier.
- **Rental/towing is core scope, not a gap.** It is 2 of the 6 intents; Phase 0 recorded "no prior art in the corpus", which is a statement about the *sources*, not a shortfall in this project. Phase 3 authors both coverage sections as first-class deliverables with unambiguous ground truth.
- Mermaid architecture diagram, in-repo.
- Full cost model with the free-tier table and a per-resource teardown-risk column.
- Threat model covering prompt injection, tool abuse, PII leakage, toll fraud and denial-of-wallet, seeded by the observed failure modes in `docs/phase0/SECURITY-FINDINGS.md`.
- Propose `.claude/skills/ai-sdlc-phase-gate/SKILL.md` from friction actually encountered in Phases 0–2, and **wait for approval** before writing it.

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
- **No application code, no Terraform, no billable resource created. $0.00 new spend.** Remaining Phase 2 work: ADR-001 through ADR-006, ADR-009 through ADR-011; Mermaid architecture diagram; full zero-free-tier cost model with teardown-risk column; threat model (prompt injection, tool abuse, PII leakage, toll fraud, denial-of-wallet).
