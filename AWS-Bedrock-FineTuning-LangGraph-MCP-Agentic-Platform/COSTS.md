# COSTS.md — AWS-Bedrock-FineTuning-LangGraph-MCP-Agentic-Platform

**Permanent record of what was costed and approved.**
Region: `us-east-1` · Account: `759316130780` · Currency: USD, list price.

**Approval status: ⏳ NOT YET APPROVED.** No resource in this document may be provisioned until this file is
approved and the budget ceiling in §5 is confirmed.

---

## 1. How these prices were obtained

Not from memory, and not from a blog post. Queried live on **2026-08-02** from the **AWS Price List API**:

```bash
aws pricing get-products --region us-east-1 --service-code AmazonBedrock \
  --filters 'Type=TERM_MATCH,Field=regionCode,Value=us-east-1'
```

Raw results for the base model the guide specifies (**Nova 2 Lite**, `amazon.nova-2-lite-v1:0:256k`,
confirmed available and `AUTHORIZED` on this account):

| AWS usage type | Price | Unit |
|---|---:|---|
| `USE1-Nova2.0Lite-Customization-Training` | 0.00378 | per 1K tokens |
| `USE1-Nova2.0Lite-Customization-Storage` | 1.95 | per Model / month |
| `USE1-Nova2.0Lite-input-tokens-custom-model` | 0.00030 | per 1K tokens |
| `USE1-Nova2.0Lite-output-tokens-custom-model` | 0.00250 | per 1K tokens |
| `USE1-Nova2.0Lite-input-tokens` (base, on-demand) | 0.00033 | per 1K tokens |
| `USE1-Nova2.0Lite-output-tokens` (base, on-demand) | 0.00275 | per 1K tokens |
| `USE1-Nova2.0Lite-ProvisionedThroughput-NoCommit-ModelUnits` | 60.50 | per hour |
| `USE1-Nova2.0Lite-ProvisionedThroughput-1month-ModelUnits` | 55.00 | per hour |

---

## 2. 🔴 The pricing trap, and why we are not in it

The skill's warning is precisely on point here: **fine-tuned Bedrock models have historically required
Provisioned Throughput, billed hourly with no free tier and no pay-per-use path.**

**Verified: that is not the case for Nova 2 Lite in `us-east-1`.** Amazon Bedrock **Custom Model on-Demand
(CMoD)** supports Nova 2 Lite — token-billed, with **no hourly charge and nothing billed while idle**. This is
what the guide uses throughout (§8 "Create a Custom Model on Demand with Inference", and step "Deploy for
on-demand inference" in every scenario). AWS docs list Nova 2 Lite explicitly among CMoD-supported base
models; the APIs are `CreateCustomModelDeployment` / `DeleteCustomModelDeployment`.

**The disaster we avoided, in numbers.** Had we used Provisioned Throughput for three demo models:

| | Provisioned Throughput (⛔ NOT USED) | Custom Model on-Demand (✅ USED) |
|---|---:|---:|
| Per model, per hour | $60.50 | $0.00 idle |
| 3 models, per hour | **$181.50** | **$0.00** idle |
| 3 models, one 8h session | **$1,452.00** | ~$0.40 (tokens only) |
| 3 models, 48h weekend | **$8,712.00** | **$0.00** |
| 3 models, 30 days | **$130,680.00** | **$0.00** |

**Project invariant, enforced in CI:** the strings `ProvisionedThroughput`,
`aws_bedrock_provisioned_model_throughput`, and `create_provisioned_model_throughput` are forbidden anywhere
in `src/`, `infra/`, or `scripts/`. `tests/unit/test_no_provisioned_throughput.py` fails the build on a hit.

**What *does* bill while idle:** custom model **storage**, $1.95 per model per month. Three demos = **$5.85 per
month, indefinitely, until the custom models are deleted.** Small, but not zero — and it is exactly why
teardown must delete the *custom models*, not merely the deployments.

---

## 3. Measured inputs

Dataset sizes measured directly from the repo files (4 chars/token estimate):

| Active demo | Records | Chars | Est. tokens | Training $ @ 1 epoch | @ 2 epochs (proposed) | @ 5 epochs |
|---|---:|---:|---:|---:|---:|---:|
| Banking Virtual Assistant | 230 | 103,694 | 25,924 | $0.098 | $0.196 | $0.490 |
| IT / DevOps L1 Helpdesk | 210 | 88,726 | 22,182 | $0.084 | $0.168 | $0.419 |
| Pharmacovigilance AE Triage | 210 | 106,639 | 26,660 | $0.101 | $0.202 | $0.504 |
| **Total (3 active demos)** | **650** | **299,059** | **74,766** | **$0.283** | **$0.565** | **$1.413** |

Costed conservatively on full-file tokens; the 10% validation split means real training tokens are ~10% lower.

---

## 4. Cost table

Assumes the **3 active demos** — 3 training jobs, 3 custom models, 3 CMoD deployments.
"One test session" = ~8 hours, including one full training run and ~200 demo inferences against **both** base
and tuned models.

| Resource | SKU / tier | Reason for this choice | Cost/hr running | One test session (~8h) | Left running 48h | Left running 30d | Cheaper alternative |
|---|---|---|---:|---:|---:|---:|---|
| Bedrock fine-tuning (training) × 3 | Nova 2 Lite SFT, 2 epochs | Base model mandated by the guide; smallest fine-tunable Nova | n/a — one-time | **$0.57** | $0.57 | $0.57 | Fewer epochs (1 → $0.28); train 1 demo instead of 3 (→ $0.20) |
| Bedrock custom model **storage** × 3 | $1.95 / model / month | Unavoidable while a custom model exists | $0.0080 | $0.06 | $0.39 | **$5.85** | Delete models after the demo → $0 |
| Bedrock CMoD deployment × 3 | Custom Model on-Demand | **No hourly charge. $0 when idle.** | **$0.00** | $0.00 | **$0.00** | **$0.00** | — already the cheapest tier |
| Tuned-model inference | $0.00030 in / $0.00250 out per 1K tok | Demo traffic only | usage-based | $0.20 | $0.20 | $0.20 | Shorter prompts / fewer runs |
| Base-model inference (comparison pane) | $0.00033 in / $0.00275 out per 1K tok | Required by the base-vs-tuned UX | usage-based | $0.22 | $0.22 | $0.22 | Cache base responses per prompt |
| S3 — datasets + job artifacts | S3 Standard | ~1.1 MB data + small metrics files | ~$0.0000 | <$0.01 | <$0.01 | **$0.02** | Lifecycle expiry on `output/` (already configured, 30d) |
| S3 — Terraform remote state | S3 Standard + versioning | Skill requirement | ~$0.0000 | <$0.01 | <$0.01 | **$0.01** | — |
| DynamoDB — state lock | **PAY_PER_REQUEST** | On-demand; a handful of writes per apply | ~$0.0000 | <$0.01 | <$0.01 | **$0.01** | — already cheapest |
| CloudWatch Logs | 7-day retention | Expected <1 GB; 5 GB ingest is free tier | ~$0.0000 | $0.00 | $0.00 | **$0.50** (worst case) | Shorter retention |
| AWS Budgets + alerts | 2 budgets | First 2 budgets are free | $0.00 | $0.00 | $0.00 | **$0.00** | — |
| Langfuse (self-hosted, docker-compose) | local container | $0, no data leaves the machine | $0.00 | $0.00 | $0.00 | **$0.00** | Langfuse Cloud free tier |
| **TOTAL** | | | **~$0.008/hr idle** | **≈ $1.06** | **≈ $1.39** | **≈ $6.81** | |

### Bolded totals

- **One test session (~8h, including one full training run): ≈ $1.06**
- **Left running 48 hours (accidental weekend, idle after a session): ≈ $1.39**
- **Left running 30 days (idle after a session): ≈ $6.81**
- **Steady-state idle burn, no activity at all: $5.85/month** — entirely custom model storage.

### 🚩 Red flags

- **No single resource exceeds $50/month.** The largest line is custom model storage at $5.85/month.
- **The one genuinely dangerous line item is the one we are not using.** Provisioned Throughput would be
  **$130,680/month** for three models — a 19,000× difference. See §2. Guarded in CI.
- **The guide's own cost claim is wrong.** §3 states the walkthrough carries no charge and §5 estimates it
  at $0.01. Training alone is ~$0.57 for three demos, and storage accrues
  at $5.85/month afterwards. Free-tier credits may absorb it, but credits are finite and are not a price.
- **Repeated training re-bills.** Each re-run of `make run` that launches a fresh fine-tuning job costs another
  ~$0.57. The pipeline detects an existing completed model for a scenario and refuses to retrain without an
  explicit `--force-retrain` flag plus typed approval.
- **Cost of forgetting teardown is low but not nil** — $5.85/month forever. The budget alert is the backstop.

### Sensitivity: all 7 scenarios instead of 3

If every scenario were later enabled: training (2 epochs) ≈ **$1.28** one-time, storage **7 × $1.95 = $13.65/
month**. Still under $50/month, but it exceeds the concurrent-deployment quota (2) and would need serialized
deploys or a quota increase.

---

## 5. Budget ceiling and alerting — **decided: $25/month**

**$25/month AWS Budget**, chosen by the user on 2026-08-02. Created by Terraform **before any billable
resource exists** (`aws_budgets_budget`, with `depends_on` wired so it is not an afterthought).

| Threshold | Type | Action |
|---|---|---|
| 50% ($12.50) | ACTUAL | Email notification |
| 80% ($20.00) | ACTUAL | Email notification |
| 100% ($25.00) | ACTUAL | Email notification |
| 100% ($25.00) | FORECASTED | Email notification |

$25 gives ~4.3× headroom over the $5.85/month steady-state idle burn. Normal operation will not trip the 50%
alert. What would reach it: repeated retraining (~$0.19 per demo per run) plus heavy demo inference, or
leaving three custom models undeleted for four-plus months. Both are precisely the conditions worth alerting
on, so this is a tripwire rather than a nuisance threshold.

**❓ Still needed before Phase 4:** the **email address** for budget notifications. `djmau1974@gmail.com` is on
file for this session — confirm or replace it. I will not hardcode it unasked. Terraform cannot create the
budget without it, and the budget must exist before any billable resource.

### Other decisions recorded

| Decision | Value | Cost effect |
|---|---|---|
| Epochs | **2** | Training = **$0.57** across all 3 demos (as costed in §3 and §4) |
| Rollout | **All three demos in this build** | Full $0.57 training cost incurred in one pass; ~12h wall-clock. Deployments serialized around the *in-progress deployments = 2* quota |
| Observability | **Langfuse Cloud** (free tier) | **$0** — same as self-hosting. Requires user-supplied API keys before Phase 7 |

---

## 6. Assumptions

Every one of these is cost-relevant. Correct any that are wrong and I will re-cost.

1. **Tokens estimated at 4 characters/token.** Bedrock's real tokenizer will differ by roughly ±15%. At these
   magnitudes that is cents.
2. **Training tokens billed = dataset tokens × epochs**, at 2 epochs.
3. **`Customization-Storage` is prorated** for partial months. If AWS charges a whole month on creation, the
   30-day figure ($5.85) applies immediately rather than accruing — worst case still under $6.
4. **Region `us-east-1` for everything.** Mandatory: it is the only region supporting Nova CMoD.
5. **Demo inference volume:** ~200 invocations per session, ~400 input / ~300 output tokens each, executed
   against **both** base and tuned models.
6. **Free-tier credits are ignored.** This account may have credits that absorb these charges; the table
   reports list price, because credits are a balance, not a pricing tier.
7. **Prices are `us-east-1` list price as of 2026-08-02** and may change. `scripts/print_cost_estimate.py`
   re-queries the Price List API at run time so the number printed before provisioning is always live, never
   this file's snapshot.
8. **One training run per demo.** Retraining re-bills at ~$0.19 per demo.

---

## 7. Teardown safety net

Per the skill: every resource that bills while idle must have a Terraform-managed budget alert and a
conspicuous teardown reminder.

| Control | Implementation |
|---|---|
| Budget alert | `aws_budgets_budget` + 4 notifications — a **Terraform resource**, not a manual console step |
| Terminal reminder | `make provision` and `make run` both end with a banner: *"Resources are live and billing. Run `make teardown` when done."* |
| README | Cost table + teardown instructions, prominently placed |
| Ordered teardown | `scripts/teardown.py` — deployments → custom models → S3 objects → `terraform destroy` |
| Verification | `tests/post_teardown/test_zero_resources.py` — **P0 release blocker**, asserts zero deployments, zero custom models, no bucket, empty Terraform state |
| Cost gate | No fine-tune job or `terraform apply` runs without printing a live cost estimate and reading a typed approval |

---

## 8. Approval

Requires explicit sign-off on **both** this cost estimate and [`PLAN.md`](PLAN.md).

- [x] Cost table reviewed and accepted
- [x] Budget ceiling confirmed — **$25/month** (§5)
- [x] Alert email confirmed — §5 (`djmau1974@gmail.com`)
- [x] Epoch count confirmed — **2 epochs**
- [x] Rollout confirmed — **all three demos in this build**
- [x] Observability confirmed — **Langfuse Cloud** (keys needed before Phase 7)

**Until every box is checked, Phase 3 does not begin.**
