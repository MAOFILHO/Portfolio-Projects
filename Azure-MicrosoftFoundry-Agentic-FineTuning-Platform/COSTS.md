# COSTS.md — approved cost record

**Approved:** 2026-08-05 · **Budget ceiling:** $25 USD · **Region:** eastus2

This is the permanent record of what was costed and approved. Per the project's
governing rule: *no resource may be provisioned that is not listed here.*

---

## Headline finding

**Nothing in this design bills by the hour.** Every model deployment is either
Global Standard or Developer Tier — both are pay-per-token with a **$0/hour**
rate. An accidentally-abandoned stack therefore costs essentially nothing, which
is the single most important cost property of this build.

The dominant cost is **not** infrastructure. It is Demo 1's evaluation run:
16 AI-judge evaluators × 45 synthetic rows, plus the target model's own tokens.

---

## Cost table

Pricing verified by web search against Microsoft documentation on 2026-08-05.

| Resource | SKU / tier | Reason | Cost/hr idle | One session (~8 h) | Left 48 h | Left 30 d | Cheaper alternative |
|---|---|---|---|---|---|---|---|
| Resource group | — | container | $0 | $0 | $0 | $0 | — |
| Foundry (Cognitive Services `AIServices`) | **S0** | only tier offered for AIServices | $0 | $0 | $0 | $0 | none exists |
| Foundry project | — | child of account | $0 | $0 | $0 | $0 | — |
| `gpt-4.1` deployment (baseline) | GlobalStandard | lab baseline; $0/hr | $0 | ~$0.10 | $0 | $0 | — |
| `gpt-5.4` deployment | GlobalStandard | Demo 1 compare + eval target | $0 | ~$2.50 | $0 | $0 | gpt-5.4-mini |
| `gpt-5.4-mini` deployment | GlobalStandard | Demo 1 compare | $0 | ~$0.30 | $0 | $0 | — |
| **SFT training job** | **Developer** | 50 % off global training | n/a | **~$0.016** | n/a | n/a | — |
| Fine-tuned deployment | **Developer Tier** | **$0/hr**, auto-purged 24 h | **$0** | ~$0.05 | $0 | $0 | — |
| Application Insights + Log Analytics | PerGB2018, 30-day retention | tracing | ~$0 | ~$0 | ~$0 | ~$0.30 | console-only export |
| Storage account (TF remote state) | Standard_LRS | state + lock | ~$0 | ~$0 | ~$0.00 | ~$0.02 | local state |
| Consumption budget + alert | — | cost guard | $0 | $0 | $0 | $0 | — |
| Evaluation run (16 evaluators × 45 rows) | pay-per-token | Demo 1 §11 | n/a | **~$3.00** | n/a | n/a | fewer evaluators |

### Totals

| Scenario | Cost |
|---|---|
| **Mock mode (default), unlimited runs** | **$0.00** |
| **One full live test session (~8 h, all 3 demos)** | **≈ $3–6** |
| **Left running 48 h (accidental weekend)** | **≈ $0.00** |
| **Left running 30 d** | **≈ $0.50** |

**No line item exceeds $50/month.** No red flags.

---

## Why Developer Tier is the default

| Deployment type | Hourly | 30 days idle | SLA | Data residency |
|---|---|---|---|---|
| **Developer Tier** ✅ chosen | **$0.00** | **$0** | none | none |
| Standard | $1.70 | **$1,224** | yes | yes |
| Global Standard | $1.70 | $1,224 | yes | no |
| Regional Provisioned Throughput | PTU/hr | ≫ $1,224 | yes | yes |

Developer Tier deployments are removed automatically after 24 hours regardless of
usage, and may be redeployed on demand. For a demo/portfolio workload that
property is a *feature*: a forgotten deployment self-heals instead of quietly
accruing $1,224/month.

Trade-off accepted: no availability SLA and no data-residency guarantee. Neither
matters here. Switch via `FT_DEPLOYMENT_TYPE` in `.env` if they ever do.

---

## Reconciling with the lab guides' own figures

| Source | Stated total | Assessment |
|---|---|---|
| *Fine-tune a language model* §5 | $0.032 | **Accurate for training only.** The job log shows `Training tokens billed: 16000`; at the ~$2/1M global rate that is exactly $0.032. Using Developer training halves it to ~$0.016. |
| *Explore and compare models* §5 | $0.013 | **Understated.** It excludes the evaluation, which the guide's own results page shows consumed 65,615 target tokens plus 16 evaluators × 45 rows of judge inference plus a 10,000-token cluster analysis. Realistically ~$3. |

The estimates in this document are the honest ones and supersede the guides.

---

## Cost guards implemented

1. **Budget alert provisioned before any billable resource** — a Terraform
   resource (`azurerm_consumption_budget_resource_group`), not a manual step.
   Thresholds at 50 % / 80 % / 100 % of the $25 ceiling.
2. **`DEMO_MODE=mock` is the default.** Spending requires an explicit opt-in.
3. **Developer Tier everywhere it is offered** — training and FT deployment.
4. **Teardown sweeps every suffix**, so auto-increment orphans cannot hide.
5. **Post-teardown test is a release blocker** — it fails the build if any tagged
   resource survives.
6. Loud teardown reminder printed by `make provision` and in the README.

## Assumptions

- gpt-5.4 at $2.50/$15 per 1M input/output tokens; gpt-5.4-mini estimated at
  roughly one-tenth. Mini pricing was not separately confirmed and is the least
  certain figure here.
- gpt-4.1 fine-tune training at ~$2/1M tokens global, less 50 % for Developer.
- Evaluation judge-token volume extrapolated from the guide's screenshots.
- Application Insights stays within the 5 GB/month free grant.

## Dataset catalog addition (no cost impact)

The 7 additional fine-tuning datasets under `data/converted/` (see
CHANGELOG.md "Unreleased") add **$0** to every figure above — they're static
JSONL files with a `GET /finetune/datasets` / `validate_jsonl` /
`estimate_training_cost` read path in mock mode, no new Azure resources, and
no live training run has been submitted against any of them. Their cost
estimates shown in the UI are a ~4-chars/token heuristic, explicitly labelled
as such, and are informational only — the orchestrated "Run Demo 2" flow (the
one that actually simulates a submitted job) still runs exclusively against
`travel-finetune-hotel.jsonl`, so none of the totals above change.
