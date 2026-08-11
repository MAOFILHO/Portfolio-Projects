# PROJECT_STATE.md

### STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and my explicit approval.
- No billable AWS resource is created without me typing `APPROVED: <phase name>`.
- The Amazon Connect instance and DID already exist. Never create either.
- `PROJECT_STATE.md` is updated before any session ends.
- Restate these four conditions verbatim at the top of every session summary and after every `/compact`.

---

**Last updated:** 2026-08-11
**Current phase:** Phase 3 — Data engineering and knowledge base — **approved, starting** (`APPROVED: Phase 3` typed by Marco 2026-08-11).
**Progress:** Phase 2 signed off; Connect Customer Basic tier switch approved, executed, and verified (screenshot + console confirmation) same day — this is now the live billing tier. Phase 3 exit criteria are in place below; work begins from here.
**Running spend attributable to this project:** **$0.00** provisioned by us.
Pre-existing accrual only: the claimed Canada DID (rate unverified, est. $0.90–$3.00/mo).
Bedrock standing-approval budget consumed: **$0.00 of $5.00**.

---

## Phase status

| Ph | Name | Status |
|---|---|---|
| 0 | Repo archaeology, workspace setup, merge strategy | ✅ **Signed off** 2026-08-11 |
| 1 | Problem framing and success criteria | ✅ **Signed off** 2026-08-11 (two corrections applied) |
| 2 | Architecture and ADRs | ✅ **Signed off** 2026-08-11 |
| 3 | Data engineering and knowledge base | 🔵 **In progress** — `APPROVED: Phase 3` typed 2026-08-11 |
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
| 7 | Ingestion pipeline: chunks corpus, embeds via Titan Embed v2, writes to DynamoDB per `ADR-002`'s schema | Exercises the $5 Bedrock standing cap only if run against AWS; local/LocalStack path preferred for iteration |
| 8 | Data card written: what's synthetic, what's derived from real regulatory/domain sources (KABCO, NHTSA MMUCC), what's authored with no external grounding at all (rental/towing, deductible logic) | ✅ `docs/phase3/DATA-CARD.md` — as-of-date warning carried prominently at the top per Marco's instruction; provenance graded per-document, with the corpus-construction-choice reframing (§3, Marco's own language) restated here too, not just upstream |
| 9 | No real customer/policy PII introduced; no images vendored from any source repo | ✅ All names/phones/emails/addresses fabricated (555 exchange, `@example.com`, generic Ontario streets); no images anywhere in Phase 3 output |
| 10 | No application/agent code written (Phase 5's scope, not this one) | |
| 11 | No billable resource created beyond exercising the already-approved $5 Bedrock standing cap (Phases 3–7), logged per-run in `COSTS.md` | Provisioned resources remain individually gated regardless |
| 12 | Marco's explicit approval to begin, per the STOP CONDITIONS | ⬜ **Pending** — type `APPROVED: Phase 3` if this scope is right, or redirect before work starts |

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
