# AWS-Insurance-FNOL-Voice-Agentic-AI

An agentic, voice-first **First Notice of Loss (FNOL)** intake system for P&C auto insurance, built on
Amazon Connect, Amazon Lex V2, Amazon Bedrock and LangGraph.

> **Status: Phase 0 of 13 complete — analysis and workspace scaffolding only.**
> No application code exists yet and no billable AWS resource has been created.
> This README is a stub; the full clone-to-live-call guide is written in Phase 12.
>
> **Start here instead: [`PROJECT_STATE.md`](PROJECT_STATE.md)** — current phase, decisions, risks and open questions.

---

## What this will be

A caller dials a real number and reaches an AI agent that understands intent, retrieves grounded answers from
policy documents, calls backend tools, handles interruption and fallback, escalates to a human when
appropriate, and emits full traces and transcripts to a dashboard.

Scope is **P&C auto only** — health and life claims are out of scope — across exactly six intents:

1. File a new auto claim (multi-slot: policy number, date/time, location, vehicles, injuries)
2. Check claim status (tool call)
3. Coverage question (RAG against synthetic policy wordings)
4. Rental / towing entitlement (RAG + tool call)
5. Update contact info (write path, explicit confirmation)
6. Injury or fatality mentioned — immediate hard-coded escalation from any state

It is a **portfolio-grade prototype**: small scale, minimal cost, architecturally honest. Everything a
production system would have is present and *functional* — IaC, CI/CD, evals, guardrails, observability,
tests, runbooks — just sized down. Nothing is stubbed out and labelled "production would do X here."

---

## Constraints that shape every decision

| Constraint | Value |
|---|---|
| Hard monthly budget | **$25 USD** — a ceiling, not a target |
| Region | `us-west-2` (single region; Bedrock via `us.*` cross-region inference profiles) |
| Telephony | Connect instance and DID are **pre-provisioned** — never created, never destroyed |
| Call recording | **Disabled**, enforced by a CI check |
| Infrastructure | 100% IaC (Terraform); zero portal clicks |
| Backend / frontend | Python 3.12 · React + TypeScript + Vite |

Cost reality worth stating up front: **telephony is roughly 92% of the ~$0.20 marginal cost per
conversation** — Bedrock is noise by comparison. The call simulator is therefore the primary cost control,
not a convenience, and real calls are reserved for demo and verification.

---

## Phase 0 findings

Eight AWS sample repositories were read and assessed. All are MIT-0, so there are no licence
incompatibilities. Of 100 meaningful modules: **20 KEEP · 22 REFACTOR · 5 REWRITE · 53 DISCARD** — about
**97% discarded by lines of code**, since the discards include entire EKS/Fargate deployments and three
Create React App frontends while the keeps are small schemas, prompts, taxonomies and fixtures.

Four findings materially shaped the plan:

- The nominal "richest agentic source" repository **contains no Bedrock at all** — it runs a self-hosted Ollama pod on GPU nodes, and its LangGraph code is partly non-functional. The entire Bedrock, checkpointing, guardrails, RAG, eval and MCP layer is greenfield. **No source repo uses MCP.**
- The pre-provisioned DID is a **Canada** number, so the assumed US telephony rates do not apply.
- Terraform's `aws_lexv2models_*` resources carry open bugs precisely where this project needs them (prompt specifications, DTMF/barge-in attempt specs, and an intent↔slot circular dependency). The proposed resolution keeps Terraform as the single IaC tool while defining the bot as one nested CloudFormation `AWS::Lex::Bot` resource.
- The 12-month AWS free tier no longer exists in its old form, and **Lex V2 has no perpetual free tier** — every speech request costs from turn one.

Also worth knowing: across all eight repos combined there is **no prior art whatsoever** for barge-in, DTMF,
timeout/no-match configuration, streaming, or interim audio fillers — and rental/towing coverage, which two
of the six intents depend on, is never mentioned. Those are authored from scratch.

Details:

| Document | Contents |
|---|---|
| [`docs/phase0/MERGE-MATRIX.md`](docs/phase0/MERGE-MATRIX.md) | Per-module verdicts with reasons; discard rate reported both ways |
| [`docs/phase0/DEPENDENCY-CONFLICTS.md`](docs/phase0/DEPENDENCY-CONFLICTS.md) | Ten conflict classes and their resolutions |
| [`docs/phase0/DOMAIN-ARTIFACTS.md`](docs/phase0/DOMAIN-ARTIFACTS.md) | FNOL sequences, KABCO injury scale, coverage taxonomy, business rules, PII taxonomy |
| [`docs/phase0/SECURITY-FINDINGS.md`](docs/phase0/SECURITY-FINDINGS.md) | Do-not-propagate list, critical findings, PII gate ruling |
| [`docs/phase0/TARGET-LAYOUT.md`](docs/phase0/TARGET-LAYOUT.md) | Target layout and old→new path mapping |

**All data in this project is synthetic.** No real customer, policy or vehicle data is used. See the
attestation in `DOMAIN-ARTIFACTS.md`.

---

## Commands

Not yet functional — implemented across Phases 5–11.

```bash
make bootstrap    # one-time local + state backend setup
make deploy       # provision everything destroyable      (alias: provision)
make destroy      # return to $0; never touches the protected telephony stack (alias: teardown)
make simulate     # replay conversations locally, no AWS spend
make eval         # eval report with real numbers
make redteam      # guardrail effectiveness report
make test lint typecheck
```

---

## Repository context

This project is one top-level folder in the [`MAOFILHO/Portfolio-Projects`](https://github.com/MAOFILHO/Portfolio-Projects)
monorepo. GitHub Actions reads workflows only from the repository root, so this project's workflows live in
`.github/workflows-for-monorepo-root/` and are copied to the root on install — see the README in that
directory.

Conventions, commands and the full constraint set are in [`CLAUDE.md`](CLAUDE.md).
