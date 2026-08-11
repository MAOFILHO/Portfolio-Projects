# Cost Model — Phase 2

**Assumption: zero free-tier credits, zero promotional credits.** This account is not new; AWS's current
free-tier program (checked live 2026-08-11) offers new accounts "$100 in credits immediately... up to $200
over 6 months" — this account gets none of it. Only the account-age-independent **always-free** allowances
apply (Lambda, DynamoDB storage, Step Functions, CloudWatch/SNS basics, listed below). **Lex V2 and S3
Vectors have no free tier of any kind, for any account.** Every figure below was re-verified live on
2026-08-11 against the AWS Price List API and current pricing pages — none is carried forward from memory or
from the Phase 0 plan's estimates without re-checking.

---

## ⚠ The one finding that changes the model most: Connect Customer vs. Connect Customer Basic

Amazon Connect now ships as two priced products, confirmed live today:

| Product | Voice rate | What it bundles |
|---|---|---|
| **Amazon Connect Customer** (the new default — *"all new instances are Connect Customer instances"*, which includes this project's instance, created 2026-08-11) | **$0.038/min** | Agentic voice/chat AI, no-code agent designer (ACXD), AI agent observability, case summarization, forecasting — a managed AI bundle this project deliberately does not use (`ADR-001`) |
| **Amazon Connect Customer Basic** | **$0.018/min service fee + ~$0.0022/min US local-DID telephony ≈ $0.0202/min** | Plain pay-as-you-go Connect with none of the above — what this project's own hand-built Lex V2 + Bedrock + LangGraph stack actually needs |

**This project's architecture (`ADR-001`) explicitly does not use Connect Customer's bundled AI capabilities**
— it uses Lex V2 for ASR/TTS/turn-management and its own Bedrock/LangGraph stack for everything else. That
makes **Connect Customer Basic the pricing tier that matches actual usage**, at roughly **half** the per-minute
rate the project's earlier cost estimates assumed.

**Status: ✅ done.** Marco approved the switch by name on 2026-08-11 and executed it via the console the
same day — confirmed by screenshot (`docs/runbooks/MANUAL-STEPS.md`). **The instance now runs Connect
Customer Basic; the Basic-tier figures throughout this document are the live, applicable rate, not a
projection.** The Customer-tier figures are retained below for the historical record only. Two questions
raised at Phase 2 sign-off were resolved before executing:

1. **Is the tier fixed at instance creation, forcing a new instance (and DID re-claim) to switch?** **No.**
   Confirmed live against `docs.aws.amazon.com/connect/latest/adminguide/enable-nextgeneration-amazonconnect.html`:
   the tier is an **instance-level toggle** — "Enable Connect Customer across your entire instance" section,
   with an **Enable**/**Disable** action, on the existing instance's own settings page. Switching to Customer
   Basic does **not** require creating a new instance and therefore carries **no DID release/re-claim risk** —
   the 180-day claim block does not enter into this decision.
2. **Is it IaC-expressible?** **No — console-only, as of 2026-08-11.** The `UpdateInstanceAttribute` API's
   documented attribute types (`INBOUND_CALLS`, `OUTBOUND_CALLS`, `CONTACTFLOW_LOGS`, `CONTACT_LENS`,
   `AUTO_RESOLVE_BEST_VOICES`, `USE_CUSTOM_TTS_VOICES`, `EARLY_MEDIA`, `MULTI_PARTY_CONFERENCE`,
   `HIGH_VOLUME_OUTBOUND`, `ENHANCED_CONTACT_MONITORING`, `ENHANCED_CHAT_MONITORING`,
   `MULTI_PARTY_CHAT_CONFERENCE`, `MESSAGE_STREAMING`) include nothing for the Connect Customer/Basic split,
   and Terraform's `aws_connect_instance` resource covers the same attribute set — no argument reaches this
   toggle either. Recorded as the fourth CLAUDE.md-permitted manual step in `docs/runbooks/MANUAL-STEPS.md`,
   which carries the exact console path. **Claude has no console/browser access in this session — Marco
   performs the switch directly**, consistent with his stated preference on a protected resource.

**The pre-switch Connect Customer tier was never a deliberate choice — it is simply what a newly created
Connect instance ships with by default** ("all new instances are Connect Customer instances," per AWS's own
docs). Every cost figure computed against the Customer tier anywhere in this document, including the ones
still shown below for the historical record, reflects that unexamined default, not a decision this project
made. Connect Customer Basic is the tier `ADR-001` actually calls for.

Both tiers are still carried in the tables below — **Customer tier retained for the historical record only**
(what the instance billed under before 2026-08-11), **Basic tier is now the live, active rate.**

---

## Always-free allowances (persist regardless of account age)

| Service | Allowance | Caveat |
|---|---|---|
| Lambda | 1,000,000 requests + 400,000 GB-seconds/month | Confirmed current |
| DynamoDB | 25 GB storage | **Confirmed today: the 25 free RCU/WCU portion applies only to provisioned-capacity tables. On-demand tables (this project's mode) get free storage only — every read/write request unit is billed from the first request.** This corrects an unstated assumption carried in earlier planning |
| Step Functions (Standard) | 4,000 state transitions/month | Confirmed perpetual, not a 12-month-only allowance |
| CloudWatch | 10 metrics, 5 GB logs (ingestion+storage+Insights scan), 10 alarms, 3 dashboards (≤50 metrics each), 1,800 Live Tail min/month | Confirmed current |
| SNS | 1,000,000 requests, 100,000 HTTP/S notifications, 1,000 email notifications/month | Confirmed current |
| AWS Budgets | First 2 action-enabled budgets free/month; plain monitoring-only budgets are free with no stated cap | A $25/month **non-action** budget alarm costs **$0** |
| **Lex V2** | **None.** No perpetual free tier exists on the current pricing page — pay-per-use from request #1 | Confirmed; the old "10,000 free text + 5,000 free speech requests for 12 months" language is gone |
| **S3 Vectors** | **None.** | Confirmed — no free tier for any account |

---

## Fixed monthly cost, idle (zero calls, zero conversations)

| Resource | SKU/tier | Free-tier coverage | Est. monthly cost | Cost if teardown forgotten | Teardown risk |
|---|---|---|---|---|---|
| Canada DID (`+14169871547`) | Claimed number, `PhoneNumberCountryCode: CA` | None | **$0.90–$3.00/mo, unverified exact rate** — read from Cost Explorer once ≥1 day of accrual exists (Q1) | Same — it survives `make destroy` **by design** (protected, separate state, `prevent_destroy`) | **None — this is intentional, not a leak.** Releasing/re-claiming risks a 180-day claim block, so this line item is a permanent fixture, not a risk |
| DynamoDB table(s) | On-demand, storage only while idle | 25 GB free storage | **$0.00** at demo-scale data volume (well under 25 GB) | $0.023/GB-month beyond 25 GB — trivial at this project's scale | Low — `make destroy` removes tables; on-demand mode means no idle compute charge regardless |
| S3 bucket(s) (transcripts, checkpoints overflow, policy corpus) | Standard storage | None (S3 has no always-free tier) | **~$0.01–$0.05/mo** at demo-scale data volume ($0.023/GB-month) | Same, scales with data retained | Low — `make destroy` empties and removes buckets; risk is only forgetting a bucket has `prevent_destroy` set incorrectly |
| Lambda functions | On-demand, zero invocations while idle | 1M req + 400k GB-s free | **$0.00** | $0.00 while idle regardless (no idle charge for Lambda) | None — Lambda has no idle cost by design |
| Step Functions (if used later) | Standard, zero executions while idle | 4,000 transitions free | **$0.00** | $0.00 while idle | None |
| CloudWatch dashboards/alarms | Within always-free limits at this project's scale | 10 alarms, 3 dashboards free | **$0.00** | Small overage cost only if alarm/dashboard count is later increased carelessly | Low |
| AWS Budgets alarm ($25/mo threshold) | Non-action monitoring budget | Free, no cap | **$0.00** | $0.00 | None |
| Lex V2 bot | No idle charge — pay-per-request only | None | **$0.00** while idle | $0.00 while idle | Low — `make destroy` removes the bot; the accepted `AWS::Lex::Bot` nested-stack approach (`ADR-007`) is destroyable in one command by design |
| **Total idle, excluding the protected DID** | | | **≈ $0.01–$0.06/mo** | | |

**The DID is the only cost that survives `make destroy` — by design, not by omission.** Every other line item
in this table goes to exactly $0.00 on teardown.

---

## Per-conversation marginal cost (8 turns, ~4 minutes) — corrected pricing

| Component | Rate | Est. cost |
|---|---|---|
| Connect voice, Customer tier *(historical — pre-2026-08-11)* (4 min × $0.038) | $0.038/min | $0.152 |
| **Connect voice, Customer Basic tier — ✅ live rate** (4 min × $0.0202) | $0.0202/min | $0.081 |
| Canada inbound telco add-on | Unverified exact rate | ~$0.01 (placeholder pending Cost Explorer read, Q1) |
| Lex V2 speech (8 turns × $0.004) | $0.004/request | $0.032 |
| Bedrock — routing+L2 merged call (Nova Micro, `ADR-004`), 8 turns, ~6k in / 1k out total | $0.035/$0.14 per 1M | ~$0.0003 |
| Bedrock — generation (Nova Lite default, `ADR-004`), ~6k in / 1k out total | $0.06/$0.24 per 1M | ~$0.0006 |
| Guardrails — input + output, 16 units total (content + PII) | $0.15/1k (content) · $0.10/1k (PII) | ~$0.004 |
| DynamoDB on-demand (checkpoint writes/reads, claim record) | $0.625/M WRU · $0.125/M RRU | <$0.001 |
| S3 (transcript, checkpoint overflow if any) | $0.023/GB-mo + $0.005/1k PUT | <$0.001 |
| **Total, Customer tier** *(historical)* | | **≈ $0.20/conversation** |
| **Total, Customer Basic tier — ✅ live** | | **≈ $0.13/conversation** |

**Telephony remains the dominant cost regardless of tier** — roughly 75–90% of the per-conversation total —
confirming the project's existing finding that Bedrock is noise by comparison, now more so after the Nova
pricing correction (Nova Micro/Lite both came in materially cheaper than the earlier estimate once re-verified).

---

## Scenario costs at demo volume (simulator-first per `D8`; real calls reserved for demo/verification)

| Scenario | Customer tier *(historical)* | Customer Basic tier — ✅ **live, active** |
|---|---|---|
| 20 real calls/month (verification + demo) | ~$4.00 + DID (~$1–3) ≈ $5–7/mo | ~$2.60 + DID (~$1–3) ≈ **$3.60–5.60/mo** |
| 100 real calls/month (stress-test the budget on purpose) | ~$20 + DID ≈ $21–23/mo | ~$13 + DID ≈ **$14–16/mo** |

Both scenarios stay under the **$25/month hard ceiling**, and the simulator (zero AWS spend, per `D8`) remains
the primary tool for anything beyond verification-scale real-call volume.

### ⚠ Does the $25/month ceiling survive the zero-free-tier rebuild? **Yes — and the active number now carries real margin, not a thin pass.**

Every figure in this cost model was built under the zero-credits/zero-promotional-free-tier assumption from
the first line of this document — there is no separate "real" number waiting to be discovered in Phase 8.

**Before the switch (Connect Customer, the unexamined default the instance shipped with):** worst case was
**100 real calls/month ≈$21–23/mo**, roughly **$2–4 of headroom** under the $25 ceiling — thin enough that
Marco flagged it as not comfortable given Q1 (the exact Canada DID rate) was still open. That flag was
correct: $2–4 left effectively no room for Q1 to land above its placeholder, a Canada-telco add-on to be
re-verified, or any modest usage growth beyond the modeled 100 calls.

**Now, live (Connect Customer Basic, executed 2026-08-11):** worst case is **100 real calls/month ≈$14–16/mo**,
**≈$9–11 of headroom** under the $25 ceiling — roughly **3x the pre-switch margin**. This is the number that
actually creates working room against Q1 and against normal estimate noise, which is why the switch was
treated as margin-creating, not cosmetic, and executed rather than deferred to Phase 8. At the project's
actual expected usage — simulator-first, ~20 verification/demo calls/month — the live tier sits at
**$3.60–5.60/mo**, with most of the budget unused.

**The one figure genuinely still open is Q1** (the exact Canada DID per-minute/per-day rate, pending ≥1 day
of Cost Explorer accrual). Against the live ≈$9–11 headroom, Q1 landing meaningfully above its placeholder no
longer threatens the ceiling the way it would have pre-switch. **Verdict: the ceiling holds, and the active
Basic-tier rate is what converts that from a thin pass into a real margin.**

---

## Bedrock standing-approval budget ($5 cap, Phases 3–7)

At the per-conversation Bedrock cost above (~$0.001/conversation across routing+L2+generation), the $5 cap
covers **roughly 5,000 simulated/eval conversations** before it would be exhausted — the cap is not expected
to bind at any point in Phases 3–7's actual usage (eval runs, red-team probes, development iteration). Actual
spend is logged per-run in `COSTS.md` regardless, so this is a monitored ceiling, not an unverified assumption.

---

## Guardrails cost detail

| Policy | Price | Note |
|---|---|---|
| Content filters | $0.15/1k text units | |
| Denied topics | $0.15/1k text units | |
| PII detection | $0.10/1k text units | |
| Contextual grounding check | $0.10/1k text units | Used on `CoverageQuestion`/`RentalTowingEntitlement` groundedness checks |
| Automated Reasoning checks | ~$0.17, **exact billing unit unconfirmed** — sources disagreed on "per policy" vs. "per 1,000 text units" | Not currently planned for use; re-verify before adopting |

A text unit = up to 1,000 characters. Billed only for enabled policies; a blocked **input** is billed for the
guardrail evaluation only (no FM call charged); a blocked **output** is billed for the guardrail evaluation
**and** the FM inference that already happened (per `ADR-010`'s `ApplyGuardrail`-based design, this project
pays this cost knowingly since the ordering requirement means the model call sometimes happens before an
output block is known).

---

## What's explicitly excluded from this model (and why that's safe)

Per the banned-services list in `CLAUDE.md` — OpenSearch Serverless, Kendra, provisioned-throughput Bedrock,
Aurora, NAT Gateway, always-on ECS/EKS/Fargate, Contact Lens, SageMaker endpoints, MSK, Connect Voice ID,
Connect Cases, multi-AZ anything — none of these appear anywhere in this model because none are used
anywhere in the accepted architecture (`ADR-001` through `ADR-011`). This is stated explicitly so their
absence reads as a design decision, not an oversight.

## Sources

All pricing figures fetched live on 2026-08-11 via a background research agent against the AWS Price List
API and current AWS pricing pages, per the project's standing rule to verify pricing against current sources
rather than memory. Full citation list is in `docs/adr/ADR-004-model-tier-router-strategy.md` (Bedrock/Guardrails
pricing) and the individual service pricing pages: `aws.amazon.com/{connect,lex,dynamodb,s3,step-functions,
lambda,cloudwatch,sns}/pricing`, plus `aws.amazon.com/products/connect/customer/pricing/` and its appendix for
the Connect Customer/Basic split.
