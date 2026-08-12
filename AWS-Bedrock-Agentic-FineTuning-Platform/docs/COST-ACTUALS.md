# Cost record — estimated vs actual

Companion to [`COSTS.md`](../COSTS.md) (the pre-build estimate) and
[`INCIDENT-LOG.md`](INCIDENT-LOG.md). `COSTS.md` records what was *approved before building*;
this file records **what was actually estimated, and what was actually spent**, including where
the original estimate turned out to be wrong.

All prices queried live from the **AWS Price List API**, not from memory or documentation.

---

## 1. Headline

| | |
|---|---:|
| Fine-tuning jobs attempted | **10** |
| Jobs that produced a model | **1** |
| **Total training spend** | **$0.1759** |
| Demo inference, **actual** (21-record held-out eval + probes) | **$0.0055** |
| Custom model storage | $1.95 / month, until deleted |
| **First-month total** | **≈ $2.13** |
| **After teardown** | **$0.00** |
| Budget ceiling | $25 / month |
| **Budget consumed** | **≈ 8.5%** |

**Nine of the ten jobs cost exactly $0.00.** Bedrock bills training by tokens *processed*, so jobs
that never started training — including one that sat for 74 hours — were never billed. Had
training been billed by wall-clock time, those nine failures would have been ruinous.

---

## 2. Estimate vs actual

### 2.1 Training

| | Base model | Region | Est. tokens | Price/1K | Estimated | Actual |
|---|---|---|---:|---:|---:|---:|
| Original plan (`COSTS.md` §3) | Nova 2 Lite | us-east-1 | 53,320 | $0.00378 | $0.2015 | **$0.00** — never trained |
| Diagnostic attempt | Nova Micro | us-east-1 | 66,651 | $0.00100 | $0.0667 | **$0.00** — never trained |
| **Delivered** | **Llama 3.3 70B** | **us-west-2** | **53,318** | **$0.0033** | **$0.1759** | **$0.1759** |

The delivered run matched its estimate exactly, because Bedrock's training charge is a
deterministic function of tokens × epochs × unit price — there is no time component to vary.

### 2.2 Post-training stages

| Stage | Estimated | Actual | Notes |
|---|---:|---:|---|
| Deploy (`CreateCustomModelDeployment`) | $0.00 | **$0.00** | No creation charge; took 8m to reach `Active` |
| Inference, base vs tuned | $0.0027 | **$0.0055** | Scope grew from 1 sample prompt to the full 21-record held-out set (42 calls) |
| Schema validation (`PharmaTriageOutput`) | $0.00 | **$0.00** | Pure Python, runs locally |
| `results.json` + `make test-post-run` | $0.00 | **$0.00** | File writes + a few S3 list calls |
| Idle, deployed but not invoked | $0.00/hr | **$0.00/hr** | The entire point of CMoD |

The inference overrun is 2× the estimate in ratio and **$0.003 in absolute terms** — the estimate assumed
the single configured `sample_prompt`, while the run evaluated all 21 held-out records against both models
to produce a real accuracy comparison.

### 2.3 Inference scaling

Llama 3.3 70B in us-west-2: **$0.00072/1K tokens, input *and* output**, for both the base model
and the custom deployment.

| Demo comparisons (base + tuned) | Cost |
|---:|---:|
| 1 | $0.0003 |
| 10 | $0.0027 |
| 200 | $0.0547 |
| 1,000 | $0.2736 |

A thousand side-by-side demos still costs less than the single training run.

---

## 3. The cost decision that dominated every other

Bedrock offers two ways to serve a fine-tuned model. The gap is not marginal.

| | Provisioned Throughput | **Custom Model on-Demand (CMoD)** |
|---|---:|---:|
| Billing basis | wall-clock hours held | tokens processed |
| Rate | $60.50/hr (Nova) | $0.00072/1K (Llama 3.3 70B) |
| Idle cost | **still billing** | **$0.00** |
| 3 models, one 8h session | $1,452 | ~$0.40 |
| 3 models, 48h weekend | **$8,712** | **$0.00** |
| 3 models, 30 days | **$130,680** | **$0.00** |

**This project uses CMoD exclusively and has never provisioned throughput.** Verified: zero
provisioned throughputs in both us-east-1 and us-west-2.

It is enforced, not merely intended — `tests/unit/test_no_provisioned_throughput.py` fails the
build if `ProvisionedThroughput`, `aws_bedrock_provisioned_model_throughput`, or
`create_provisioned_model_throughput` appears anywhere under `src/`, `infra/`, or `scripts/`.

**This constraint drove model selection.** Only five base models support CMoD: Nova Micro, Lite,
2 Lite, Pro (us-east-1), and Meta Llama 3.3 70B Instruct (us-west-2). Every other fine-tunable
model is Provisioned-Throughput-only and would have exceeded the $25/month budget in under 90
minutes. Llama 3.3 70B was the only viable option outside us-east-1 — and notably has **no PT SKU
at all**, making the expensive path structurally impossible.

---

## 4. Where the original estimate was wrong

Recorded because the corrections matter more than the numbers.

### 4.1 `COSTS.md` dataset measurements were stale

§3 records pharma at 106,639 chars / 26,660 tokens. The actual file is **148,219 chars**, splitting
into 133,302 (train) + 14,917 (validation). Real training tokens were ~25% higher than documented.

### 4.2 The cost estimator was model-blind

`cost_estimator.py` hardcoded Nova 2 Lite Price List usage types, so changing a scenario's
`base_model_id` silently priced the *wrong model* — Nova Micro training is $0.001/1K vs Nova 2
Lite's $0.00378/1K, a **3.8× overstatement**. Fixed: usage types now derive from `base_model_id`
via an explicit map, and an unknown model raises `UnknownModelPricingError` rather than guessing.

### 4.3 The Price List API is not authoritative for availability

`aws pricing get-products` still returns live SKUs for **Titan Text Lite and Express**, which are
**retired** and absent from `list_foundation_models` in both regions. Pricing SKUs outlive the
models they price.

> **`list_foundation_models` is authoritative for availability; the Price List API is not.**

Costing a model purely from pricing data can produce a plan around a model that no longer exists.

### 4.4 The binding constraint was throughput, not cost

Every estimate in `COSTS.md` models **tokens and dollars**. Neither is what actually limits this
deployment. Live quotas for Llama 3.3 70B custom model deployments in us-west-2:

| Quota | Value | Adjustable |
|---|---:|---|
| On-demand custom model deployment **requests per minute** | **4** | **No** |
| On-demand custom model deployment tokens per minute | 300,000 | No |
| On-demand custom model deployment tokens per day | 16,200,000 | No |
| Total custom model deployments | 10 | Yes |
| In-progress custom model deployments | 2 | Yes |

The held-out eval threw `ThrottlingException` at ~20 requests/minute and had to be paced to one call
every 16 seconds. The token ceilings are enormous relative to this workload; **the 4 req/min request
ceiling is the real limit, and it cannot be raised.**

Consequences for the platform:

- The 21-record eval takes ~7 minutes wall-clock, bounded entirely by rate limiting, not by cost.
- A UI that fires base and tuned concurrently per user action consumes 2 of the 4 available
  requests. Two users clicking at once will throttle.
- Any batch scoring path needs client-side pacing; boto3's default retry does not absorb a steady
  overrun, only a burst.

> **Cheap does not mean fast.** CMoD's $0-idle billing is paid for in throughput, and the ceiling is
> not negotiable via a quota increase request.

---

## 5. What "$0.00 for nine failed jobs" depends on

Worth stating explicitly, because it is a property of the billing model rather than luck:

- Bedrock charges for **tokens processed during training**.
- Nine jobs never reached `trainingDetails: InProgress`, so zero tokens were processed.
- One job (`-ft-3`) sat in that state for **74 hours** and cost nothing.
- S3 storage for the datasets (~150 KB) is fractions of a cent.
- The failed jobs' S3 output artifacts fell under the bucket's 30-day lifecycle expiry.

Under a time-based billing model, those same nine failures would have been extremely expensive.

---

## 6. Guardrails that kept this inside budget

| Control | Implementation |
|---|---|
| Typed approval before any billable action | `scripts/print_cost_estimate.py` blocks on the literal token `APPROVE`; no job or `terraform apply` proceeds without it |
| Live pricing, never hardcoded | Every estimate re-queries the Price List API at run time |
| Fail loudly on unknown pricing | `PriceUnavailableError` / `UnknownModelPricingError` — refusing to quote beats quoting wrong |
| Provisioned Throughput banned | CI test scans `src/`, `infra/`, `scripts/` for forbidden strings |
| Budget ceiling | `aws_budgets_budget` at $25/mo, alerts at 50% / 80% / 100% / forecast-100%, created **before** any billable resource |
| Ordered teardown | `scripts/teardown.py` — deployments → custom models → S3 → `terraform destroy` |
| Teardown verification | `tests/post_teardown/test_zero_resources.py` — P0 release blocker |

---

## 7. Reproducing these figures

```bash
# live cost estimate for all enabled scenarios (no side effects)
.venv/bin/python scripts/print_cost_estimate.py --dry-run

# confirm nothing is billing hourly
.venv/bin/python - <<'PY'
import boto3
for r in ['us-east-1', 'us-west-2']:
    c = boto3.client('bedrock', region_name=r)
    print(r, 'provisioned throughputs:',
          len(c.list_provisioned_model_throughputs().get('provisionedModelSummaries', [])))
PY
```

---

## 8. Open items

- [ ] Confirm actual billed training cost against Cost Explorer once it settles (24–48h lag)
- [x] Record actual inference spend after the demo session — **$0.0055**
- [ ] Delete the deployment and custom model when the demo is done; storage accrues at $1.95/month
      until then (the deployment itself is $0 idle, so there is no hourly urgency)
- [ ] Update `COSTS.md` §3 dataset measurements, which are stale for all seven scenarios
- [ ] Re-cost banking and it_helpdesk on Llama 3.3 70B before launching either
