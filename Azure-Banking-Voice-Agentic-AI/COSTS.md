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

## Pre-spend cost estimate — before any Stage 4+ resource is created (2026-08-20)

Every figure below is `docs/PLAN.md`'s Budget section estimate, restated as an hourly-equivalent for
the gate check before provisioning starts. These are estimates, not measurements — Phase 0's own job
is to replace them with real Cost Analysis numbers (see the sections above and below). Nothing here
should be read as already measured.

| What Stage 3+ creates | Fixed/idle rate | Hourly-equivalent | Starts billing at |
|---|---|---|---|
| Phone number (Stage 9) | $1.00/mo | ~$0.00137/hr | purchase — the one resource kept past teardown |
| Azure OpenAI resource + deployment (Stages 5–7) | $0 fixed | $0/hr while idle | consumption-only; only bills per token actually processed |
| ACS resource (Stage 8) | $0 fixed | $0/hr while idle | consumption-only; only bills per PSTN minute / streaming minute actually used |
| Container App, min-replicas=1, 0.25 vCPU/0.5GiB (Stage 12) | $4.29/mo idle – $14.31/mo active | ~$0.00588/hr – ~$0.0196/hr | from creation — this is the one resource that bills just for existing, R-04 is what determines which end of the range applies |

**Per-minute, only while an actual call is connected** (not an hourly rate — stated separately so it
isn't conflated with the idle rates above): $0.0215/min floor – $0.031/min realistic (PSTN + ACS
streaming + model tokens). Applies only during the 3 test calls in script 2, not during provisioning.

**Worst-case all-in hourly rate while Phase 0's resources sit idle between test calls**: ~$0.0196/hr
(Container App active-state ceiling) + ~$0.00137/hr (number) ≈ **$0.021/hr, ~$0.50/day** — this is the
number that matters for "how much does leaving this running overnight cost," not the per-minute call
rate.

## First billable resource purchased — 2026-08-20, Stage 9

**The phone number — measured, not estimated. Per R-09 (`docs/PLAN.md`), this number is never
released by any script, at any phase, for any reason.**

| Field | Value |
|---|---|
| Number | `+17059100383` (705 — North Bay/Sault Ste Marie, ON numbering plan area) |
| `purchaseDate` (live API, `GET /phoneNumbers`) | `2026-08-20T21:46:17.2076119+00:00` |
| Monthly lease | **$1.00 USD/mo**, confirmed on the live owned-numbers record, matches the pre-spend
  estimate above exactly — no revision needed |
| Inbound rate | **$0.0085/min**, single national Canada rate (confirmed via Microsoft's PSTN pricing
  doc, not area-code-specific — see `docs/phase0/findings.md`, "R-05 supplemental") |
| Capabilities | `calling: inbound`, `sms: none` — matches decision 17's scope exactly (no outbound, no
  SMS needed) |
| `billingFrequency` | `monthly` (from `GET /phoneNumbers`'s `cost` object) |

**First billing date: not confirmed.** `GET /phoneNumbers` and `GET /phoneNumbers/{number}` both
expose `purchaseDate` and `cost.billingFrequency` but **no explicit next-bill-date or cycle-anchor
field**. Microsoft's own docs describe monthly leasing fees as recurring "on a month-to-month basis"
without stating whether the first month is prorated from `purchaseDate` or billed in full, or which
day of the month the cycle anchors to. **Not asserted here as a specific date** — this will be settled
empirically once Cost Analysis actually shows a charge for this number (Phase 0 script 3, ~24h check,
same free-tier-suppression caveat as the rest of this document applies).

This is the first billable-capable resource this project has actually purchased. Everything before it
(AOAI resource + deployment, ACS resource) is consumption-only at $0 fixed cost; the Container App
(Stage 12, not yet run) is the next one that will bill just for existing.

## Free Services portal check (Stage 1, 03-cost-check-24h.sh, 2026-08-23T00:25:54Z)

Confirmed clean (no ACS/Azure OpenAI/Container Apps free-tier coverage): could-not-verify — the Free Services blade could not be checked

**Superseded same day (2026-08-22), by Marco directly, not via the wizard**: the blade above is
retired; the replacement path (Subscriptions → this subscription → Overview → "Top free services by
usage" → "View all free services") **does** work for this PayAsYouGo subscription. Result:
**Confirmed clean — yes.** Container Apps does not appear anywhere in the 57-row covered-meter table
(structurally ineligible, not just showing zero usage); only one meter (Networking Data Transfer Out)
shows any usage at all, and no Cognitive Services row shows usage either. Caveat: the table's own
banner warns of inaccuracy in the last 24h, and the full row list wasn't scrolled exhaustively, so a
Communication Services (ACS) entry can't be ruled out with total certainty — none was seen. Full
writeup and the corrected discrimination-at-72h analysis: `docs/phase0/findings.md`, "Free Services
blade retirement and the free-tier suppression question." `FREETIER_CLEAN=yes` in `.env.phase0`
reflects this, not the wizard's own re-run.

## R-04 telemetry window — scope note (2026-08-24, before script 4's Stage 4 writes the measured section)

R-04's Replicas-continuity figure (`docs/phase0/findings.md`, "R-04 — Container Apps compute cost...")
measures `CALL3_TIME` (2026-08-21T22:54:09Z) to teardown — **the idle window only, by design**
(`04-teardown-and-r08.sh` Stage 1's own window definition, reused rather than invented fresh — see
that finding's "Window measured" line). It does not cover, and was never intended to cover, the
provisioning-through-test-calls period (`PROVISION_TIME` 22:49:35Z through Call 3's start at
22:54:09Z, which includes all three test calls). Do not read the "103/103 datapoints, zero gaps"
continuity claim as spanning back to provisioning — it doesn't. What does cover that earlier period is
log-based, not metric-based: see `docs/phase0/findings.md`, "R-03 residual — cold-start/scale-from-zero
hypothesis ruled out."

## Measured, not estimated (generated 2026-08-25T01:26:32Z by docs/phase0/wizard/04-teardown-and-r08.sh)

| Item | Plan estimate | Measured |
|---|---|---|
| Fixed monthly (extrapolated) | $5.29–$15.31 | $6.72 |
| Per-minute floor | $0.0215/min | $0.031/min |
| Container Apps idle-vs-active (R-04) | undocumented, decision 15 assumed idle | **IDLE** |
| Demo runs/month (R-08) | ~30-160 (naive, pre-eval-budget estimate) | **79.2** (gate: PASSED) |

If the free-tier promotion section above (or added by 03-cost-check-24h.sh) flagged any of these
meters as free-tier-covered, treat the "Measured" column with that caveat — see that section's
fallback (measured quantity × PLAN.md's list rate) before trusting these dollar figures.

### Transport RTT baseline

See docs/phase0/findings.md "R-02 / R-03 / RTT" section — app-side processing-latency samples
from 3 test calls (turns, not calls; not a turn-latency percentile — that needs Phase 2's
RealtimeSession per B5).

### Full detail

docs/phase0/findings.md has every raw query result this wizard captured (R-01, R-02, R-03, R-04,
R-05, R-06, R-08) with timestamps.

