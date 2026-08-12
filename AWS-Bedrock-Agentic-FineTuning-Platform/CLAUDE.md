# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This repository is being built into a **production-grade Python project** — `AWS-Bedrock-Agentic-FineTuning-Platform` — derived from a hands-on guide: *"Create a Bedrock Custom Model with Fine-tuning and Inference"*.

Current contents are **source inputs**, not the finished project:

- `UserGuide - Create Bedrock Custom Model with Fine-tuning and Inference.pdf` — the source guide. This is the **functional spec**. Its step-by-step AWS console instructions define what the automated pipeline must replicate.
- Seven `.jsonl` fine-tuning datasets — the training data, one per scenario.
- `README_Template.md` — the required template for the project README.

Build tooling (`pyproject.toml`, Terraform modules, GitHub Actions workflows, frontend scaffolding, test suites) **does not exist yet and is expected to be created.** Scaffold it as required by `TASKS.md` — do not treat its absence as a signal to avoid creating it.

The build is planned in `PLAN.md`, sequenced in `TASKS.md`, and costed in `COSTS.md`. Those three files are the contract.

## Target architecture

- **Backend:** Python 3.12 + FastAPI, Pydantic v2 on every boundary
- **Agentic layer:** LangGraph orchestrator + task-specific sub-agents, tools exposed via MCP — scoped to the ML workflow only
- **IaC:** Terraform, remote state in S3 + DynamoDB lock
- **Frontend:** React + TypeScript + Node, Contoso theme, fixed left nav + right content pane
- **CI/CD:** GitHub Actions (validate and plan only — never apply)
- **Cloud:** AWS, region `us-east-1`, Amazon Bedrock

## Scenario model

The guide contains **7 scenarios**: a primary gardening walkthrough plus 6 optional industry scenarios. All seven follow an **identical pipeline** — S3 upload → fine-tune job → deploy for inference → validate → teardown.

They are implemented as **one config-driven pipeline**, never as separate implementations. A Pydantic `ScenarioConfig` model carries dataset path, system prompt, expected output schema, validation rules, and display metadata. **Scenarios are data, not code** — adding one costs a config entry, not a new module.

### Dataset inventory

| File | Scenario | Status | Output format |
|---|---|---|---|
| `banking_assistant.jsonl` | Banking Virtual Assistant | **ACTIVE DEMO** | Prose + fixed compliance disclaimers |
| `it_helpdesk_l1.jsonl` | IT / DevOps L1 Helpdesk | **ACTIVE DEMO** | Numbered steps + fixed L2 escalation line |
| `pharma_adverse_event_triage.jsonl` | Pharmacovigilance Adverse-Event Triage | **ACTIVE DEMO** | Strict JSON only |
| `gardening_lessons.jsonl` | Gardening knowledge assistant (guide's primary) | Config only, disabled | Prose, analogy-driven |
| `support_ticket_triage.jsonl` | Support Ticket Triage | Config only, disabled | Strict JSON only |
| `patient_message_triage.jsonl` | Patient Message Triage (Clinic Routing) | Config only, disabled | Strict JSON only |
| `ecommerce_product_copy.jsonl` | E-Commerce Product Description Generator | Config only, disabled | Short copy, word limit |

Disabled scenarios must be valid configs that work when a flag is flipped — no code change required to enable one.

**Frontend narrative uses the pipeline story** (fine-tuning a foundation model for a specialized business domain), **not** the gardening framing from the guide's Real-Time Scenario.

### Shared record schema

Every line in every `.jsonl` file is a standalone JSON object in Bedrock's conversation fine-tuning format:

```json
{
  "schemaVersion": "bedrock-conversation-2024",
  "system": [{"text": "<scenario-specific system prompt>"}],
  "messages": [
    {"role": "user", "content": [{"text": "..."}]},
    {"role": "assistant", "content": [{"text": "..."}]}
  ]
}
```

The `system` prompt encodes the scenario's persona and output constraints. When adding or editing examples, preserve this exact structure and stay consistent with that file's existing `system` prompt and output format. Several scenarios are strict-JSON-only — those examples must contain no prose outside the JSON payload. Record count and formatting affect Bedrock-side fine-tuning job validation.

## Reference pipeline (from the guide)

1. Create/reuse an S3 bucket and upload the scenario's `.jsonl` file
2. Create a Bedrock custom model fine-tuning job pointing at that S3 data
3. Deploy the resulting custom model for inference
4. Validate responses
5. Clean up: **terminate the custom model / provisioned throughput FIRST, then delete the S3 bucket**

Teardown order is not optional — reversing it hangs the destroy.

---

## Project Invariants — non-negotiable

### Cost control
- Never run `terraform apply`, launch a Bedrock fine-tuning job, or allocate
  Provisioned Throughput without first printing a cost estimate and receiving
  explicit typed approval.
- Provisioned Throughput bills hourly with no free tier. Any code path that
  creates it must have a matching teardown path in the same PR.
- Prefer smallest viable instance sizes, shortest training runs, and smallest
  eval datasets that still demonstrate the concept.
- Three active demos means three training jobs and three deployments. Flag the
  cumulative cost before provisioning more than one.

### Infrastructure
- Terraform is declarative. Idempotency comes from stable naming + remote state,
  never from runtime rename-on-collision logic.
- No LLM/agent may execute an AWS mutation. Agents orchestrate ML workflow steps
  only; infra changes are deterministic scripts.
- `terraform destroy` must leave a verifiably empty footprint; the post-teardown
  test is a release blocker.
- GitHub Actions runs `validate` and `plan` only. Never `apply` from CI.

### Code
- Python 3.12. Pydantic v2 on every boundary — API, agent I/O, tool calls.
- Schema validation failures are surfaced in the UI as a demonstrated feature,
  not swallowed. A caught malformed model response is a successful demo.
- Secrets in `.env` only. Never hardcoded, never committed, `.env.example` only.
- The `demo`/`demo123` login is a deliberate insecure stub. Label it as such in
  code. Do not connect it to real identity services.

### Execution discipline
- `TASKS.md` is the contract. Work tasks in order, check them off as completed,
  and do not add scope that isn't in the file.
- Stop and ask when uncertain. Do not invent defaults for credentials, region,
  model IDs, or dataset paths.
- Never claim a step succeeded without running its verification command and
  showing the output.
