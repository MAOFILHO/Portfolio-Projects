# Target Layout and Path Mapping — Phase 0

## Layout

Follows the conventions established by the sibling project
`AWS-Bedrock-FineTuning-LangGraph-MCP-Agentic-Platform` in the same monorepo.

```
AWS-Insurance-FNOL-Voice-Agentic-AI/
├── CLAUDE.md                    # conventions + STOP CONDITIONS verbatim
├── PROJECT_STATE.md             # single source of truth for phase/decisions/risks
├── README.md                    # clone → live call (written in Phase 12)
├── CHANGELOG.md                 # semantic versioning
├── COSTS.md                     # estimates + per-run Bedrock spend against the $5 cap
├── Makefile                     # bootstrap deploy destroy eval redteam test lint typecheck simulate
├── pyproject.toml               # py3.12, ruff (line 100), mypy strict, pytest
├── requirements.txt / requirements-dev.txt
├── .env.example                 # never .env
├── .gitignore  .pre-commit-config.yaml
│
├── .claude/
│   ├── settings.json            # read-only auto-approvals only
│   ├── mcp.json                 # Phase 5 — local MCP servers for Claude Code
│   └── skills/                  # Phase 2+ (proposed, approved before writing)
│
├── .github/workflows-for-monorepo-root/
│   ├── README.md                # the root-copy step; renaming this folder breaks path filters silently
│   ├── aws-insurance-fnol-voice-agentic-ai-ci.yml
│   └── aws-insurance-fnol-voice-agentic-ai-terraform.yml
│
├── src/fnol_voice_agent/
│   ├── agents/            # LangGraph graph, nodes, state schema, checkpointer wiring
│   ├── mcp/               # one MCP server per backend domain (policy, claims, contact, escalation)
│   ├── aws/               # bedrock model router, dynamodb checkpointer, lex adapter, connect helpers
│   ├── models/            # pydantic FNOL / policy / claim / vehicle schemas
│   ├── knowledge/         # chunk, embed, index, retrieve
│   ├── guardrails/        # PII redaction, injection screening, guardrail client
│   ├── observability/     # structlog JSON, OTel spans, EMF metrics, correlation IDs
│   ├── config/            # settings, feature flags (OpenFeature)
│   ├── validation/        # slot validators, business rules, authority limits
│   └── api/               # dashboard backend (API Gateway HTTP + Lambda)
│
├── infra/terraform/
│   ├── bootstrap/               # state backend (S3 + DynamoDB lock)
│   ├── stacks/telephony/        # DID ONLY. prevent_destroy, SEPARATE STATE,
│   │                            # import guard asserts Protected=true. make destroy never touches it
│   ├── stacks/main/             # flows, queues, hours, Lex (nested CFN), Lambda, DDB, S3,
│   │                            # EventBridge, Step Functions, dashboards, alarms, budget
│   └── modules/
│
├── frontend/                    # React + TypeScript + Vite
│                                # live contact feed, transcript viewer w/ agent traces,
│                                # tool-call inspector, metrics, cost/conversation, eval results,
│                                # guardrail interventions, and the web call simulator
│
├── data/synthetic/              # policy corpus, policyholders, vehicles, claims (all synthetic)
├── evals/                       # golden set, component + conversation evals, judge rubrics
├── redteam/                     # injection, PII extraction, jailbreak, hallucination probes
├── simulator/                   # CLI/replay harness — the primary cost control
│
├── tests/
│   ├── unit/                    # ≥80% on agent core
│   ├── pre_provision/           # validate config before any spend
│   ├── post_provision/          # assert deployed state, incl. recording-disabled check
│   ├── post_run/                # assert behaviour after a simulated call
│   └── post_teardown/           # assert $0 footprint and that the DID survived
│
├── docs/
│   ├── phase0/                  # MERGE-MATRIX, DEPENDENCY-CONFLICTS, DOMAIN-ARTIFACTS,
│   │                            # SECURITY-FINDINGS, TARGET-LAYOUT (this file)
│   ├── adr/                     # immutable; supersede, never edit
│   ├── COST-ACTUALS.md  RESULTS.md  LESSONS-LEARNED.md  INCIDENT-LOG.md
│   ├── evidence/  screenshots/
│   └── runbooks/
└── scripts/
```

### Two layout notes that matter

**`.github/workflows-for-monorepo-root/`** — GitHub Actions reads workflows **only** from the repository
root. A `.github/workflows/` directory inside a project folder is silently ignored: no error, no warning, the
workflows simply never run. Workflows are therefore staged here with a project-name prefix,
`paths:`-scoped to this folder, each job setting `working-directory`, and copied to the monorepo root on
install. If this folder is ever renamed, the `paths:` filters, `working-directory:` values and
`cache-dependency-path:` entries must be updated — a mismatch makes the workflows stop running silently
rather than fail loudly. Repository variables are prefixed `FNOL_*` so they cannot collide with a sibling
project's settings in shared monorepo configuration.

**`infra/terraform/stacks/telephony/` is separate state, deliberately.** It holds only the pre-existing DID,
with `prevent_destroy = true`, and `make destroy` must not target it. Releasing and re-claiming a number risks
a **180-day claim block**. Its import guard asserts the `Protected=true` tag before proceeding. The Connect
instance itself is consumed via a data source and is in no state file at all.

---

## Old → new path mapping

Given that ~97% of source code by volume is discarded, most of this table reads "no source — written fresh".
That is stated explicitly rather than left implied, so nobody later assumes inheritance that does not exist.

### Carried forward

| Source (read-only) | Destination | Form |
|---|---|---|
| repo 6 `voice-fnol-agent/app/models/claim_schema.py` | `src/fnol_voice_agent/models/fnol.py` | Adapted Pydantic v2 (aliases retained; the `otherParty` optionality and `numberOfPassengers` type inconsistencies fixed) |
| repo 6 `voice-fnol-agent/app/agent.py:117-188` (SYSTEM_PROMPT) | `src/fnol_voice_agent/agents/prompts/` | Prose ported into the versioned prompt registry, rewritten for a voice register |
| repo 6 `app/tools/safety_check.py` | `src/fnol_voice_agent/agents/nodes/safety.py` | Triage ladder + guidance strings as a LangGraph node |
| repo 6 `app/tools/validate_fields.py` | `src/fnol_voice_agent/validation/required_fields.py` | Rule set incl. the conditional police-receipt rule |
| repo 6 `app/tools/extract_claim.py` | `src/fnol_voice_agent/validation/parsing.py` | Fuzzy date parsing + human-readable field labels |
| repo 6 `event-catalog/events/*/schema.json` | `docs/adr/` + `src/fnol_voice_agent/models/events.py` | Event vocabulary and payload contracts |
| repo 6 `agent-skills/VOICE_AGENT_SKILL.md` | `docs/phase0/` (reference) | Read for its pitfalls section; not vendored |
| repo 6 `ClaimFieldsDisplay.js` | `frontend/src/components/` | UX pattern rewritten in React + TS |
| repo 5 `Knowledgebase/SampleRepairCost.docx` | `data/synthetic/policy/` + `src/fnol_voice_agent/models/severity.py` | KABCO enum, damage-extent enum, cost bands, labour formula |
| repo 5 Lex export slot script | `infra/terraform/stacks/main/lex/` | **Spec only** — bot hand-authored as nested CFN. The zip is never imported |
| repo 5 Guidewire/Socotra sequences | `src/fnol_voice_agent/mcp/claims_server.py` | Shapes the mock claims system's contract |
| repo 5 `VehiclePricing` table | `data/synthetic/vehicles/` | Parts price seed data |
| repo 7 `human_workflow_manager.py` | `src/fnol_voice_agent/validation/authority.py` | Role enum, authority matrix, regulatory clocks, audit trail |
| repo 7 `enhanced_models.py` | `src/fnol_voice_agent/models/taxonomy.py` | P&C enums, cut to auto-only, `ConfigDict` |
| repo 7 `langgraph_policy_agent.py` (2 functions) | `src/fnol_voice_agent/validation/coverage.py` | Deductible / peril / exclusion arithmetic |
| repo 7 `shared/observability.py` | `src/fnol_voice_agent/observability/` | structlog config + metric dataclasses; Powertools EMF replaces the threading machinery |
| repo 7 `shared/authentic_llm_integration.py` | `src/fnol_voice_agent/agents/prompts/registry.py` | Prompt-registry structure only |
| repo 7 `data/sample_claims.json`, `fraud_patterns.json` | `data/synthetic/claims/` | Auto records only |
| repo 8 `complexity_analyzer.py` | `src/fnol_voice_agent/validation/triage.py` | Thresholds, weighted score, conservative bias, **deterministic non-LLM fallback** |
| repo 8 `evidence_analyzer.py` (transcript taxonomy) | `src/fnol_voice_agent/models/post_call.py` | Tag enums for post-call analysis |
| repo 8 `generated_evidence/CLM_00*_transcript_*.txt` (6 files) | `evals/fixtures/transcripts/` | Verbatim test fixtures |
| repo 8 `generate_claim_evidence.py` (transcript + Polly paths) | `scripts/generate_fixtures.py` | Polly neural → PCM → WAV 16 kHz mono. **Nova Canvas/Reel paths dropped** |
| repo 8 `backend/main.py` (API shape) | `src/fnol_voice_agent/api/` | Async-analyze-then-poll design |
| repo 8 cdk DynamoDB/S3 IAM statements | `infra/terraform/modules/` | ARN-scoping pattern |
| repo 1 `samplecontactflow.json` | `infra/terraform/stacks/main/flows/` | Modern-schema grammar reference; FNOL content authored fresh |
| repo 1 `dialogAction` Delegate/Close + repo 2 ElicitSlot/messages | `src/fnol_voice_agent/aws/lex.py` | The Lex V2 codehook response contract |
| repo 1 `IntegrationAssociation` + `Lambda::Permission` | `infra/terraform/stacks/main/` | Scoped-permission pattern → `aws_connect_integration_association` |
| repo 1 `available_intents` session attribute | `infra/terraform/stacks/main/flows/` + `agents/` | Per-turn intent scoping |
| repo 2 `SetRecordingBehavior` block | `tests/post_provision/fixtures/` | **Negative fixture** the recording guard must reject |
| repo 2 `myPersonalResponder_v1.js` contract | `src/fnol_voice_agent/aws/connect.py` | `event.Details.Parameters` in / flat map out |
| repo 3 `PII_ENTITY_TYPES` | `src/fnol_voice_agent/guardrails/pii.py` | 22-type vocabulary minus `DATE_TIME`/`ALL`, plus VIN/plate/policy/claim |
| repo 3 README (Contact Lens rationale) | `docs/adr/` | Cited in the redaction ADR |
| **Live Connect instance** `Sample recording behavior` flow | `tests/post_provision/` | Verified `UpdateContactRecordingBehavior` JSON — the CI check is written against real schema, not a guess |

### Written fresh — no source exists

| Destination | Why there is no source |
|---|---|
| `src/fnol_voice_agent/agents/graph.py` + all nodes | Repo 7's LangGraph is Ollama-bound, EKS-shaped and partly non-functional; only the shape transfers |
| `src/fnol_voice_agent/aws/bedrock.py` (Converse, model router, retry/throttle, streaming) | **No repo contains any Bedrock agentic integration.** Repo 7 has none at all |
| `src/fnol_voice_agent/aws/checkpointer.py` (DynamoDB `BaseCheckpointSaver`) | No repo has durable checkpointing; there is no official `langgraph-checkpoint-dynamodb` |
| `src/fnol_voice_agent/mcp/**` | **No repo uses MCP at all** |
| `src/fnol_voice_agent/knowledge/**` | No repo has working RAG. Repo 5's only vector store is the banned OpenSearch Serverless |
| `src/fnol_voice_agent/guardrails/` (Bedrock Guardrails, injection screening) | No repo uses Guardrails or has any injection defence |
| Lex barge-in / DTMF / timeout / no-match configuration | The combined corpus contains only `MaxRetries: 2` |
| Interim audio fillers / streaming | No repo streams; repo 1 produces dead air by design |
| `evals/**` | No repo has an eval harness, golden dataset, or judge rubric |
| `redteam/**` | No repo has any red-team suite |
| `simulator/**` | No repo has a call simulator |
| Rental reimbursement + towing coverage sections | **Zero mentions across all eight repos** — and two of our six intents need them |
| Deductible computation, total-loss rule, injury-severity→coverage mapping | No repo computes any of these |
| Speakable claim-number format | No repo supplies a usable one (OTP-leaking, unspeakable, or 3 digits) |
| `infra/terraform/**` | Five different IaC approaches across eight repos, none adoptable; and all their infrastructure is on the banned list |
| `frontend/**` (app shell) | All three source frontends are Create React App; we use Vite + TS |
| `.github/workflows-for-monorepo-root/**` | **No source repo has any CI at all** |
| `tests/**` | Coverage across the corpus is ~0%, except ~25–30% of one repo's voice `app/` with **0% of its business logic**. Repo 8's only test is a commented-out stub that passes vacuously |
| `Makefile`, `pyproject.toml`, `.pre-commit-config.yaml` | No repo has lint, type or pre-commit configuration |
