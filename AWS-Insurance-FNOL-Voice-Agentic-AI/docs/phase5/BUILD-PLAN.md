# Phase 5 Build Plan — Agent Implementation

Answers the two things Marco asked to see before approving exit criteria: the build order and dependency
sequence (so a mid-phase gate is possible), and exactly where the cost gate applies. This document is the
detail; `PROJECT_STATE.md`'s exit-criteria table is the checklist that points here.

**Scope is broader than the original Phase 0 roadmap's one-line description** ("LangGraph graph, MCP servers,
Bedrock router, DynamoDB checkpointer keyed on Connect contactId, fake-LLM harness, `.claude/mcp.json`") —
that line under-specifies what those pieces depend on. `models/`, `validation/`, `config/`, `knowledge/
retrieve.py`, and `guardrails/` are added as named prerequisites, not silently folded in. Said plainly rather
than left implicit, per this project's own discipline about scope changes.

---

## 1. Build order — eight stages, each a clean gate

Each stage ends in a state where work can stop and resume cleanly: tests green, nothing half-wired. Stages
1–5 have no dependency on each other's *internals*, only on their *outputs* (a typed schema, a callable
interface) — several could be delegated to isolated subagents per `CLAUDE.md`'s "use a subagent per phase
where it isolates context" guidance, if that helps manage context pressure directly. Stages 6–7 need the main
thread as integrator, since they're where independently-built pieces get wired together and a wiring mistake
is exactly the kind of error that benefits from one continuous train of thought.

| Stage | Deliverable | Depends on | Real AWS? |
|---|---|---|---|
| **1** | **Foundations**: `models/` (Pydantic FNOL/claim/policy/vehicle/event schemas, adapted from repo 6 per `TARGET-LAYOUT.md`), `validation/` (slot validators from `SLOT-DESIGN.md`'s formats, business rules from `coverage-logic.md`'s arithmetic, authority limits from the Phase 1 non-goals matrix), `config/` (settings + the generation-tier OpenFeature flag, `ADR-004`). **Also**: a short **`ADR-012`** resolving MCP transport — in-process Python calls at runtime vs. the MCP wire protocol — before Stage 2 is written, since it shapes that stage's interface shape | Phases 1–4 docs only | No |
| **2** | **MCP servers** (`mcp/{policy,claims,contact,escalation}_server.py`, one per backend domain per `TARGET-LAYOUT.md`), each wrapping Phase 3's synthetic JSON (`data/synthetic/{policyholders,vehicles,claims}`) as typed, schema-validated tool calls — `GetPolicyholderElections` (`DIALOGUE-POLICIES.md` §2's forward requirement), `GetClaimStatus`, `GetRentalStatus`, `UpdateContactInfo` (write), `InitiateEscalation` (a stub returning a structured handoff result — real Connect transfer wiring is Phase 8's, not this one). `.claude/mcp.json` registered here, last, once the servers exist to register | Stage 1 (`models/` for typed contracts), `ADR-012` | No — reads local JSON only |
| **3** | **Knowledge retrieval** (`knowledge/retrieve.py`) — the read half of `ADR-002`'s brute-force cosine design; Phase 3 built only the write/ingest half | Stage 1, Phase 3's `ingest.py`/DynamoDB schema | No — moto by default, same two-axis pattern as `ingest.py` |
| **4** | **Bedrock model router** (`aws/bedrock_router.py`) implementing `PROMPT-REGISTRY.md` §1's two call paths, plus the **fake-LLM harness** (`agents/testing/fake_llm.py`) it's tested against by default | Stage 1 (`config/` flag), `PROMPT-REGISTRY.md` | No — fake-LLM harness by default |
| **5** | **Guardrails + PII redaction** (`guardrails/`) — `ApplyGuardrail` client wrapper (`ADR-010`'s decoupled call pattern) and PII redaction (`ADR-011`'s boundary table, `DATA-CONTRACTS.md`'s regex detectors) | Stage 1 | No — mocked `ApplyGuardrail` client; **no real Guardrail resource exists to call** (see §2) |
| **6** | **LangGraph nodes** (`agents/nodes/`): L1 safety pre-node (deterministic, `D12`/`D15`, no model call at all); the merged router+L2 node (Stage 4); Guardrails input/output nodes (Stage 5); per-intent nodes — `FileAutoClaim` (Stage 2's policy/claims servers + Stage 1's validators), `CheckClaimStatus` (Stage 2), `CoverageQuestion` (Stage 3 + Stage 2's policy server + Stage 4's generation call, per `DIALOGUE-POLICIES.md` §2's decision path), `RentalTowingEntitlement` (Stage 3 + Stage 2's claims server + Stage 4, per §3), `UpdateContactInfo` (Stage 2's contact server + confirmation policy, §4), `InjuryEscalation` (Stage 2's escalation stub, §5) | **All of Stages 1–5** | No — every dependency stays mocked/local by default |
| **7** | **Graph assembly** (`agents/graph.py`) — wires Stage 6's nodes with conditional edges implementing `DIALOGUE-POLICIES.md`'s full pipeline (§1), the escalation-trigger table (§8), and the retry ceiling (§7) as graph-level control flow, not per-node logic. **DynamoDB checkpointer** (`aws/checkpointer.py`, `langgraph-checkpoint-aws`, `ADR-005`, keyed on Connect contact ID). A thin `structlog` trace at each node transition (full OTel/EMF buildout stays Phase 11's, per the existing roadmap — this is just enough to make Stage 7's own integration tests readable). Integration tests run full simulated conversations through the assembled graph for all six intents plus injury preemption, a barge-in scenario (`DIALOGUE-POLICIES.md` §6), and a retry-ceiling-exhaustion scenario (§7) — the first real exercise of `INTENT-TAXONOMY.md`'s adversarial set, ahead of Phase 6's formal harness | Stage 6 | No — moto-backed checkpointer table |
| **8** | **Real-call verification** (optional, separately cost-gated at close — same pattern as Phases 3–4) — a small number of real Bedrock calls through the **actual shipped `aws/bedrock_router.py` code path**, not a throwaway script, confirming Stage 4's assumptions against the real API | Stage 4, 6, 7 | **Yes — the only stage that spends anything** |

---

## 2. Where the cost gate applies

**Mock-by-default stays the posture for every stage, no exceptions** — the same two-axis pattern Phase 3
established (`--embeddings {mock,bedrock}`, `--vector-store {local,aws}`) extends here: every AWS-touching
component defaults to a local/mocked backend, and switching any one of them to real requires an explicit flag
plus, for anything spending money, a separate approval.

| Component | Ever touches real AWS in Phase 5? | Governing gate |
|---|---|---|
| `models/`, `validation/`, `config/` | No | None — pure Python |
| MCP servers | No | None — local JSON |
| Knowledge retrieval | **No, not even optionally** | Real DynamoDB table creation is Phase 8's, full stop — see below |
| Bedrock router | Optionally, Stage 8 only | **$5 standing cap (Phases 3–7)**, same cap Phases 3–4 already drew from ($0.0001161 consumed to date) |
| Fake-LLM harness | No | None — deterministic, no network |
| Guardrails | **No, not even optionally** | Real Guardrail resource creation is Phase 8's — see below |
| LangGraph nodes/graph/checkpointer | No | Depends only on the above; inherits their postures |

**Two things Phase 5 deliberately never creates, regardless of the standing cap:**

1. **A real DynamoDB table.** The $5 standing approval is scoped explicitly to *"Bedrock on-demand
   inference"* (`CLAUDE.md`) — it does not cover DynamoDB, and `CLAUDE.md` separately states *"provisioned
   resources are still gated individually."* A table is a persistent, named, provisioned resource, not a
   stateless API call — creating one, even a near-free on-demand table, needs its own `APPROVED: <name>`
   moment. That moment is Phase 8's, which already owns the real vector-store table Phase 3's manifest
   anticipates. Phase 5 stays moto-only for every DynamoDB interaction, with no optional real-table step —
   unlike Bedrock, which does get one (Stage 8), because a model inference call and a table-creation API call
   are fundamentally different kinds of "billable."
2. **A real Bedrock Guardrail.** `CreateGuardrail` provisions a named, persistent resource the same way a
   DynamoDB table does — it is not covered by the inference-only standing cap either. `guardrails/` is fully
   built and tested against a mocked `ApplyGuardrail` client in Phase 5; the real Guardrail resource is
   created in Phase 8 alongside the DynamoDB table, with its own approval at that time.

**What this means concretely:** Phase 5 can run start-to-finish, all seven mocked stages, at **$0.00**, same
as Phase 3's default `make ingest` run. Stage 8 is the only point all phase where typing `APPROVED:` again is
even a live question, and it's optional — the phase's exit criteria do not require it, exactly as Phase 3's
didn't require the real-embedding check to complete Phase 3's own content (that check happened as a Marco-
requested closing step, not a blocking exit criterion).

---

## 3. What Phase 5 does not build

Real Connect telephony wiring (contact flows, queue transfer, Lex association) — Phase 8. Full observability
(OTel spans, EMF metrics, dashboards) — Phase 11, beyond the thin Stage 7 trace. The eval harness itself —
Phase 6, though Stage 7's integration tests exercise the same adversarial utterances that harness will later
formalize. Guardrail *tuning* against real utterances — Phase 7. Nothing here is stubbed and left implied as
working; each of these is a named future phase, not a silent gap.
