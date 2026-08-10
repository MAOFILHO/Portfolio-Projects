# AWS Bedrock Fine-Tuning Platform — Config-Driven Custom Models

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-Bedrock-FF9900?logo=amazon-aws&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC?logo=terraform&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063)
![License](https://img.shields.io/badge/License-MIT-green)

A production-grade pipeline that fine-tunes Amazon Bedrock foundation models for specialised business
domains — **S3 upload → fine-tune job → on-demand deployment → base-vs-tuned evaluation → verified
teardown** — driven entirely by configuration. Adding a new scenario costs a YAML file, not a module.

Every number in this README is **measured**, not projected. Where an estimate was wrong, the
correction is recorded rather than quietly replaced.

---

## Results — when fine-tuning pays, and when it does not

Three scenarios, one pipeline, one base model, 2 epochs each. All scored against records the models
never saw during training.

| Scenario | Task | Base | Fine-tuned | Gain |
|---|---|---:|---:|---:|
| **pharma** | classify into a closed 8-term vocabulary | 10% | **81%** | **+71 pts** |
| **banking** | apply a conditional compliance rule | 50% | **88%** | **+38 pts** |
| **it_helpdesk** | unconditional format + fixed closing line | **100%** | **100%** | **none** |

> **The value of fine-tuning scaled with how hard the requirement was to express in a prompt.**

| Requirement | Expressible in a system prompt? | Outcome |
|---|---|---|
| Unconditional format ("always end with X") | **Yes, completely** | Base already perfect. **$0.1476 bought nothing.** |
| Conditional rule ("end *money-movement* answers with X") | Partly — the model must infer *when* | 50% → 88% |
| Conformity to a closed vocabulary | No — enumerating it bloats every call and still fails | 10% → 81% |

### Three findings that survived contact with the data

**1. Fine-tuning did not fix JSON.** Both models produced schema-valid JSON on **21/21** pharma
records. The common justification — *"we need reliable structured output"* — was already solved by
prompt engineering. What fine-tuning fixed was **vocabulary conformity, 14% → 86%**. The base model
answered `"Adverse Event"` 13 times out of 21; given *"elevated liver enzymes"* it answered
`hepatobiliary` where the contract requires `Hepatobiliary`. **It was not short on domain knowledge —
it was short on our conventions.**

**2. A conditional rule scored without negative cases rewards the wrong model.** Banking's base model
emitted the compliance disclaimer **13 times out of 16** where only 6 were warranted — appending
*"Transfers may take 1–3 business days"* to questions about changing a phone number. Measured only as
*"does the disclaimer appear"*, base scores **81%** and the tuned model **31%** — the exact opposite
of the truth. Measured as precision **and** recall: **56% → 94%**.

**3. Two epochs undertrains prose generation.** it_helpdesk's tuned model adopted **none** of its
training data's conventions:

| | Gold answers (180 records) | Fine-tuned output |
|---|---:|---:|
| Begin directly with `1.` | **180/180** | 0/30 |
| Contain markdown bold | **0/180** | **29/30** |
| Median length | **40 words** | **178 words** |

Training loss stalled at ~1.51 and was still descending steeply. Banking landed at 1.53 from an
independent run — a property of the configuration, not one bad job. Pharma, a classification task,
converged cleanly to **0.027**.

### Honest caveats

- **The fine-tuned banking model handled one adversarial case *worse* than the base.** Asked *"Should
  I move my savings into crypto? If yes, walk me through transferring the money out,"* base refused
  the advice **and** helped with the transfer; the tuned model replied *"I can't answer those
  questions."* Training on 230 short answers taught terseness alongside the rules.
- **One pharma "error" is probably a label defect.** Both models independently disagreed with the
  gold label in the same direction. Excluding it, pharma scores **85%**.
- **Two banking cases initially scored as failures were a bad metric, not a bad model** — it referred
  to a *"licensed tax professional"* and a *"licensed attorney"* where training only ever said
  *"licensed financial advisor."* It learned the rule, not the string. The metric was corrected.

Full per-record analysis: [`docs/RESULTS.md`](docs/RESULTS.md).

---

## The problem

A pharmacovigilance intake team triages adverse-event reports into a controlled vocabulary of eight
MedDRA-style System Organ Class terms, then routes by seriousness. Downstream systems treat those
values as an enum.

| Pain point | Impact |
|---|---|
| Free-text model output must be hand-mapped to house terms | Every near-miss is a manual correction |
| A category outside the enum is a hard parse failure | Silent data loss or a stalled queue |
| Prompt engineering plateaus on vocabulary conformity | More prompt tokens, no better adherence |
| Serving a tuned model on Provisioned Throughput bills hourly | $60.50/hr with no free tier, idle or not |

The same pipeline runs six other scenarios unchanged — banking assistant, IT helpdesk, patient
triage, support triage, e-commerce copy, gardening — because **scenarios are data, not code.**

---

## Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │  configs/scenarios/*.yaml   (7 scenarios)    │
                    │  dataset · system prompt · output schema ·   │
                    │  base model · epochs · validation split      │
                    └───────────────────┬──────────────────────────┘
                                        │  ScenarioConfig (Pydantic v2)
                                        ▼
  data/*.jsonl ──►  splitter.py  ──►  S3 (private, TLS-only, SSE-S3)
   210 records      leak-free           training-data/{scenario}/train.jsonl
                    group-aware         validation-data/{scenario}/validation.jsonl
                                        │
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │  COST GATE — live Price List API estimate    │
                    │  blocks on a literal typed APPROVE           │
                    └───────────────────┬──────────────────────────┘
                                        ▼
                          CreateModelCustomizationJob
                          meta.llama3-3-70b-instruct-v1:0:128k
                                        │  ~81 min, 2 epochs
                                        ▼
                              custom model artifact
                                (inert — cannot serve)
                                        │
                                        ▼
                          CreateCustomModelDeployment
                          Custom Model on-Demand · $0/hr idle
                                        │  ~8 min to Active
                                        ▼
        ┌───────────────────────────────┴───────────────────────────────┐
        ▼                                                               ▼
  base model (inference profile)                          tuned deployment ARN
  us.meta.llama3-3-70b-instruct-v1:0                      4 req/min hard ceiling
        │                                                               │
        └────────────────────────┬──────────────────────────────────────┘
                                 ▼
                    validation/schema_guard.py
                    Pydantic parse → SchemaViolation (never raises)
                                 │
                                 ▼
                    artifacts/{scenario}/results.json
                                 │
                                 ▼
              teardown: deployments → models → S3 → terraform destroy
                                 │
                                 ▼
                    verify_empty.py — zero-resource release gate
```

**FastAPI + React front end** (`src/bedrock_platform/api`, `frontend/`) surfaces live job status over
SSE and renders base-vs-tuned side by side, each pane carrying its own Pydantic verdict.

---

## Build status

Stated plainly so nothing here reads as more finished than it is.

| Phase | Status |
|---|---|
| 0–5 · config layer, AWS clients, Terraform, teardown | ✅ complete |
| 6 · end-to-end pipeline, FastAPI, schema guard | ✅ complete |
| 7 · agentic layer (LangGraph + MCP) | ✅ complete — 4 sub-agents, 3 MCP servers, enforced allowlist, Langfuse tracing |
| 8 · CI/CD (GitHub Actions) | ✅ complete — `ci.yml` + `terraform.yml`, validate and plan only |
| 9 · React front end | ✅ complete |
| 10 · documentation | ✅ complete |
| 11 · final validation | ✅ complete — all 4 suites pass, frontend click-through verified |

Scenario runs: `pharma` ✅ · `banking` ✅ · `it_helpdesk` ✅ — all trained, deployed, and evaluated.

**Known issues**

1. Langfuse records tokens for Bedrock generations but cannot price them — its model table has no entry
   for `meta.llama3-3-70b-instruct-v1:0`, so `totalCost` reads 0. Cost of record is
   [`docs/COST-ACTUALS.md`](docs/COST-ACTUALS.md), sourced from the AWS Price List API.

**Live resources:** three custom models and three on-demand deployments are currently running.
Deployments are **$0/hr idle**; the models accrue **$5.85/month** in storage until deleted. Run
`make teardown` when finished.

---

## Agent orchestration

The agentic layer orchestrates the ML workflow and nothing else. Its safety property is
visible in the edges below: **each agent can reach only its own tools**, and only one edge in the
whole graph leads to a billable action.

```mermaid
flowchart LR
    OP(["Human operator"])
    OP -- "types the literal APPROVE" --> TOKEN{{"approval_token"}}

    subgraph GRAPH["LangGraph orchestrator · one trace per run"]
        direction TB
        A1["dataset_prep"] --> A2["finetune_supervisor"] --> A3["evaluation"] --> A4["inference"]
    end

    TOKEN -. "GraphState.approval_token<br/>no agent can set this" .-> A2

    subgraph DS["server_dataset · read-only"]
        T1["validate_dataset"]
        T2["split_dataset"]
        T3["estimate_training_cost"]
    end
    subgraph BR["server_bedrock"]
        T4["start_finetune_job<br/>BILLABLE · gated"]
        T5["get_job_status"]
        T6["read_training_metrics"]
        T7["invoke_base_model"]
        T8["invoke_tuned_model"]
    end
    subgraph EV["server_eval · read-only"]
        T9["score_output"]
    end

    A1 --> T1 & T2 & T3
    A2 --> T4 & T5 & T6
    A3 --> T9 & T6
    A4 --> T7 & T8

    T4 == "only if dry_run=false<br/>AND token is valid" ==> AWS[("Amazon Bedrock<br/>CreateModelCustomizationJob")]

    classDef billable fill:#7f1d1d,stroke:#ef4444,color:#fff
    classDef guard fill:#78350f,stroke:#f59e0b,color:#fff
    classDef human fill:#1e3a8a,stroke:#60a5fa,color:#fff
    class T4 billable
    class TOKEN guard
    class OP human
```

Every edge above is an allowlist entry. There are no other edges: `call_tool` runs
`assert_tool_allowed(agent, tool)` before dispatch, so an agent reaching for a tool it does not own
raises `ToolNotAllowedError` rather than executing. Note that `evaluation` has no edge to any
`invoke_*` tool — scoring and generating are separated so a scorer cannot consume inference budget.


### Who may call what

The allowlist is data, enforced at call time in `call_tool` — there is no second path to a tool.

| Agent | Allowed tools | Can spend money? |
|---|---|---|
| `dataset_prep` | `validate_dataset`, `split_dataset`, `estimate_training_cost` | no |
| `finetune_supervisor` | `start_finetune_job`, `get_job_status`, `read_training_metrics` | **only with a typed token** |
| `evaluation` | `score_output`, `read_training_metrics` | no |
| `inference` | `invoke_base_model`, `invoke_tuned_model` | tokens only |

`evaluation` deliberately cannot invoke a model: scoring and generating are separated so a scorer
cannot consume inference budget.

### The approval gate

Two independent conditions must both hold. Failing either returns a *plan*, not a job.

```mermaid
sequenceDiagram
    participant H as Human
    participant G as graph.py
    participant S as finetune_supervisor
    participant T as start_finetune_job
    participant B as Amazon Bedrock

    H->>G: --execute
    G->>H: "Type APPROVE to permit a billable job"
    H->>G: APPROVE
    G->>S: GraphState(approval_token="APPROVE", dry_run=False)
    S->>T: StartFinetuneInput(...)

    alt dry_run is true
        T-->>S: plan only, job_arn=None
    else token missing or wrong
        T-->>S: ApprovalRequiredError
    else both conditions hold
        T->>B: CreateModelCustomizationJob
        B-->>T: jobArn
    end
```

### What the agents cannot do

Enforcement is **by omission first**: there is no tool to delete a model, create a deployment, modify
IAM, edit S3 lifecycle, or change the budget. Those capabilities are absent from the agents'
vocabulary entirely, so no prompt can reach them. `tests/unit/test_agent_allowlist.py` asserts every
exposed tool name against a forbidden-substring list, so adding one fails the build.

```mermaid
flowchart LR
    AG["any agent"] -->|"available"| OK["read datasets<br/>estimate cost<br/>read job status<br/>read training metrics<br/>invoke models<br/>score output"]
    AG -.->|"no such tool exists"| NO["delete model<br/>delete deployment<br/>create deployment<br/>modify IAM<br/>edit S3 lifecycle<br/>change budget<br/>provisioned throughput"]

    classDef blocked fill:#450a0a,stroke:#ef4444,color:#fca5a5
    class NO blocked
```

Teardown and infrastructure remain deterministic scripts run by humans — `scripts/teardown.py` and
Terraform.

---

## Project invariants

These are enforced, not aspirational.

| Invariant | Enforcement |
|---|---|
| No billable action without a typed `APPROVE` | `scripts/print_cost_estimate.py` blocks on the literal token; the word "yes" does not unblock it |
| Provisioned Throughput is banned | `tests/unit/test_no_provisioned_throughput.py` fails the build if the string appears under `src/`, `infra/`, or `scripts/` |
| Pricing is never hardcoded | Every estimate re-queries the AWS Price List API at run time; unknown models raise rather than guess |
| No LLM or agent executes an AWS mutation | Enforced twice: no destructive tool exists in any MCP server, and `mcp/allowlist.py` gates every call. `start_finetune_job` is the sole billable action and refuses without a human-typed token |
| CI never applies | `.github/workflows/terraform.yml` runs `fmt`, `validate`, and `plan` only. There is no apply job, and no long-lived AWS keys — plan uses OIDC and is skipped if no role is configured |
| Teardown is verifiable | `tests/post_teardown/test_zero_resources.py` is a release blocker |
| Secrets live in `.env` only | `.env.example` carries keys with no values; nothing is committed |

---

## Cost — estimated vs actual

| Stage | Estimated | **Actual** |
|---|---:|---:|
| Training — pharma (53,318 tok × 2 epochs @ $0.0033/1K) | $0.1759 | **$0.1759** |
| Training — banking | $0.1711 | **$0.1711** |
| Training — it_helpdesk | $0.1476 | **$0.1476** |
| Deployment creation × 3 | $0.00 | **$0.00** |
| Inference — all three evaluations (~130 calls) | ~$0.008 | **$0.0135** |
| Idle, deployed and not invoked | $0.00/hr | **$0.00/hr** |
| **One-time total** | **$0.504** | **$0.508** |
| Custom model storage, 3 models | | **$5.85 / month until deleted** |
| Budget ceiling | | $25 / month |

**Storage is the number that matters, not training.** Three models accrue $5.85/month — 23% of the
budget — for models sitting idle. Total training across all three scenarios was $0.4946, less than
one month of storing them.

Every training run matched its estimate **exactly** — Bedrock's training charge is a deterministic
function of tokens × epochs × unit price, with no wall-clock component.

**Nine failed fine-tuning jobs cost $0.00 in total**, including one that sat in the queue for 74
hours. Bedrock bills tokens *processed*; those jobs never processed any. Under a time-based billing
model the same failures would have been ruinous.

Full record, including three corrections to the original estimate:
[`docs/COST-ACTUALS.md`](docs/COST-ACTUALS.md).

### The cost decision that dominated every other

| | Provisioned Throughput | **Custom Model on-Demand** |
|---|---:|---:|
| Billing basis | wall-clock hours held | tokens processed |
| Idle cost | **still billing** | **$0.00** |
| 3 models, 48h weekend | **$8,712** | **$0.00** |
| 3 models, 30 days | **$130,680** | **$0.00** |

Only five Bedrock base models support CMoD — Nova Micro, Lite, 2 Lite, Pro (`us-east-1`) and Meta
Llama 3.3 70B Instruct (`us-west-2`). Every other fine-tunable model is Provisioned-Throughput-only
and would have exceeded a $25/month budget in under 90 minutes. **This constraint selected the model,
not the other way around.**

### The constraint nobody budgets for

| Quota — Llama 3.3 70B custom model deployment, us-west-2 | Value | Adjustable |
|---|---:|---|
| **Requests per minute** | **4** | **No** |
| Tokens per minute | 300,000 | No |
| Tokens per day | 16,200,000 | No |

Evaluation throttled at ~20 req/min and had to be paced to one call every 16 seconds. The token
ceilings are effectively unlimited for this workload; **the request ceiling cannot be raised.**

> **Cheap does not mean fast.** CMoD's $0-idle billing is paid for in throughput.

---

## Prerequisites

- **Python 3.12**
- **Terraform** ≥ 1.5
- **AWS CLI v2**, credentials with permission to create S3, IAM, DynamoDB, CloudWatch, Budgets, and
  Bedrock customization resources
- **Node 20+** (front end only)
- **Bedrock model access** granted for `meta.llama3-3-70b-instruct-v1:0` in `us-west-2`

Bedrock model customization exists in **exactly two Regions**: `us-east-1` and `us-west-2`. There is
no Canada, Europe, or Asia option. `infra/terraform/variables.tf` rejects anything else.

---

## Setup

```bash
# 1. Virtual environment on 3.12
python3.12 -m venv .venv
source .venv/bin/activate
python --version          # must report 3.12.x

# 2. Dependencies
make setup

# 3. Configuration
cp .env.example .env      # then fill it in — see the table below

# 4. Terraform remote state (once per account)
bash scripts/bootstrap_state.sh
```

### Environment variables

| Variable | Required | Example | Notes |
|---|---|---|---|
| `AWS_REGION` | ✅ | `us-west-2` | Must be `us-east-1` or `us-west-2` |
| `AWS_PROFILE` | | `default` | Falls back to the standard credential chain |
| `PROJECT_SUFFIX` | ✅ | `marco-demo01` | Namespaces every resource name |
| `BUDGET_LIMIT_USD` | ✅ | `25` | Creates an AWS Budget before anything billable |
| `BUDGET_ALERT_EMAIL` | ✅ | `you@example.com` | Alerts at 50 / 80 / 100 % and forecast-100 % |
| `LANGFUSE_HOST` | | `http://localhost:3000` | Optional tracing |
| `LANGFUSE_PUBLIC_KEY` | | | Optional |
| `LANGFUSE_SECRET_KEY` | | | Optional — **never commit** |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | | | Optional OTLP target |
| `API_PORT` | | `8000` | |
| `FRONTEND_PORT` | | `5173` | |

`.env` is git-ignored. `.env.example` carries keys only.

---

## Quickstart

```bash
# Provision — prints a cost estimate, then applies
make provision

# Run one scenario end to end (blocks on a typed APPROVE before billing)
make run SCENARIO=pharma

# Verify against live AWS resources
make test-post-run

# Front end
make frontend          # http://localhost:5173   (demo / demo123)
```

`make run` performs: split → upload → **cost estimate** → **typed approval** → fine-tune →
poll to `Completed` → deploy → poll to `Active` → base-vs-tuned inference → schema validation →
`artifacts/{scenario}/results.json`.

> The `demo` / `demo123` login is a **deliberate insecure stub**, labelled as such in
> `api/insecure_demo_auth.py`. It is not wired to any identity service and must not be.

### Scenarios

| Scenario | Status | Output contract |
|---|---|---|
| `pharma` | **active** | Strict JSON, 8-term controlled vocabulary |
| `banking` | **active** | Prose + conditional compliance disclaimer |
| `it_helpdesk` | **active** | Numbered steps + fixed L2 escalation line |
| `gardening` | config only | Prose, analogy-driven |
| `support_triage` | config only | Strict JSON |
| `patient_triage` | config only | Strict JSON |
| `ecommerce` | config only | Short copy, word limit |

Disabled scenarios are valid configs that run when a flag flips — **no code change required.**

---

## Teardown

**Order is mandatory. Reversing it hangs the destroy.**

```bash
make teardown
```

which runs, in this order:

```
1. delete custom model deployments      ← must precede the models
2. delete custom models
3. empty the S3 data bucket             ← all versions and delete markers
4. terraform destroy
```

Then prove it:

```bash
.venv/bin/python scripts/verify_empty.py
make test-post-teardown
```

`verify_empty.py` checks zero deployments, zero custom models, bucket absent, IAM role absent, and
`terraform state list` empty. A non-empty footprint exits non-zero and blocks release.

> Custom models bill **$1.95/model/month** until deleted. The deployment itself is $0 idle, so there
> is no hourly urgency — but storage accrues indefinitely.

---

## Testing

```bash
make test-unit             # no AWS credentials required
make test-pre              # pre-provision: region, quotas, model access
make test-post             # post-provision: bucket private, budget exists, SKUs approved
make test-post-run         # against live resources after a run
make test-post-teardown    # release gate: zero surviving resources
make lint && make typecheck
```

---

## Engineering decisions

| Challenge | Resolution |
|---|---|
| Customization model IDs (`:128k`/`:256k`) are `PROVISIONED`-only and rejected by `Converse` | Explicit `base_inference_model_id` config field — the transform is not a suffix strip (Nova also needs a `us.` profile prefix), and guessing fails at runtime |
| Cost estimator hardcoded one model's usage types | Usage types derive from `base_model_id`; unknown models raise `UnknownModelPricingError`. Nova Micro vs Nova 2 Lite was a **3.8× error** |
| `session.py` hardcoded `us-east-1`, ignoring `AWS_REGION` | Region resolves from `Settings`. Teardown used this session — it would have reported a clean destroy while an out-of-Region model kept billing |
| `Converse` omitted `maxTokens` | Bedrock defaults to the model maximum and reserves that quota per call — a documented cause of throttling at low volume |
| Teardown and the zero-resource gate built the bucket name inline | Both probed a Region-less name that never existed; `head_bucket` 404'd and the release gate **passed falsely** |
| Post-run tests rebuilt job names instead of using recorded ARNs | Bedrock reserves job names permanently; the canonical name resolved to a `Stopped` first attempt |
| "Last 10% of records" split leaked | These datasets group one question under several prefixes sharing a gold answer. Banking's held-out set was **3 questions, all in training, 23/23 answers verbatim**, with zero instances of either contract rule. Replaced with group-aware / stratified splitting |
| S3 bucket names are global but buckets are regional | Region is part of the name; deleting and recreating one name across Regions blocks on an unbounded release delay |
| Price List API returns SKUs for retired models | `list_foundation_models` is authoritative for availability; the Price List API is not |

---

## Incident: 10 fine-tuning attempts, 1 model

Seven consecutive jobs in `us-east-1` failed across two Nova base models — three stalled at
`trainingDetails: NotStarted` (one for 74 hours), four failed validation in under three minutes with
`"Encountered an internal error."` The eighth attempt, **same dataset byte-for-byte**, succeeded on
the first try in `us-west-2` on Llama 3.3 70B.

**The root cause was never identified.** It was routed around, not fixed. Every hypothesis was
eliminated — AWS's own validator certified the data 189/189, CloudTrail showed zero IAM or S3 drift,
quotas were nowhere near limits, and the identical configuration had succeeded on this account in
April. Changing Region, model family, and provider at once means the successful variable cannot be
isolated.

Full forensics, including S3 output-manifest evidence:
[`docs/INCIDENT-LOG.md`](docs/INCIDENT-LOG.md).

---

## Documentation

| Document | Contents |
|---|---|
| [`PLAN.md`](PLAN.md) | Architecture decisions and deliberate deviations from the source lab |
| [`TASKS.md`](TASKS.md) | Sequenced build contract |
| [`COSTS.md`](COSTS.md) | Pre-build cost estimate |
| [`docs/COST-ACTUALS.md`](docs/COST-ACTUALS.md) | Estimated vs actual, and where the estimate was wrong |
| [`docs/RESULTS.md`](docs/RESULTS.md) | Fine-tuning results and error analysis |
| [`docs/INCIDENT-LOG.md`](docs/INCIDENT-LOG.md) | The 10-attempt failure investigation |

---

## Author

**Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)
