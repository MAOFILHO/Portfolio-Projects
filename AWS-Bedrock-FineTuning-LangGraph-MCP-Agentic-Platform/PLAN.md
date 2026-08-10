# PLAN.md — AWS-Bedrock-FineTuning-LangGraph-MCP-Agentic-Platform

**Status:** Phase 2 deliverable. Awaiting approval. **Zero implementation code written. Zero resources provisioned.**
**Source of truth:** `UserGuide - Create Bedrock Custom Model with Fine-tuning and Inference.pdf` (117 pages, read end to end).
**Companion files:** [`TASKS.md`](TASKS.md) (execution contract) · [`COSTS.md`](COSTS.md) (approved cost record).

---

## 1. Phase 1 findings — what the guide actually specifies

### 1.1 Scenario count — verified against the guide's own table of contents

The user stated **7 scenarios** (1 primary + 6 optional). **The guide agrees.** Cross-checked against the
Contents block on p.3 and the Summary on p.112:

| # | Guide section | Page | Scenario | Dataset in repo |
|---|---|---|---|---|
| — | §6–§9 (primary walkthrough) | 11–35 | Gardening knowledge assistant | `gardening_lessons.jsonl` |
| 1 | §12 | 41 | Support Ticket Triage | `support_ticket_triage.jsonl` |
| 2 | §13 | 52 | IT / DevOps L1 Helpdesk | `it_helpdesk_l1.jsonl` |
| 3 | §14 | 61 | Pharmacovigilance Adverse-Event Triage | `pharma_adverse_event_triage.jsonl` |
| 4 | §15 | 70 | Patient Message Triage (Clinic Routing) | `patient_message_triage.jsonl` |
| 5 | §16 | 81 | Banking Virtual Assistant | `banking_assistant.jsonl` |
| 6 | §17 | 93 | E-Commerce Product Description Generator | `ecommerce_product_copy.jsonl` |

**7 scenarios, 7 datasets, 1:1 match. No discrepancy.** `CLAUDE.md` also asserts 7 — consistent.

### 1.2 Repetition structure — one pipeline, seven data rows

The guide says so itself (§10, p.36): *"This follows the same flow as the original walkthrough (S3 → Fine-tune job →
Custom model on-demand → Playground test → Clean up), repeated once per scenario. Steps 1–2 are done once;
repeat Steps 3–6 for each dataset."*

Every scenario section (§12–§17) is byte-for-byte the same 20 console steps with three substitutions:
job name, dataset filename, deployment name. **This is a config-driven pipeline, not seven implementations.**

### 1.3 Data schema — read from actual records, not filenames

All seven files are JSONL, one standalone JSON object per line, Bedrock conversation format:

```json
{
  "schemaVersion": "bedrock-conversation-2024",
  "system": [{"text": "<scenario persona + output constraints>"}],
  "messages": [
    {"role": "user",      "content": [{"text": "..."}]},
    {"role": "assistant", "content": [{"text": "..."}]}
  ]
}
```

Verified per file (record counts and measured character volume, tokens estimated at 4 chars/token):

| Dataset | Records | Chars | Est. tokens | Output shape |
|---|---:|---:|---:|---|
| `banking_assistant.jsonl` | 230 | 103,694 | ~25,900 | Prose + mandatory disclaimer sentence |
| `pharma_adverse_event_triage.jsonl` | 210 | 106,639 | ~26,700 | **Strict JSON only** |
| `it_helpdesk_l1.jsonl` | 210 | 88,726 | ~22,200 | Numbered steps + mandatory L2 escalation line |
| `gardening_lessons.jsonl` | 240 | 66,132 | ~16,500 | Prose |
| `support_ticket_triage.jsonl` | 220 | 88,536 | ~22,100 | **Strict JSON only** |
| `ecommerce_product_copy.jsonl` | 220 | 93,281 | ~23,300 | Short copy, word limit |
| `patient_message_triage.jsonl` | 136 | 68,418 | ~17,100 | **Strict JSON only** |

All 7 are inside the Nova 2 Lite fine-tuning quota (20,000 train+validation records, verified live).

### 1.4 Cloud provider and services — evidence

AWS. Guide §7 step 1: *"We are working in the Northern Virginia region"* → **`us-east-1`**, which is also the
only region where Nova custom models can be deployed for on-demand inference (verified in AWS docs).

Services the guide relies on: **Amazon S3** (§6), **Amazon Bedrock model customization** (§7),
**Bedrock Custom Model on-Demand deployment** (§8), **Bedrock Playground / runtime inference** (§9),
**IAM service role** for the customization job (§7 step 10).

### 1.5 Base model — verified live against this account

The guide selects **Nova 2 Lite v1** in every scenario (§7 step 6, and §12–§17 step 3 of each).
Confirmed against the live account (`759316130780`, `us-east-1`):

```
$ aws bedrock list-foundation-models --by-customization-type FINE_TUNING
  amazon.nova-2-lite-v1:0:256k   Nova 2 Lite   Amazon
$ aws bedrock get-foundation-model-availability --model-id amazon.nova-2-lite-v1
  agreementAvailability: AVAILABLE   authorizationStatus: AUTHORIZED
  entitlementAvailability: AVAILABLE regionAvailability: AVAILABLE
```

**Customization base model ID: `amazon.nova-2-lite-v1:0:256k`.** Model access is already granted — this
normally-manual prerequisite is already satisfied on this account.

### 1.6 Billable resources implied by the guide

1. Bedrock **model customization (training)** — per training token, per epoch.
2. Bedrock **custom model storage** — per custom model, per month, charged while the model exists.
3. Bedrock **inference on the deployed custom model** — per input/output token.
4. Bedrock **inference on the base model** (needed for the base-vs-tuned comparison the UX requires).
5. **S3** — dataset objects + job output artifacts (loss metrics), plus the Terraform remote-state bucket.
6. **DynamoDB** — Terraform state lock table (on-demand).
7. **CloudWatch Logs** — observability.
8. **AWS Budgets** — first two budgets are free.

Full costing in [`COSTS.md`](COSTS.md).

### 1.7 Manual-only prerequisites (cannot be automated)

| # | Prerequisite | Status on this account | Automatable? |
|---|---|---|---|
| P1 | AWS account (guide §4) | ✅ `759316130780` | No |
| P2 | Bedrock model access for Nova 2 Lite | ✅ already `AUTHORIZED` | No — console/API agreement |
| P3 | AWS CLI configured, `us-east-1` | ✅ `aws-cli/2.36.13`, region `us-east-1` | No |
| P4 | Service quota: *In-progress custom model deployments* = **2** | ⚠️ hard ceiling of 2 concurrent | Increase is a manual request; **we design around it instead** |
| P5 | Langfuse project + API keys (observability) | ❓ **needs your input** | No |
| P6 | Contoso logo asset for the frontend | ❓ **not present in repo** | No |

P4 is the operationally important one: **three demos cannot be deployed simultaneously without a quota
increase.** The pipeline therefore deploys serially with a wait-for-slot gate (`TASKS.md` Phase 6).

### 1.8 Teardown ordering — the guide is incomplete, and this matters

Guide §19 orders teardown: (a) terminate the custom model, then (b) empty and delete the S3 bucket.
That ordering is correct as far as it goes, **but the guide never tells you to delete the Custom Model
on-Demand deployment**, even though §8 and every scenario section create one.

AWS documentation is explicit: *"After you delete the deployment, you can't use it for on-demand inference,
but deployment deletion doesn't delete the underlying custom model."* A deployment referencing a model
blocks clean model deletion and leaves an orphaned billable footprint.

**Corrected teardown order — enforced in code and asserted by the P0 post-teardown test:**

```
1. DeleteCustomModelDeployment   (all deployments, wait for gone)
2. DeleteCustomModel             (all custom models, wait for gone)
3. Empty S3 data bucket          (all object versions + delete markers)
4. terraform destroy             (bucket, IAM role/policies, budget, logs)
5. Assert zero surviving resources
```

Reversing 1↔2 or 3↔4 hangs the destroy. This is a release blocker, not a nicety.

### 1.9 Conflicts and deviations from the guide — flagged, not silently resolved

| # | Guide says | Problem | Decision |
|---|---|---|---|
| C1 | §3/§5 claim the walkthrough is free and estimate the cost at $0.01 | **False.** Training, custom-model storage ($1.95/model/month), and inference all bill. Free-tier credits mask it, they don't remove it. | Cost honestly in `COSTS.md`. Budget alert is mandatory. |
| C2 | §6 steps 5–6: enable ACLs, **allow public access** to the bucket | Publishing training data to the internet. Bedrock reads via IAM role — public access is not needed and never was. | **Deviate deliberately.** Block Public Access fully on, ACLs disabled (`BucketOwnerEnforced`), SSE-S3, TLS-only bucket policy. Documented in README. |
| C3 | §7 step 8: *"select … the training dataset file **and the validation dataset file**"* | No validation file is supplied for any scenario. Only one `.jsonl` per scenario exists. | Deterministic held-out split → `validation.jsonl`, seedless and stable (no RNG), written next to the training object in S3. Records count against the same 20,000 quota. **Revised during Phase 6:** the original "last 10% of records" rule leaked, because these datasets group one question under several conversational prefixes sharing a gold answer. Superseded by group-aware / stratified splitting — see TASKS.md **6.1a** and `data/splitter.py`. |
| C4 | §19 teardown | Omits the CMoD deployment (see §1.8) | Corrected order above. |
| C5 | §7 step 7 / all scenarios: *"Hyperparameters: leave defaults"* | Default epoch count is not stated anywhere in the guide and drives training cost linearly. | Set **explicitly** in `ScenarioConfig` (never left to a provider default, per skill rule). Cost table brackets 1/2/5 epochs. |
| C6 | Real-Time Scenario (p.1) is gardening | User requires the regulated-industry pipeline narrative in the UI | Frontend copy uses the pipeline story. Gardening remains a valid but **disabled** config. |

---

## 2. The pricing question the skill demands I not get wrong

> ⚠️ The skill warns: *never assume a cheap tier exists.* For fine-tuned Bedrock models this is exactly the
> trap — historically, custom models required **Provisioned Throughput**, billed hourly with no free tier.

**Verified live via the AWS Price List API** (`aws pricing get-products --service-code AmazonBedrock`,
`us-east-1`), not from memory and not from a blog:

| Usage type | Price | Unit |
|---|---:|---|
| `USE1-Nova2.0Lite-Customization-Training` | **$0.00378** | per 1K tokens |
| `USE1-Nova2.0Lite-Customization-Storage` | **$1.95** | per model / month |
| `USE1-Nova2.0Lite-input-tokens-custom-model` | **$0.00030** | per 1K tokens |
| `USE1-Nova2.0Lite-output-tokens-custom-model` | **$0.00250** | per 1K tokens |
| `USE1-Nova2.0Lite-input-tokens` (base) | $0.00033 | per 1K tokens |
| `USE1-Nova2.0Lite-output-tokens` (base) | $0.00275 | per 1K tokens |
| `USE1-Nova2.0Lite-ProvisionedThroughput-NoCommit-ModelUnits` | **$60.50** | per hour ⛔ |

**The good outcome is real and confirmed:** Amazon Nova 2 Lite supports **Custom Model on-Demand (CMoD)**
inference in `us-east-1` — token-billed, **no hourly charge, nothing billed while idle**. AWS docs list
Nova 2 Lite explicitly among CMoD-supported base models, and `CreateCustomModelDeployment` /
`DeleteCustomModelDeployment` are the APIs. Custom-model token rates are *cheaper* than base on-demand rates.

**The avoided disaster, stated plainly:** if we had used Provisioned Throughput instead, three demo models
would cost **3 × $60.50/hr = $181.50/hr → $130,680 for 30 days.** A weekend left running would be **$8,712**.

**Therefore, a hard project invariant:** `aws_bedrock_provisioned_model_throughput` and
`CreateProvisionedModelThroughput` are **forbidden anywhere in this codebase.** A CI grep test fails the
build if either string appears outside `PLAN.md`/`COSTS.md`.

**What actually bills while idle:** `Customization-Storage`, $1.95 per custom model per month — **$5.85/month
for three demos**. That is the entire idle footprint. It is small, but it is not zero, and it is why teardown
must delete custom models and not merely deployments.

---

## 3. Decisions

### 3.1 Language

**Python 3.12.** Determined by: (a) `CLAUDE.md` mandates 3.12; (b) skill default is 3.12. The machine's
default `python3` is **3.13.13** (pyenv) — wrong version, so the venv must be created explicitly from
`pyenv`'s 3.12.10 (`~/.pyenv/versions/3.12.10/bin/python3.12`, verified present). A pre-provision smoke test
asserts `sys.version_info[:2] == (3, 12)` and fails loudly otherwise.

### 3.2 Frontend

**React + TypeScript + Node** (Vite build). No existing frontend is present, so nothing to preserve.
Streamlit explicitly rejected per skill rule. Node v24.15.0 and npm 11.12.1 verified present.

**Layout** — fixed left nav at 18% width:

```
┌──────────────┬───────────────────────────────────────────────────────┐
│ [Contoso]    │                                                       │
│              │   Right content pane — selected demo renders here     │
│  ⌂ Home      │                                                       │
│              │   Phase rail: Model → Dataset → Fine-tune → Deploy    │
│  Banking     │               → Inference → Compare                   │
│  Virtual     │                                                       │
│  Assistant   │   Real job ARNs · real status · real latency (ms)     │
│              │                                                       │
│  IT / DevOps │                                                       │
│  L1 Helpdesk │                                                       │
│              │                                                       │
│  Pharma AE   │                                                       │
│  Triage      │                                                       │
│              │                                                       │
│  18% fixed   │                          82%                          │
└──────────────┴───────────────────────────────────────────────────────┘
```

**⚠️ Open item (P6):** the prompt says *"Match the attached screenshots for layout and login."*
**No screenshots were attached to this session and none exist in the repo.** I have built the layout spec
from the textual description above. If the screenshots exist, supply them before Phase 3 Task 9.1 and I will
match them. Otherwise the frontend ships with an inline-SVG Contoso wordmark placeholder.

**Auth:** hardcoded `demo` / `demo123`, implemented as a deliberately obvious stub in a single file named
`insecure_demo_auth.py`, carrying a module-level banner comment. Never wired to Cognito or IAM. Session is a
client-side flag only — no token, no cookie, no backend identity.

### 3.3 Infrastructure

**Terraform**, remote state in S3 + DynamoDB lock. Idempotent via a stable `project_suffix` variable — a
required input with no default, never a random suffix, never rename-on-collision. Re-running `apply` converges.

**Critical split — what Terraform owns vs. what deterministic Python owns:**

| Concern | Owner | Why |
|---|---|---|
| S3 data bucket, IAM role + policies, budget + alerts, CloudWatch log group, DynamoDB lock table | **Terraform** | Static, declarative, stable |
| Fine-tuning job (`CreateModelCustomizationJob`) | **Python (boto3)** | `aws_bedrock_custom_model` has a **20-minute default create timeout**; the guide measures real training at **~4 hours** (§7 step 12: *"For us, it took 4 hours"*). The UX also requires live status polling with real job IDs, which a blocking `terraform apply` cannot surface. |
| CMoD deployment (`CreateCustomModelDeployment`) | **Python (boto3)** | **No Terraform resource exists** for custom model deployments in the AWS provider. |
| Teardown of models + deployments | **Python (boto3)**, invoked by `make teardown` before `terraform destroy` | Ordering constraint from §1.8 |

This is a deliberate, documented decision — not a gap. Everything Terraform *can* own declaratively, it owns.
The Bedrock lifecycle steps it cannot express are deterministic scripts with no LLM in the path.

### 3.4 Agentic layer — scope fence

LangGraph orchestrator + four focused sub-agents, tools exposed over **MCP**:

| Agent | Responsibility | MCP tools it may call |
|---|---|---|
| `dataset_prep` | Validate JSONL schema, compute train/val split, estimate tokens & cost | `validate_dataset`, `split_dataset`, `estimate_training_cost` |
| `finetune_supervisor` | Launch job, poll status, interpret failure reasons | `start_finetune_job`, `get_job_status`, `read_training_metrics` |
| `evaluation` | Run held-out prompts, score format compliance, diff base vs tuned | `invoke_base_model`, `invoke_tuned_model`, `score_output` |
| `inference` | Serve a single ad-hoc prompt against base + tuned | `invoke_base_model`, `invoke_tuned_model` |

**Hard fence — no LLM performs an AWS mutation.** `start_finetune_job` is the sole exception and it is
*gated*: it will not fire without an explicit typed human approval token carried in the graph state, and it
can only launch a job whose parameters came from an approved `ScenarioConfig`. No agent may touch IAM, S3
lifecycle, budgets, deployments, or any delete API. Teardown has **no agentic path whatsoever** — it is a
plain script. Enforced by an MCP tool allowlist per agent, unit-tested.

### 3.5 Scenarios as data

```python
class ScenarioConfig(BaseModel):
    id: Literal["banking", "it_helpdesk", "pharma", "gardening",
                "support_triage", "patient_triage", "ecommerce"]
    enabled: bool                       # the flag; flipping it is the whole cost of enabling
    display_name: str
    tagline: str
    industry: str
    dataset_path: FilePath
    system_prompt: str                  # must match the dataset's own `system` block
    output_mode: Literal["prose", "strict_json", "numbered_steps", "short_copy"]
    output_schema_ref: str | None       # dotted path to the Pydantic model for strict_json
    validation_rules: list[ValidationRule]
    sample_prompts: list[str]           # lifted verbatim from the guide
    base_model_id: str = "amazon.nova-2-lite-v1:0:256k"
    epochs: int                         # explicit, never a provider default
    validation_split: float = 0.10
```

Seven config entries live in `configs/scenarios/*.yaml`, loaded and validated at startup.
`enabled: true` for banking, it_helpdesk, pharma. `enabled: false` for the other four. Adding an eighth
scenario costs one YAML file and one dataset — no module, no route, no component.

### 3.6 Pydantic validation as a visible feature

Two of three active demos emit strict JSON. Model output is parsed through a scenario-specific Pydantic model
(`PharmaTriageOutput`, `SupportTriageOutput`, `PatientTriageOutput`). On `ValidationError` the API returns
**HTTP 200** with a structured `SchemaViolation` payload — raw model text, the exact Pydantic error path, and
the expected schema — and the UI renders it in an amber "Schema violation caught" panel, not a red error.
**A caught violation is a successful demo.** The API never 500s on malformed model output.

Example — `PharmaTriageOutput`, derived from the dataset's own system prompt:

```python
class PharmaTriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seriousness: Literal["Serious", "Non-serious"]
    event_category: str
    expedited_reporting: bool

    @model_validator(mode="after")
    def expedited_only_when_serious(self) -> Self:
        if self.expedited_reporting and self.seriousness != "Serious":
            raise ValueError("expedited_reporting may be true only when seriousness is 'Serious'")
        return self
```

That cross-field rule is stated in the dataset's system prompt and is a genuine regulatory constraint — an
excellent thing to demonstrate the model occasionally getting wrong.

### 3.7 Observability

- **Infra/API:** OpenTelemetry → CloudWatch (OTLP), plus a console span exporter so **traces are visible in
  the terminal during `make run`**, not only in the console.
- **LLM/agent:** **Langfuse** (self-hosted via `docker-compose` for $0, or Langfuse Cloud free tier).
  Chosen over LangSmith because a Langfuse skill is already available in this environment.
  **⚠️ Needs your input (P5):** Langfuse Cloud keys, or confirmation to self-host locally.
  I will not invent keys or a host.

---

## 4. Architecture

```
                        ┌──────────────────────────────────────────┐
                        │  React + TypeScript (Vite)  · Contoso     │
                        │  18% fixed left nav │ 82% content pane    │
                        │  demo/demo123 stub login (insecure)       │
                        └────────────────────┬─────────────────────┘
                                             │ REST + SSE (JSON, Pydantic-typed both ways)
                        ┌────────────────────▼─────────────────────┐
                        │  FastAPI (Python 3.12, Pydantic v2)       │
                        │  /scenarios /dataset /finetune /deploy    │
                        │  /infer /compare /teardown-status         │
                        └───────┬────────────────────────┬─────────┘
                                │                        │
                 ┌──────────────▼─────────┐   ┌──────────▼──────────────┐
                 │ LangGraph orchestrator │   │ Deterministic AWS layer │
                 │  ├ dataset_prep        │   │  (boto3, NO LLM)        │
                 │  ├ finetune_supervisor │   │  ├ finetune_client      │
                 │  ├ evaluation          │   │  ├ deployment_client    │
                 │  └ inference           │   │  └ teardown (ordered)   │
                 └──────────┬─────────────┘   └──────────┬──────────────┘
                            │ MCP (allowlisted tools)    │
                 ┌──────────▼─────────────┐              │
                 │ MCP servers            │              │
                 │  dataset · bedrock · eval ────────────┘
                 └────────────────────────┘
                            │
        ┌───────────────────┼────────────────────────────────────┐
        │                   │                                    │
┌───────▼──────┐  ┌─────────▼─────────────┐  ┌──────────────────▼────────┐
│ S3 data      │  │ Bedrock customization │  │ Bedrock CMoD deployment    │
│ training-    │  │ Nova 2 Lite           │  │ token-billed, $0 idle      │
│ data/ output/│  │ $0.00378 / 1K tok     │  │ $0.00030 in / $0.00250 out │
└──────────────┘  └───────────────────────┘  └────────────────────────────┘
        │
┌───────▼───────────────────────────────────────────────────────────────┐
│ Terraform: S3 · IAM role · AWS Budget + alerts · CloudWatch · DynamoDB │
└───────────────────────────────────────────────────────────────────────┘

Observability: OTel → CloudWatch + terminal spans │ Langfuse → agent/LLM traces
```

### Data flow — one demo click-through

```
1. Select Foundation Model   → GET  /scenarios/{id}          → shows amazon.nova-2-lite-v1:0:256k
2. Load / inspect dataset    → POST /dataset/{id}/validate   → dataset_prep agent: schema check,
                                                                 record count, token + cost estimate
3. Approve cost              → POST /finetune/{id}/approve   → typed approval token → graph state
4. Launch fine-tune          → POST /finetune/{id}/start     → CreateModelCustomizationJob → real jobArn
5. Poll status               → GET  /finetune/{id}/status    → SSE: InProgress → Completed (~4h)
6. Deploy                    → POST /deploy/{id}             → CreateCustomModelDeployment → real ARN
7. Run inference             → POST /infer/{id}              → base + tuned in parallel, real latency
8. Compare                   → UI side-by-side + Pydantic verdict per side
9. Teardown                  → make teardown                 → ordered destroy + zero-footprint assert
```

---

## 5. File tree

```
AWS-Bedrock-FineTuning-LangGraph-MCP-Agentic-Platform/
├── CLAUDE.md                          # PRESERVED — read-only project law, never overwritten
├── PLAN.md  TASKS.md  COSTS.md
├── README.md  CHANGELOG.md  LICENSE  .gitignore  .env.example
├── Makefile                           # setup provision run teardown test
├── pyproject.toml  requirements.txt  requirements-dev.txt
├── Dockerfile  docker-compose.yml     # api + frontend + langfuse (self-host option)
├── data/
│   ├── banking_assistant.jsonl              (ACTIVE)
│   ├── it_helpdesk_l1.jsonl                 (ACTIVE)
│   ├── pharma_adverse_event_triage.jsonl    (ACTIVE)
│   ├── gardening_lessons.jsonl              (disabled)
│   ├── support_ticket_triage.jsonl          (disabled)
│   ├── patient_message_triage.jsonl         (disabled)
│   └── ecommerce_product_copy.jsonl         (disabled)
├── configs/
│   ├── settings.yaml
│   └── scenarios/                     # 7 YAML files — scenarios are DATA
│       ├── banking.yaml  it_helpdesk.yaml  pharma.yaml
│       ├── gardening.yaml  support_triage.yaml
│       ├── patient_triage.yaml  ecommerce.yaml
├── src/bedrock_platform/
│   ├── __init__.py  __main__.py
│   ├── config/        settings.py  scenario_loader.py  scenario_config.py
│   ├── models/        # Pydantic v2 — every boundary
│   │   ├── api.py  agent_io.py  tool_io.py  bedrock.py
│   │   └── outputs/   pharma.py  support_triage.py  patient_triage.py
│   │                  banking.py  it_helpdesk.py  ecommerce.py  gardening.py
│   ├── aws/           # deterministic, NO LLM
│   │   ├── session.py  s3_client.py  finetune_client.py
│   │   ├── deployment_client.py  inference_client.py
│   │   ├── cost_estimator.py  teardown.py
│   │   └── guards.py            # forbids Provisioned Throughput at runtime
│   ├── agents/        graph.py  state.py  dataset_prep.py
│   │                  finetune_supervisor.py  evaluation.py  inference.py
│   ├── mcp/           server_dataset.py  server_bedrock.py  server_eval.py
│   │                  allowlist.py
│   ├── validation/    schema_guard.py  violation.py  rules.py
│   ├── observability/ otel.py  langfuse_setup.py  console_spans.py
│   └── api/           app.py  deps.py  insecure_demo_auth.py
│                      routes/ scenarios.py dataset.py finetune.py
│                              deploy.py infer.py health.py
├── infra/terraform/
│   ├── backend.tf  providers.tf  versions.tf
│   ├── main.tf  variables.tf  outputs.tf
│   ├── terraform.tfvars.example
│   ├── bootstrap/                 # one-time: state bucket + DynamoDB lock
│   └── modules/
│       ├── s3_data/  iam_bedrock_role/  budget_alerts/  observability/
├── scripts/
│   ├── bootstrap_state.sh  preflight.py  run_pipeline.py
│   ├── teardown.py  verify_empty.py  print_cost_estimate.py
├── frontend/
│   ├── package.json  tsconfig.json  vite.config.ts  index.html
│   └── src/
│       ├── main.tsx  App.tsx  theme/contoso.css
│       ├── api/client.ts  api/types.ts     # mirrors Pydantic models
│       ├── components/ LeftNav.tsx  ContosoLogo.tsx  LoginStub.tsx
│       │               PhaseRail.tsx  DatasetInspector.tsx
│       │               JobStatusPanel.tsx  ComparePane.tsx
│       │               SchemaViolationPanel.tsx  CostBanner.tsx
│       └── pages/      Home.tsx  DemoScenario.tsx
├── tests/
│   ├── unit/           test_scenario_config.py  test_output_models.py
│   │                   test_schema_guard.py  test_cost_estimator.py
│   │                   test_agent_allowlist.py  test_no_provisioned_throughput.py
│   ├── pre_provision/  test_python_version.py  test_aws_auth.py
│   │                   test_region.py  test_model_access.py  test_quotas.py
│   ├── post_provision/ test_resources_live.py  test_approved_skus.py
│   │                   test_bucket_not_public.py  test_budget_exists.py
│   ├── post_run/       test_outputs_exist.py  test_job_completed.py
│   │                   test_inference_returns.py
│   └── post_teardown/  test_zero_resources.py         # P0 RELEASE BLOCKER
└── .github/workflows/  ci.yml  terraform.yml          # validate + plan ONLY
```

**Estimated file count: ~150** (≈95 Python/config, ≈30 frontend, ≈15 Terraform, ≈10 root docs/tooling).

---

## 6. Pinned versions

Resolved live from PyPI on 2026-08-02. Exact pins, no ranges.

**`requirements.txt`**
```
fastapi==0.141.1
uvicorn[standard]==0.52.1
pydantic==2.13.4
pydantic-settings==2.14.2
boto3==1.43.62
langgraph==1.2.10
langchain-core==1.5.3
langchain-aws==1.6.4
mcp==2.0.0
langfuse==4.14.2
opentelemetry-sdk==1.44.0
opentelemetry-exporter-otlp==1.44.0
opentelemetry-instrumentation-fastapi==0.65b0
python-dotenv==1.2.2
structlog==26.1.0
tenacity==9.1.4
pyyaml==6.0.3
```

**`requirements-dev.txt`**
```
pytest==9.1.1
pytest-asyncio==1.4.0
httpx==0.28.1
moto==5.2.2
ruff==0.16.1
mypy==2.3.0
boto3-stubs[bedrock,bedrock-runtime,s3,dynamodb]==1.43.62
```

**Toolchain (verified present):** Python 3.12.10 (pyenv) · Terraform 1.15.8 · Node 24.15.0 · npm 11.12.1 ·
Docker 29.5.1 · AWS CLI 2.36.13.
**Terraform:** `hashicorp/aws ~> 6.0`, `required_version >= 1.9.0`.
**Frontend:** React 19 · TypeScript 5.9 · Vite 7 (exact patch pins written at Task 9.1 from `npm view`).

---

## 7. Terraform resources to be created

| Resource | Type | SKU / tier chosen | Note |
|---|---|---|---|
| Data bucket | `aws_s3_bucket` | S3 Standard | Holds `training-data/`, `validation-data/`, `output/` |
| — public access | `aws_s3_bucket_public_access_block` | all four blocks `true` | **Deviates from guide §6 (C2)** |
| — ownership | `aws_s3_bucket_ownership_controls` | `BucketOwnerEnforced` | ACLs disabled |
| — encryption | `aws_s3_bucket_server_side_encryption_configuration` | `AES256` (SSE-S3, free) | Not KMS — KMS adds per-request cost |
| — TLS policy | `aws_s3_bucket_policy` | deny non-TLS | |
| — lifecycle | `aws_s3_bucket_lifecycle_configuration` | expire `output/` at 30d, abort MPU 7d | Caps drift |
| Bedrock service role | `aws_iam_role` + `aws_iam_role_policy` | least privilege | S3 read on data prefix, write on output prefix only |
| Budget | `aws_budgets_budget` | COST, monthly | **Created before any billable resource** |
| Budget alerts | notifications | 50% / 80% / 100% actual + 100% forecast → email | |
| Log group | `aws_cloudwatch_log_group` | 7-day retention | Retention set explicitly — never provider default |
| State bucket | `aws_s3_bucket` (bootstrap) | S3 Standard + versioning | One-time |
| State lock | `aws_dynamodb_table` (bootstrap) | **`PAY_PER_REQUEST`** | Never provisioned capacity |

**Explicitly NOT created, ever:** `aws_bedrock_provisioned_model_throughput`. CI greps for it.

---

## 8. Test strategy

| Suite | When | Key assertions |
|---|---|---|
| **unit** | always, no AWS | Pydantic models; all 7 configs load; 3 enabled; strict-JSON models reject bad payloads; agent tool allowlist; no `ProvisionedThroughput` string in `src/` or `infra/` |
| **pre_provision** | before `make provision` | Python is 3.12; `sts get-caller-identity` succeeds; region is `us-east-1`; Nova 2 Lite `AUTHORIZED`; quota *in-progress deployments* ≥ 2; required env vars set |
| **post_provision** | after `make provision` | Bucket exists **and is not public**; DynamoDB is `PAY_PER_REQUEST`; budget exists with the approved ceiling; IAM role assumable by `bedrock.amazonaws.com`; log group retention == 7 |
| **post_run** | after `make run` | Job status `Completed`; custom model ARN resolves; deployment `Active`; `output/` artifacts non-empty; tuned inference returns non-empty text; strict-JSON scenarios parse or produce a well-formed `SchemaViolation` |
| **post_teardown** | after `make teardown` | **P0.** `list_custom_model_deployments` == 0 · `list_custom_models` == 0 · data bucket gone · IAM role gone · `terraform state list` empty. Ordering regression test: deleting a model with a live deployment is attempted and asserted to be handled. |

---

## 9. Decisions received from the user (2026-08-02)

| # | Question | **Decision** | Consequence |
|---|---|---|---|
| **Q1** | Monthly budget ceiling | **$25/month** | ~4.3× headroom over the $5.85/mo idle burn. Alerts at 50% ($12.50) / 80% ($20) / 100% ($25) actual + 100% forecast. Tighter than my recommendation — noted below. |
| **Q2** | Epoch count | **2 epochs** | Training across all 3 demos = **$0.57**. Written explicitly into every `ScenarioConfig`; never left to a provider default. |
| **Q3** | Langfuse | **Langfuse Cloud** | ⚠️ **Blocks Phase 7.** Requires `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` in `.env`. I will not invent them. Everything through Phase 6 proceeds without them. |
| **Q4** | Reference screenshots | ❓ **still outstanding** | None were attached to the session and none are in the repo. Phase 9 proceeds against the §3.2 layout spec with an inline-SVG Contoso wordmark unless supplied first. |
| **Q5** | Rollout | **All three demos in this build** | ~12h training wall-clock. Deployments **must be serialized** — the *In-progress custom model deployments* quota is **2**. `deployment_client.py` waits for a free slot; it must never fire three in parallel. |

### Note on the $25 ceiling

$25 is workable and I'll build to it, but it is worth knowing where it sits. Steady-state idle is **$5.85/month**
(3 × custom model storage), so the 50% alert at $12.50 will **not** fire from normal operation. What could
reach it: repeated retraining (~$0.19/demo/run) combined with heavy demo inference, or leaving the three
custom models in place for **four-plus months** without teardown. Both are exactly the conditions you want an
alert for, so $25 is a reasonable tripwire rather than a nuisance threshold.

**Still needed before Phase 4:** the **email address** for budget notifications. `djmau1974@gmail.com` is on
file for this session — confirm or replace it. I will not hardcode it unasked.

### Outstanding blockers by phase

| Needed before | What | Impact if missing |
|---|---|---|
| **Phase 4** (Terraform) | Budget alert email | Cannot create `aws_budgets_budget` — hard stop, the budget must exist before anything billable |
| **Phase 7** (agents) | Langfuse Cloud keys | Agent tracing unwired; Phases 1–6 unaffected |
| **Phase 9** (frontend) | Reference screenshots + Contoso logo | Falls back to the §3.2 spec and an inline-SVG placeholder |

**Assumptions I am making unless you say otherwise** — all cost-relevant, all listed in `COSTS.md`:

- Tokens estimated at **4 characters/token**; Bedrock's tokenizer will differ by roughly ±15%.
- Training tokens billed = dataset tokens × epochs.
- `Customization-Storage` ($1.95/model/month) is prorated for partial months.
- Region `us-east-1` for everything (required for Nova CMoD).
- Demo inference volume ≈ 200 invocations per session, ~400 input / ~300 output tokens each, run against
  **both** base and tuned models for the comparison view.
- Free-tier credits may absorb these charges on this account; the cost table reports **list price**, because
  credits are finite and are not a pricing tier.

---

## 10. Phase 2 checklist

| # | Item | Where |
|---|---|---|
| 1 | Language version + how determined | §3.1 |
| 2 | Cloud provider + evidence | §1.4 |
| 3 | Frontend decision + reason | §3.2 |
| 4 | Full folder/file tree | §5 |
| 5 | `requirements.txt` pinned | §6 |
| 6 | Cost table, bolded totals, >$50/mo flags | `COSTS.md` |
| 7 | Budget ceiling + alert plan | §9 Q1, `COSTS.md` §5 |
| 8 | Terraform resources | §7 |
| 9 | APIs / accounts / approvals needed first | §1.7, §9 |
| 10 | All assumptions incl. pricing | §9, `COSTS.md` §6 |
| 11 | Estimated file count | §5 (~150) |

---

**⛔ HARD STOP — Phase 2 gate.**
No implementation code and no provisioning until you approve **both** this plan **and** the cost estimate in
[`COSTS.md`](COSTS.md), and answer Q1–Q5.
