# PROJECT_STATE.md

### STOP CONDITIONS — absolute, no exceptions

- No phase begins without written exit criteria from the prior phase and my explicit approval.
- No billable AWS resource is created without me typing `APPROVED: <phase name>`.
- The Amazon Connect instance and DID already exist. Never create either.
- `PROJECT_STATE.md` is updated before any session ends.
- Restate these four conditions verbatim at the top of every session summary and after every `/compact`.

---

**Last updated:** 2026-08-11
**Current phase:** Phase 0 — complete, awaiting sign-off
**Next phase:** Phase 1 — Problem framing and success criteria (blocked on Phase 0 sign-off)
**Running spend attributable to this project:** **$0.00** provisioned by us.
Pre-existing accrual only: the claimed Canada DID (rate unverified, est. $0.90–$3.00/mo).
Bedrock standing-approval budget consumed: **$0.00 of $5.00**.

---

## Phase status

| Ph | Name | Status |
|---|---|---|
| 0 | Repo archaeology, workspace setup, merge strategy | ✅ Complete — awaiting sign-off |
| 1 | Problem framing and success criteria | ⬜ Not started |
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
| 12 | No billable resource created; $0.00 new spend | ✅ |

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

### Proposed, pending Phase 2 ADR

| # | Proposal | Status |
|---|---|---|
| P1 | Define the Lex V2 bot as a **single CloudFormation `AWS::Lex::Bot` resource** wrapped by Terraform's `aws_cloudformation_stack`; everything else native Terraform | Proposed — becomes the IaC ADR. Rationale under "Risks" below |

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
| R1 | **Terraform `aws_lexv2models_*` resources are known-broken exactly where we need them** — `prompt_specification` updates silently dropped ([#42147]), `prompt_attempts_specification` / `message_selection_strategy` "inconsistent result after apply" ([#36845]), **intent↔slot circular dependency via `slot_priority`** ([#39948]) | Hits the barge-in/DTMF config (constraint 14) and the 9-slot FNOL intent (the showcase) | P1 above: single nested CFN `AWS::Lex::Bot` resource structurally cannot hit the cycle. Formal ADR in Phase 2 |
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

---

## Session log

### 2026-08-11 — Phase 0
- Read all eight source repos via three parallel archaeology agents. Produced merge matrix (84% discard, justified per row), dependency conflict report, domain artifact inventory, security findings, target layout.
- Verified live environment rather than trusting the brief: confirmed the Connect instance and, notably, that **the DID is Canadian (`CountryCode: CA`), not US** — the assumed US rates do not apply.
- Extracted the **modern recording-block ground truth** from the instance's own `Sample recording behavior` flow: the 2019-10-30 schema has no `RecordingBehaviorOption`; recording state is the `RecordedParticipants` array, empty = off. The constraint-18 CI check is now written against verified JSON rather than a guess.
- Confirmed Bedrock inference profiles and that `amazon.nova-micro-v1:0` is **`INFERENCE_PROFILE`-only**, making constraint 17's `us.*` rule mandatory rather than stylistic.
- Discovered R1 (Terraform Lex V2 provider bugs) and R3 (free-tier replacement) — both materially change Phase 2.
- Scaffolded workspace: `CLAUDE.md`, `PROJECT_STATE.md`, `.claude/settings.json`, `docs/phase0/*`, `.gitignore`, `CHANGELOG.md`, `README.md`.
- **No application code written. No billable resource created. $0.00 new spend.**
- Marco re-tagged the DID to `Project=AWS-Insurance-FNOL-Voice-Agentic-AI`, `Owner=marcos`, `Protected=true`; recorded above and wired into the Phase 8 import guard.
