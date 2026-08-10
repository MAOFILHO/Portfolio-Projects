# Fine-tuning results — three scenarios, one pipeline

Every number here is measured, not projected. Three scenarios, one config-driven pipeline, one base
model (`meta.llama3-3-70b-instruct-v1:0:128k`, `us-west-2`), 2 epochs each.

Sources: [`COST-ACTUALS.md`](COST-ACTUALS.md), [`INCIDENT-LOG.md`](INCIDENT-LOG.md),
and `artifacts/{scenario}/results.json`.

---

## Scenario 1 — Pharmacovigilance Adverse-Event Triage (classification)

### The problem fine-tuning actually solves

A pharmacovigilance intake system classifies adverse-event reports into a **controlled vocabulary** —
8 MedDRA-style System Organ Class terms — and routes them by seriousness. Downstream, those values
are an enum: a case tagged `Cardiovascular` when the schema says `Cardiac` is a parse failure, not a
near miss.

| | |
|---|---|
| Base model | Meta Llama 3.3 70B Instruct (`us-west-2`) |
| Training records | 189 |
| Held-out records | 21 — the original positional split, verified non-leaking here: all 21 prompts are distinct clinical cases absent from training. Answer overlap is inherent to a 16-value output space and is not leakage |
| Epochs | 2 |
| Output contract | Strict JSON, validated by a Pydantic v2 model |
| House vocabulary | `Nervous system` · `Gastrointestinal` · `Skin` · `Cardiac` · `Respiratory` · `Hepatobiliary` · `Immune system` · `General` |

### Results — 21 records the model never saw

| Metric | Base Llama 3.3 70B | Fine-tuned |
|---|---:|---:|
| JSON well-formed, fields present | 21/21 · **100%** | 21/21 · **100%** |
| **Full schema incl. `event_category` enum** | 3/21 · **14%** | 18/21 · **86%** |
| `event_category` in house vocabulary | 3/21 · **14%** | 18/21 · **86%** |
| `seriousness` exact match | 19/21 · 90% | 20/21 · 95% |
| `event_category` exact match | 3/21 · **14%** | 18/21 · **86%** |
| **Both fields exact** | 2/21 · **10%** | **17/21 · 81%** |
| Total tokens consumed | 3,142 | **2,715** |
| Mean latency | 501 ms | 728 ms |

Training converged cleanly with no overfitting:

| | Epoch 1 | Epoch 2 |
|---|---:|---:|
| Training loss | 0.4177 | **0.0268** |
| Validation loss | 0.1763 | **0.0452** |

### The finding that matters most

> **Fine-tuning did not fix JSON syntax. A system prompt already had that at 100%.**
> What it fixed was conformity to the *contract*.

Both models emitted well-formed, parseable JSON with the correct fields on every single record. The
widespread justification for fine-tuning — *"we need reliable structured output"* — was already
solved by prompt engineering before a dollar was spent on training.

That framing depends entirely on what the schema encodes. `PharmaTriageOutput` originally typed
`event_category` as a bare `str`, so it reported "valid" for answers the downstream enum would
reject. Constraining it to the 8-term vocabulary — which is what the real contract requires — moves
schema validity from *100% for both models* to **14% base / 86% tuned**.

> A schema that validates only the *shape* of a response will report success on output that breaks
> the system consuming it. "100% schema-valid" is only meaningful if the schema carries the whole
> contract.

What fine-tuning bought was **conformity to a specific downstream contract**, and the base model's
failure mode shows why that is a different problem:

```
BASE event_category values (21 records)     FINE-TUNED
13x  'Adverse Event'          [invalid]      5x  'Gastrointestinal'
 2x  'Cardiovascular'         [invalid]      3x  'Skin'
 2x  'Gastrointestinal'                      3x  'Nervous system'
 1x  'Immune system disorders' [invalid]     3x  'Respiratory'
 1x  'cutaneous'              [invalid]      2x  'Cardiovascular'  [invalid]
 1x  'hepatobiliary'          [invalid]      1x  'Infections'      [invalid]
 1x  'Respiratory'                           1x each: Immune system, Cardiac,
                                                 Hepatobiliary, General
```

The base model answered **`"Adverse Event"` 13 times out of 21** — a restatement of the task rather
than a classification. Correct English, unusable output.

**The sharpest example is case 17.** Given *"elevated liver enzymes,"* the base model answered
`hepatobiliary` — semantically perfect, and still a failure, because the contract says
`Hepatobiliary`. Cases 6 and 8 fail the same way (`Immune system disorders`, `cutaneous`). The base
model is not short on domain knowledge; it is short on **your** conventions. That is precisely the
gap fine-tuning closes and prompting does not.

### Error analysis — the 4 remaining misses

Reported in full because the failures are more instructive than the successes.

| # | Case | Gold | Tuned | Diagnosis |
|---|---|---|---|---|
| 2 | fever, life-threatening | `General` | `Infections` | Genuine model error — invented a category instead of using the catch-all, despite handling the parallel `fatigue` case correctly |
| 3 | chest tightness, mild | `Cardiac` | `Cardiovascular` | Pretrained term surviving training |
| 5 | chest tightness, fatal | `Cardiac` | `Cardiovascular` | Same root cause |
| 13 | shortness of breath, recovered after dose reduction | `Non-serious` | `Serious` | **Probable label defect** — see below |

**Cases 3 and 5 are a data problem, not a hyperparameter problem.** `Cardiac` is the
weakest-represented category in training (22 occurrences), and the pretrained prior for
`Cardiovascular` survived 2 epochs. The base model made the identical substitution, which confirms
the source. Fix: more `Cardiac` examples, or state the enum explicitly in the system prompt.

**Case 13 is likely mislabelled.** Base and fine-tuned models independently answered `Serious`.
When two models disagree with the label in the same direction, the label deserves scrutiny first —
and under ICH E2A, "recovered after dose reduction" without hospitalization is genuinely
non-serious. It is also the fine-tuned model's *only* seriousness miss. Excluding it:

| | Base | Fine-tuned |
|---|---:|---:|
| Both fields exact (20 records) | 2/20 · 10% | **17/20 · 85%** |

## Scenario 2 — Northwind Bank Virtual Assistant (prose, conditional rule)

Where pharma tests a closed output space, banking tests a **conditional** rule — and conditional
rules are where naive metrics lie.

The scenario's system prompt states two obligations:

1. *"End any answer about moving money with: 'Transfers may take 1–3 business days.'"*
2. *"Never give personalized investment, tax, or legal advice — instead suggest speaking to a
   licensed advisor."*

Rule 1 is conditional. A model that appends the disclaimer to every answer has not learned it.

### The held-out split had to be replaced

The positional last-10% split produced a validation set of **3 distinct questions**, all present in
training under different conversational prefixes, with **23/23 gold answers appearing verbatim in
training**, and containing **zero instances of either rule**. It measured memorisation and nothing
else. See `TASKS.md` **6.1a**.

Scoring therefore uses **16 purpose-written prompts**, none appearing in the 230 training records,
authored against the rules *before* the model finished training:

| Group | n | Tests |
|---|---:|---|
| **D** — money movement | 5 | disclaimer must appear (recall) |
| **N** — ordinary banking | 5 | disclaimer must **not** appear (precision) |
| **R** — advice requests | 4 | must refuse and refer out |
| **X** — adversarial | 2 | both rules at once; and a "transfer" mention that must *not* trigger the disclaimer |

> A behaviour backed by a single canned answer can never be held out by any split. Banking's ten
> advice-refusal records share one identical string, forming one indivisible group — it goes wholly
> to train or wholly to validation. Such behaviours require a written eval set, not a split.

### Results — 16 unseen prompts

| Metric | Base Llama 3.3 70B | Fine-tuned |
|---|---:|---:|
| Disclaimer applied **correctly** | 9/16 · **56%** | 15/16 · **94%** |
| Advice refusal correct | 15/16 · **94%** | 14/16 · 88% |
| **Both rules correct** | 8/16 · **50%** | **14/16 · 88%** |
| Total tokens | 3,201 | **2,492** |

| | Epoch 1 | Epoch 2 |
|---|---:|---:|
| Training loss | 2.4130 | **1.5281** |
| Validation loss | 2.4562 | **1.8341** |

### Precision, not recall, is the whole story

The base model emitted the disclaimer **13 times out of 16** where only **6** cases warranted it —
appending *"Transfers may take 1–3 business days"* to questions about changing a phone number,
replacing a damaged card, and enabling two-factor authentication. The fine-tuned model emitted it 5
times against 6 needed.

> Measured only as *"does the disclaimer appear"*, base scores **81%** and the fine-tuned model
> **31%** — the exact opposite of the truth. The negative cases are what give the metric meaning.
> **A conditional rule scored without negative cases will reward the wrong model.**

### The model generalised past its training data

Two cases initially scored as failures against a regex looking for the canned
`licensed financial advisor` string. The actual outputs:

| Prompt | Fine-tuned response |
|---|---|
| *"...structure my accounts to reduce my tax bill?"* | "consulting a **licensed tax professional**" |
| *"...inherited his account. What are my legal obligations?"* | "speaking with a **licensed attorney** or estate planning professional" |

The training data says *"licensed financial advisor"* and nothing else. The model learned the
**rule** — refer out to the appropriate licensed professional — rather than the string. **The metric
was wrong, not the model**, and it was corrected.

### The genuine regression

**X1** — *"Should I move my savings into crypto? If yes, walk me through transferring the money out."*

```
BASE   "I can't provide personalized investment advice. For guidance on investing in
        crypto, I recommend speaking with a licensed financial advisor... If you still
        wish to proceed with transferring..."              <- refuses AND helps

TUNED  "I can't answer those questions."                   <- refuses and stops
```

**The base model handled this better.** The fine-tuned model caught the advice trap but abandoned
the legitimate half of a compound request, and dropped the referral entirely. Training on 230 short
answers taught **terseness alongside the rules** — visible in the 22% token reduction, usually a
win, here the cause of a worse answer.

This is a real cost of fine-tuning and it only surfaces if the eval set contains compound requests.

## Scenario 3 — IT Helpdesk L1 (prose, unconditional rule) — a null result

Reported in full because a null result is a result, and this one is the most decision-useful of the
three.

The system prompt states two unconditional obligations: *"Give clear numbered troubleshooting
steps"* and *"Always end with: 'If this persists, I'll raise a ticket to L2.'"*

Scored on the **30 held-out records** produced by the new group-aware splitter — 30 distinct
questions, zero gold answers shared with training, and both rules present in 30/30.

### Results — 30 unseen questions

| Metric | Base Llama 3.3 70B | Fine-tuned |
|---|---:|---:|
| Numbered steps present | 30/30 · **100%** | 30/30 · **100%** |
| Ends with the exact L2 line | 30/30 · **100%** | 30/30 · **100%** |
| **Both rules correct** | 30/30 · **100%** | 30/30 · **100%** |
| Total tokens | 9,139 | 8,658 |

| | Epoch 1 | Epoch 2 |
|---|---:|---:|
| Training loss | 2.4379 | **1.5122** |
| Validation loss | 2.2182 | **1.7209** |

**Fine-tuning produced no measurable improvement.** The base model already satisfied both rules
perfectly, from the system prompt alone.

### It did not merely fail to improve — it failed to learn the style at all

| | Gold answers (180 training records) | Fine-tuned output (30 held-out) |
|---|---:|---:|
| Begin directly with `1.` | **180/180** | 0/30 — all have a conversational preamble |
| Contain markdown bold | **0/180** | **29/30** |
| Median length | **40 words** | **178 words** |

The training data is uniformly terse, unformatted numbered lists. The fine-tuned model emits
4.5x longer answers with preambles and markdown bolding — conventions appearing **nowhere** in its
180 training examples. On this scenario the tuned model is, behaviourally, still the base model.

This is consistent with the loss curve: training loss stalled at 1.51 and was still descending
steeply at epoch 2. **Two epochs undertrains prose generation.** Banking landed at 1.53 from an
independent run, so this is a property of the configuration, not one bad job.

### What this scenario actually establishes

**The value of fine-tuning scales with how hard the requirement is to express in a prompt.**

| Scenario | Requirement | Expressible in a prompt? | Gain |
|---|---|---|---:|
| `it_helpdesk` | unconditional format + fixed closing line | **Yes, completely** | **none** |
| `banking` | rule conditional on intent | Partly — the model must infer *when* | **50% -> 88%** |
| `pharma` | conformity to a closed 8-term vocabulary | No — enumerating it bloats every call and still fails | **10% -> 81%** |

> **$0.1476 bought nothing measurable here.** That is the finding. A team that fine-tunes to enforce
> an unconditional format is paying to solve a prompt-engineering problem — and, at 2 epochs, would
> not even get the formatting it trained on.

## Cost — estimated vs actual

| Stage | Estimated | Actual |
|---|---:|---:|
| Training (53,318 tokens x 2 epochs @ $0.0033/1K) | $0.1759 | **$0.1759** |
| Deployment creation | $0.00 | **$0.00** |
| Inference — held-out eval (42 calls, base + tuned x 21) | $0.0027 | **$0.0042** |
| Inference — exploratory probes and console playground | — | **$0.0013** |
| Idle, deployed and not invoked | $0.00/hr | **$0.00/hr** |
| **Total** | | **$0.1814** |
| Custom model storage, ongoing | | $1.95/month until deleted |
| Budget ceiling | | $25/month |

Training matched its estimate **exactly**, because Bedrock's training charge is a deterministic
function of tokens x epochs x unit price — there is no wall-clock component. The inference variance
is scope, not pricing: the estimate assumed one sample prompt, the run evaluated all 21 held-out
records against both models.

**The fine-tuned model is cheaper per call than the base model** — 2,715 tokens vs 3,142 across the
same 21 prompts, because it stopped padding its answers.

## The constraint nobody budgets for

Cost was never the binding limit. **Throughput was.**

| Quota (Llama 3.3 70B custom model deployment, us-west-2) | Value | Adjustable |
|---|---:|---|
| **Requests per minute** | **4** | **No** |
| Tokens per minute | 300,000 | No |
| Tokens per day | 16,200,000 | No |

The evaluation threw `ThrottlingException` at ~20 req/min and had to be paced to one call every
16 seconds — a 21-record evaluation takes 7 minutes, bounded entirely by rate limiting. The token
ceilings are effectively unlimited for this workload; the 4 req/min request ceiling **cannot be
raised by a quota increase request.**

> **Cheap does not mean fast.** Custom Model on-Demand's $0-idle billing is paid for in throughput.
> A UI that fires base and tuned concurrently consumes half the available rate on a single click.

## Why Custom Model on-Demand, not Provisioned Throughput

Bedrock offers two ways to serve a fine-tuned model. The gap is not marginal.

| | Provisioned Throughput | **Custom Model on-Demand** |
|---|---:|---:|
| Billing basis | wall-clock hours held | tokens processed |
| Idle cost | **still billing** | **$0.00** |
| 3 models, 48h weekend | **$8,712** | **$0.00** |
| 3 models, 30 days | **$130,680** | **$0.00** |

This constraint drove model selection, not the other way around. Only five base models support CMoD;
every other fine-tunable model would have exceeded the $25/month budget in under 90 minutes. It is
enforced in CI, not merely intended — `tests/unit/test_no_provisioned_throughput.py` fails the build
if `ProvisionedThroughput` appears anywhere under `src/`, `infra/`, or `scripts/`.

## What it cost to get here: 10 attempts, 1 model

Seven consecutive jobs in `us-east-1` failed to produce a model across two Nova base models — three
stalled at `trainingDetails: NotStarted` (one for 74 hours), four failed data validation in under
three minutes with `"Encountered an internal error."` The eighth attempt, **same dataset
byte-for-byte**, succeeded on the first try in `us-west-2` on Llama 3.3 70B.

**All seven failures cost $0.00.** Bedrock bills tokens processed during training; none were ever
processed. Under a wall-clock billing model, the 74-hour stall alone would have been ruinous.

The `us-east-1` root cause was **never identified** — it was routed around, not fixed. Every
hypothesis was eliminated (data validated 189/189 by AWS's own validator, zero IAM/S3 drift in
CloudTrail, quotas nowhere near limits, and the same configuration had succeeded on this account in
April). Changing Region, model family, and provider simultaneously means the successful variable
cannot be isolated. Full forensics in [`INCIDENT-LOG.md`](INCIDENT-LOG.md).

## Key engineering decisions

| Challenge | Resolution |
|---|---|
| Customization model IDs (`:128k`/`:256k`) are `PROVISIONED`-only and rejected by `Converse` | Added an explicit `base_inference_model_id` config field — the transform is not a suffix strip (Nova additionally needs a `us.` inference-profile prefix), and guessing fails at runtime |
| Cost estimator hardcoded one model's Price List usage types | Derived usage types from `base_model_id`; unknown models raise `UnknownModelPricingError` rather than silently pricing the wrong model (Nova Micro vs Nova 2 Lite is a 3.8x error) |
| `session.py` hardcoded `us-east-1`, ignoring `AWS_REGION` | Region now resolves from `Settings`. Teardown used this session — it would have reported a clean destroy while an out-of-region model kept billing |
| `Converse` calls omitted `maxTokens` | Bedrock defaults to the model's maximum and reserves that quota per call — a documented cause of throttling at low request volume |
| Post-run tests rebuilt job names instead of using recorded ARNs | Bedrock reserves job names permanently; the canonical name resolved to attempt #1 (`Stopped`), so the test asserted against the wrong job |
| S3 bucket names are global but buckets are regional | Region is part of the bucket name — deleting and recreating one name across regions blocks on AWS's unbounded name-release delay |
| Price List API returns SKUs for retired models | `list_foundation_models` is authoritative for availability; the Price List API is not. Costing from pricing data alone can plan around a model that no longer exists |

## Reproducing

```bash
# post-run verification against live AWS resources
make test-post-run

# confirm nothing is billing hourly
.venv/bin/python - <<'PY'
import boto3
for r in ['us-east-1', 'us-west-2']:
    c = boto3.client('bedrock', region_name=r)
    print(r, len(c.list_provisioned_model_throughputs().get('provisionedModelSummaries', [])))
PY
```

Teardown order is mandatory: **deployment → custom model → S3 → `terraform destroy`.** Reversing it
hangs the destroy.
