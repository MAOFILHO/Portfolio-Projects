# Incident log — Bedrock model customization failures

**Status:** **Resolved by region change — root cause never identified** · **Account:** `759316130780`
**Window:** 2026-08-03 → 2026-08-10 · **Scenario:** `pharma` (Pharmacovigilance AE Triage)

Seven consecutive `CreateModelCustomizationJob` attempts in **`us-east-1`**, across **two different
base models**, failed to produce a custom model. None ever reached `trainingDetails: InProgress`.

The eighth attempt — **identical dataset, byte-for-byte** — succeeded on the first try in
**`us-west-2`** on `meta.llama3-3-70b-instruct-v1:0:128k`, training to `Completed` in 81 minutes.

**`us-east-1` training spend: $0.00** across all seven failures. Bedrock bills tokens actually
processed during training; zero were ever processed.

> **The us-east-1 failure was never explained.** It was routed around, not fixed. Every hypothesis in
> §3 was eliminated, the AWS re:Post thread went unanswered, and Basic support does not permit a
> technical case. The successful us-west-2 run *narrows* the cause to something region- or
> model-family-scoped, but does not identify it. **Do not read §4 as a root-cause finding.**

---

## 1. Timeline

| # | Job name | Base model | Created (UTC) | Duration | `validation` | `training` | Outcome |
|---|---|---|---|---|---|---|---|
| 1 | `marco-demo01-pharma-ft` | Nova 2 Lite | 2026-08-03 14:25:29 | 1d 01:32:55 | `Completed` | `NotStarted` | Stalled → manually stopped |
| 2 | `marco-demo01-pharma-ft-2` | Nova 2 Lite | 2026-08-04 15:59:33 | 1d 01:15:50 | `Completed` | `NotStarted` | Stalled → manually stopped |
| 3 | `marco-demo01-pharma-ft-3` | Nova 2 Lite | 2026-08-05 17:15:38 | 3d 02:10:46 | `Completed` | `NotStarted` | Stalled → manually stopped |
| 4 | `marco-demo01-pharma-ft-4` | Nova 2 Lite | 2026-08-08 22:43:27 | 00:02:23 | **`Failed`** | `NotStarted` | Failed |
| 5 | `marco-demo01-pharma-ft-5` | Nova 2 Lite | 2026-08-08 23:56:22 | 00:01:08 | **`Failed`** | `NotStarted` | Failed |
| 6 | `marco-demo01-pharma-ft-6` | Nova 2 Lite | 2026-08-09 01:33:15 | 00:02:12 | **`Failed`** | `NotStarted` | Failed |
| 7 | `marco-demo01-pharma-micro-ft` | **Nova Micro** | 2026-08-09 21:21:16 | 00:01:42 | **`Failed`** | `NotStarted` | Failed |
| **8** | **`marco-demo01-pharma-llama-ft`** | **Llama 3.3 70B** *(us-west-2)* | 2026-08-09 23:58:49 | **01:21:02** | **`Completed`** | **`Completed`** | ✅ **Model created** |

> For jobs 1–3, *Duration* is time-to-manual-stop, not time-to-failure — they never failed, they
> simply never started training.
>
> Jobs 1–7 ran in `us-east-1`. Job 8 ran in `us-west-2` — the only other Region where Bedrock model
> customization exists — using the **same 189/21 record split, unchanged**.

### 1.1 The same configuration succeeded on this account in April

Two older jobs exist on the same account and region, predating this project:

| Job name | Base model | Created (UTC) | Status | `validation` | `training` |
|---|---|---|---|---|---|
| `finetune-nova-k21` | `amazon.nova-lite-v1:0:300k` | 2026-04-15 15:05 | Stopped | `Completed` | `NotStarted` |
| **`finetune-nova3-k21`** | **`amazon.nova-2-lite-v1:0:256k`** | 2026-04-15 17:33 | **`Completed`** | `Completed` | **`Completed`** |

`finetune-nova3-k21` **ran to completion on the exact same base model** (`amazon.nova-2-lite-v1:0:256k`),
in the same account and region, on 2026-04-15 — producing
`arn:aws:bedrock:us-east-1:759316130780:custom-model/amazon.nova-2-lite-v1:0:256k/x7wfvyx885l9`.

This is the strongest single data point in the log:

- **Nova 2 Lite fine-tuning is not permanently blocked for this account.** It demonstrably worked.
- **Something changed between 2026-04-15 and 2026-08-03.** Whatever it is, it is not a standing
  account restriction, a quota ceiling, or an unsupported configuration.
- It used a **different IAM role** (`k21-role-bedrock123`) whose trust policy is byte-identical to
  the current one; the only difference is broader, unconditional S3 access. That difference was
  tested and eliminated (§3, rows 3–4) — jobs 1–3 passed validation with the *current* role, so the
  role is demonstrably sufficient for the validation stage that now fails.

### Job ARNs

```
1  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-2-lite-v1:0:256k/jr2dm97inxxm
2  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-2-lite-v1:0:256k/iccv5z0tajyc
3  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-2-lite-v1:0:256k/n45xnijacww6
4  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-2-lite-v1:0:256k/lceg313i66qh
5  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-2-lite-v1:0:256k/wpde0abascim
6  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-2-lite-v1:0:256k/vsa9v6r1zahj
7  arn:aws:bedrock:us-east-1:759316130780:model-customization-job/amazon.nova-micro-v1:0:128k/q5y707uixmrq
```

---

## 2. Two distinct failure signatures

**Signature A — silent queue stall (jobs 1–3, Aug 3–5).**
Data validation completes normally in ~2–4 minutes. `trainingDetails.status` then sits at
`NotStarted` indefinitely — 25h, 25h, and 74h respectively. No `failureMessage` is ever populated.
The job remains `InProgress` forever. All three were terminated manually via
`StopModelCustomizationJob`.

**Signature B — instant validation failure (jobs 4–7, Aug 8–9).**
Data validation itself fails within 1–2.5 minutes:

```
status:                          Failed
statusDetails.validationDetails: Failed
statusDetails.trainingDetails:   NotStarted
failureMessage:                  "Encountered an internal error when processing the request."
```

**The failure mode changed between 2026-08-05 17:15 and 2026-08-08 22:43** with no corresponding
change on the client side (see §3). The same data that passed validation three times in Signature A
now fails validation in Signature B.

### 2.1 S3 output forensics

Bedrock writes job artifacts to the configured `outputDataConfig` prefix. Listing
`s3://bedrock-platform-marco-demo01-data/output/pharma/` draws a sharp line between the two
signatures:

| Jobs | Artifacts written |
|---|---|
| 1–3 (Signature A) | `input_status/**/manifest.report.csv` and `validated_data/**/validated_prompts.jsonl` for both datasets |
| 4–7 (Signature B) | **Nothing. No job directory is created at all.** |

The only Signature-B trace is a zero-byte `output/pharma/.write_access_check_file.temp`, left from
job 7's preflight write check.

**Signature B therefore fails before Bedrock processes a single record** — earlier than dataset
parsing, and earlier than anything the dataset content could influence.

#### AWS's own validator certified this exact data

From job 3 (`n45xnijacww6`), the last job to complete validation:

```csv
fileName,totalProcessedRecordCount,acceptedRecordCount,partiallyAcceptedRecordCount,rejectedRecordCount
train.jsonl,189,189,0,0
validation.jsonl,21,21,0,0
```

**189/189 and 21/21 accepted. Zero rejected, zero partially accepted.** Bedrock's
`validated_prompts.jsonl` output is byte-identical to the submitted `train.jsonl`
(verified by comparison), so the validator neither rejected nor rewrote anything.

The S3 objects are unchanged since 2026-08-03 (`LastModified`). The identical bytes that Bedrock
certified as 100% valid on 2026-08-05 fail validation with an internal error from 2026-08-08 onward.
This is conclusive: **the dataset is not the cause.**

---

## 3. Hypotheses tested and eliminated

| # | Hypothesis | Method | Result |
|---|---|---|---|
| 1 | Training data malformed or too large | Re-read both S3 objects, parsed every line, asserted `bedrock-conversation-2024` schema | **Eliminated.** 189 train + 21 validation records, 0 malformed lines, correct schema and system prompt. Files unchanged since 2026-08-03 (S3 `LastModified`). Same data passed validation 3× in Signature A. |
| 2 | IAM role or S3 bucket config drifted | `CloudTrail LookupEvents` on both resource names, 2026-08-03 → now | **Eliminated.** Last mutating events were `CreateRole`/`PutRolePolicy`/`CreateBucket`/`PutBucketPolicy` on 2026-08-03 ~10:04 EDT — *before job #1*. Zero changes since. |
| 3 | IAM policy too narrow for Bedrock's preflight | CloudTrail on the failure windows; inspected `GenerateDataKey` calls | **Eliminated.** Bedrock's write-access check (`output/pharma/.write_access_check_file.temp`) succeeds — KMS `GenerateDataKey` returns cleanly, no `errorCode` on any event in either failure window. |
| 4 | Missing `GetObject`/`DeleteObject` on `output/*` | Hardened the policy via Terraform anyway, retried | **Eliminated.** Applied cleanly; job #6 failed identically. |
| 5 | Region-specific capacity problem | Checked fine-tuning regional support | **Not actionable.** Nova customization is `us-east-1`-only. No same-model region pivot exists. |
| 6 | Model-specific to Nova 2 Lite | Job #7 on **Nova Micro**, same account/region/data/role | **Eliminated.** Identical Signature B failure. **The problem is not model-specific.** |
| 7 | Service quota exhausted | `service-quotas list-service-quotas --service-code bedrock`, plus `ListCustomModels` / `ListCustomModelDeployments` | **Eliminated.** No customization quota is zero, and usage is far below every ceiling: custom models **0 / 100**, training+validation records **210 / 20,000**, in-progress deployments **0 / 2**. |
| 8 | Permanent account restriction | Job history predating this project | **Eliminated.** `finetune-nova3-k21` completed on the same account, region, and base model on 2026-04-15 — see §1.1. |

### Not yet ruled out

- An account-level or service-level condition in `us-east-1` affecting Nova customization broadly.
- A regression on the Bedrock service side introduced between Aug 5 and Aug 8.

Neither is diagnosable from the client. **AWS Health Dashboard and technical support cases both
require a paid support plan**; this account is on Basic, so neither is available.

---

## 4. Secondary findings

Three unrelated issues surfaced during the investigation. All are real and two were latent bugs.

### 4.1 Customization model IDs cannot be used for inference

`CreateModelCustomizationJob` takes a context-suffixed ID (`amazon.nova-micro-v1:0:128k`). Those IDs
are `PROVISIONED`-only and are **rejected by `Converse`**:

```
amazon.nova-micro-v1:0:128k  →  ResourceNotFoundException: Model not found.
us.amazon.nova-micro-v1:0    →  OK
us.amazon.nova-2-lite-v1:0   →  OK
```

The base-vs-tuned comparison passed `scenario.base_model_id` straight to `Converse`, so it would
have thrown on first use. It was never caught because **no job ever reached the inference stage**.

Fixed by adding an explicit `base_inference_model_id` to `ScenarioConfig` rather than deriving it —
the transform is not a simple suffix strip, since Nova 2 Lite additionally requires the `us.`
inference-profile prefix.

### 4.2 The cost estimator was model-blind

`cost_estimator.py` hardcoded Nova 2 Lite Price List usage types. Switching a scenario's base model
silently priced the wrong model — Nova Micro training is `$0.001/1K` vs Nova 2 Lite's `$0.00378/1K`,
so the cost gate would have **overstated the figure by ~3.8×**. Usage types are now derived from
`base_model_id` via an explicit map, and an unknown model raises `UnknownModelPricingError` rather
than guessing.

### 4.3 The Price List API and the model catalog disagree

`aws pricing get-products` still returns live SKUs for **Titan Text Lite and Express**
(`USW2-TitanTextG1-Lite-Customization-Training`, etc.), but both models are absent from
`list_foundation_models` in `us-east-1` and `us-west-2` — they are retired. Pricing SKUs persist
long after a model is withdrawn.

**`list_foundation_models` is authoritative for availability; the Price List API is not.**

---

## 5. Cost architecture note

Fine-tuned Bedrock models are served one of two ways, and the gap is the single largest cost
decision in this project:

| | Provisioned Throughput | Custom Model on-Demand (CMoD) |
|---|---:|---:|
| Billing | Per hour, whether used or not | Per token processed |
| Idle cost | $60.50/hr (Nova) | **$0.00** |
| 3 models, 48h weekend | **$8,712** | **$0.00** |
| 3 models, 30 days | **$130,680** | **$0.00** |

Only **five** base models support CMoD: Nova Micro, Nova Lite, Nova 2 Lite, and Nova Pro
(`us-east-1`), plus Meta Llama 3.3 70B Instruct (`us-west-2`). Every other fine-tunable model is
Provisioned-Throughput-only, which would exceed this project's $25/month budget in **under 90
minutes**.

Source: `deploy-custom-model-on-demand.html` → *Supported base models*.

---

## 6. Reproduction

```bash
.venv/bin/python - <<'EOF'
import boto3, json
c = boto3.client('bedrock', region_name='us-east-1')
j = c.get_model_customization_job(jobIdentifier='marco-demo01-pharma-micro-ft')
print(j['status'], json.dumps(j.get('statusDetails'), default=str), j.get('failureMessage'))
EOF
```

---

## 7. External references

- re:Post thread: _<add URL>_ — original question plus two follow-ups covering jobs 1–6.
  First reply suggested stop-and-retry, then a `us-west-2` fallback; the latter is not
  applicable, as Nova customization is `us-east-1`-only.
- Per-job event history is preserved in `artifacts/pharma/job_events.*.archived.jsonl`.

## 8. Resolution

**Job 8 succeeded in `us-west-2` on `meta.llama3-3-70b-instruct-v1:0:128k`.**

```
jobArn          arn:aws:bedrock:us-west-2:759316130780:model-customization-job/
                meta.llama3-3-70b-instruct-v1:0:128k/01xcxtpzr6tq
outputModelArn  arn:aws:bedrock:us-west-2:759316130780:custom-model/
                meta.llama3-3-70b-instruct-v1:0:128k/ty578u9h2s8j
validation      Completed  2026-08-09 23:59:35 -> 2026-08-10 00:03:06
training        Completed  2026-08-10 00:03:28 -> 2026-08-10 01:19:51
hyperParameters {batchSize: 1, learningRate: 1.0E-4, epochCount: 2}  (only epochCount supplied)
cost            $0.1759
```

Training converged cleanly — training loss 0.4749 -> 0.0268, validation loss 0.1763 -> 0.0452 with
no divergence between them. Input manifests: `train.jsonl 189/189 accepted`,
`validation.jsonl 21/21 accepted`.

### 8.1 What this does and does not prove

The dataset was **unchanged** between job 7 and job 8 — same 189/21 split, same
`bedrock-conversation-2024` schema. Job 7's own AWS-side manifest had already reported
`189,189,0,0` (100% accepted) before failing, so the data was never in question.

Changing Region **and** model family **and** provider simultaneously means the successful variable
cannot be isolated. What is now established:

- The dataset is valid — proven twice, by AWS's own validator and by a completed training run.
- The pipeline code is correct — the same code path launched all eight jobs.
- The failure is **not** account-wide: this account can run customization jobs to completion.
- The failure is scoped to `us-east-1`, the Nova model family, or their intersection. **Which one is
  unknown.**

Reproducing job 7 in `us-east-1` remains the only way to confirm the us-east-1 failure persists.
That test costs $0.00 (failures process no tokens) but is not required for the project to proceed.

### 8.2 Downstream verification

| Step | Result |
|---|---|
| `CreateCustomModelDeployment` | `Active` in ~8 minutes, $0 idle |
| Held-out eval, 21 unseen records | tuned **81%** both-fields-exact vs base **10%** |
| Schema validity through `PharmaTriageOutput` | **21/21 both models** |
| `make test-post-run` | 6 passed (pharma), 12 skipped (banking, it_helpdesk not yet run) |

### 8.3 Open

- re:Post thread never received an AWS answer. The April success and this us-west-2 success are
  both worth posting as data points if the thread is revived.
- `us-east-1` remains unusable for this account's Nova customization, cause unknown. Any future
  Nova work on this account should assume it will fail until proven otherwise.
