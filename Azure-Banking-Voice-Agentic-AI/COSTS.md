# COSTS.md — Azure-Banking-Voice-Agentic-AI

## Free-tier promotion — investigated 2026-08-20, before Phase 0 spending begins

**Finding**: The subscription (`960936b9-ecde-465b-be8d-776ca077dcd0`) has an active promotion:
`{"category": "freetier", "endDateTime": "2027-02-28T21:48:31Z"}` (confirmed live via
`GET /subscriptions/{id}?api-version=2022-12-01` — `subscriptionPolicies.spendingLimit` is separately
confirmed `"Off"` from the same call, so R-07's "no spend ceiling" framing is unaffected by this).

This was raised as a real risk to Phase 0's validity: if any of Phase 0's measured meters (ACS Audio
Streaming, PSTN Geographic inbound, Azure OpenAI GlobalStandard tokens, Container Apps compute) are
covered by this promotion, the "measured" numbers Phase 0 produces would read as $0 or reduced — not
because the meters are cheap, but because the promotion is absorbing them — and R-08's demo-runs/month
figure would be computed against a budget nobody will actually be charged once the promotion ends
(2027-02-28) or the covered quantity is exceeded.

### Mechanism (confirmed, sourced)

From Microsoft's own ["Understand Cost Management data"](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/understand-cost-mgt-data)
(fetched 2026-08-20):

> Costs shown don't include free and prepaid credits.

| Included in Cost Management | **Not included** |
|---|---|
| Azure service usage (including deleted resources) | **Unbilled services (for example, free tier resources)** |
| Marketplace usage/purchases | Support charges |
| Commitment discount purchases | Taxes |
| Amortization of commitment discounts | **Credits** |

This is a stronger problem than "net vs. gross": Cost Management doesn't discount a free-tier-covered
meter's line and show the discount separately — it **omits the unbilled portion entirely**. There is no
field, view, or API call inside Cost Management that recovers "what this would have cost without the
free tier." If a meter is covered, the true rate has to come from somewhere else.

### Scope of the promotion (partially verified, gap stated honestly)

Microsoft's ["Create free services" doc](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/create-free-services)
(fetched 2026-08-20) confirms the mechanism is a **fixed quantity allowance on a fixed, small list of
infrastructure SKUs** (its own example: 750 hrs/mo of specific B-series VMs), set at account creation,
not something individual services get added to routinely — consistent with the `"freetier"` category
name and the ~12-month window from account creation to `2027-02-28`. This is a different mechanism from
the one-time $200/30-day sign-up credit (already expired given the end date is >30 days out).

**What I could not independently confirm**: the literal, current, complete list of covered services.
Microsoft's public pricing page (`azure.microsoft.com/en-us/pricing/free-services`) renders that list
client-side in JavaScript — two fetch attempts here returned the page shell with no list content.
Historically and structurally (per the mechanism above), that list is dominated by core infrastructure
primitives (VMs, managed disks, blob/file storage, SQL/Cosmos DB, bandwidth, DNS, Load Balancer) and has
never included Azure OpenAI/AI Foundry model deployments (which only ever ship paid SKUs — no free F0
tier exists for realtime models) or Azure Communication Services calling/streaming meters. That's
high-confidence, not verified-to-certainty.

### Resolution: a human-only check, now a wizard stage

The one place that's authoritative *for this specific account* is the Azure Portal's own **Free
Services** blade (Cost Management + Billing → Free Services), which shows exactly which resources on
this subscription currently have free-tier headroom remaining. That's not exposed as a documented public
REST API — it's a portal-only view — so it can't be scripted. Added as a new stage in
`docs/phase0/wizard/03-cost-check-24h.sh`, run before that script trusts any Cost Analysis number:
open the blade, confirm none of ACS / Azure OpenAI / Container Apps appear as free-tier-covered.

**Fallback if Cost Analysis numbers look suppressed anyway** (near-zero despite confirmed real usage):
Cost Management's *dollar* figures can hide free-tier coverage, but **usage quantity is independently
measured regardless** — call count/duration from the echo app's own logs (already captured in
`docs/phase0/findings.md`), token counts from Azure OpenAI's own usage metrics. If suppression is
suspected, the fallback is `measured quantity × PLAN.md's independently-sourced list rate` (from the
pricing calculator API, not this project's own estimate) rather than trusting Cost Management's dollar
total for the affected meter. This is still "measured, not estimated" per Phase 0's exit gate — the
quantity is measured; the rate is Microsoft's own published rate, not a guess.

This section will be updated with the Portal check's actual result once Stage 0 of
`03-cost-check-24h.sh` runs (~24h after test calls, per the wizard's timing).

## Model pin revised — 2026-08-20

`docs/PLAN.md` decision 14 changed: `gpt-realtime-mini` pin moved from version `2025-12-15`
(`isDefaultVersion`, retires 2026-12-15, ~4mo runway at the time) to `2025-10-06` (retires 2027-04-06,
~7.5mo runway), at **identical audio-token pricing** ($10/$20 per 1M in/out — flat across every
mini-tier snapshot in the catalog). No cost impact from this change; runway impact is real.

Full comparison across every realtime-capable model in canadacentral (not just `gpt-realtime-mini`),
including why `gpt-realtime-2.1-mini` was considered and rejected (Preview, retires 2026-10-15 — the
*shortest* runway found, despite matching pricing) and the named B3 successor
(`gpt-realtime-1.5`, ~3.2x cost, reserved not adopted): `docs/phase0/findings.md`, "Model pin
reconsideration."

**Budget impact of the reserved successor, if ever adopted**: `gpt-realtime-1.5`'s full-tier pricing
would roughly double this project's per-minute floor (model cost portion goes from ~$0.009/min to
~$0.029/min at the same token-rate assumptions), materially cutting R-08's demo-runs/month figure.
Not adopted now for exactly that reason — recorded here so a future phase-gate reviewer sees the
trade-off already quantified, not something to re-derive.
