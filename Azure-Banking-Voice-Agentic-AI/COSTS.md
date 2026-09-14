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

## R-04 telemetry window — scope note (2026-08-24, before script 4's Stage 4 writes the "Modeled from telemetry" section)

R-04's Replicas-continuity figure (`docs/phase0/findings.md`, "R-04 — Container Apps compute cost...")
measures `CALL3_TIME` (2026-08-21T22:54:09Z) to teardown — **the idle window only, by design**
(`04-teardown-and-r08.sh` Stage 1's own window definition, reused rather than invented fresh — see
that finding's "Window measured" line). It does not cover, and was never intended to cover, the
provisioning-through-test-calls period (`PROVISION_TIME` 22:49:35Z through Call 3's start at
22:54:09Z, which includes all three test calls). Do not read the "103/103 datapoints, zero gaps"
continuity claim as spanning back to provisioning — it doesn't. What does cover that earlier period is
log-based, not metric-based: see `docs/phase0/findings.md`, "R-03 residual — cold-start/scale-from-zero
hypothesis ruled out."

## Modeled from telemetry (generated 2026-08-25T01:26:32Z by docs/phase0/wizard/04-teardown-and-r08.sh)

| Item | Plan estimate | Modeled |
|---|---|---|
| Fixed monthly (extrapolated) | $5.29–$15.31 | $6.72 |
| Per-minute floor | $0.0215/min | $0.031/min |
| Container Apps idle-vs-active (R-04) | undocumented, decision 15 assumed idle | **IDLE** |
| Demo runs/month (R-08) | ~30-160 (naive, pre-eval-budget estimate) | **79.2** (gate: PASSED) |

**Provenance note**: none of the figures in this table come from an Azure Cost Management billing
query. `$6.72` (Fixed monthly) = `R04_MONTHLY_NET_OF_GRANT` (`$5.72`, computed from Container Apps
replica/network telemetry against Canada Central Retail Prices API rates, net of the free compute
grant) + a hardcoded `$1.00` phone-number constant — and matches `04-teardown-and-r08.sh`'s own
unmodified suggested default for that prompt exactly (`04:284`). `$0.031/min` (Per-minute floor) was
free-text keyboard entry at that script's `ask` prompt, matching the upper end of the fallback range
the prompt itself suggests typing (`04:290`) — not read from any per-minute billing meter. `79.2`
(Demo runs/month) is arithmetic performed on those two inputs (`04:294-309`). This run's three Cost
Management dollar-total queries (`COST_JSON`, `IDLE_COST_JSON`, `FULL_COST_JSON`) feed none of the
figures above.

If the free-tier promotion section above (or added by 03-cost-check-24h.sh) flagged any of these
meters as free-tier-covered, treat the "Modeled" column with that caveat — see that section's
fallback (measured quantity × PLAN.md's list rate) before trusting these dollar figures.

### Transport RTT baseline

See docs/phase0/findings.md "R-02 / R-03 / RTT" section — app-side processing-latency samples
from 3 test calls (turns, not calls; not a turn-latency percentile — that needs Phase 2's
RealtimeSession per B5).

### Full detail

docs/phase0/findings.md has the raw query results this wizard persists, with timestamps (R-01 through
R-06, R-08). Two are not persisted: Stage 2's full Cost Management roundup (FULL_COST_JSON) is
terminal output only, and Stage 1's raw Replicas/RxBytes/TxBytes metrics survive as derived counts,
not raw results.


---

## R-08, recomputed against a two-Container-App fixed cost — 2026-09-11 (issue #55)

**Verdict: PASSES, with headroom, and one input unpriced.** Phase 5 is the first phase since Phase 0
to create billable Azure resources, and `docs/PLAN.md`'s Phase-0 gate makes this recompute a
precondition of provisioning rather than a formality beside it. The figure this replaces — **79.2
demo runs/month**, recorded 2026-09-01 — assumed **one** always-on container. Phase 5 adds a second
(mock-core-banking) and a Storage account.

### Inputs, each traceable to where it was measured

| Input | Value | Where it comes from |
|---|---|---|
| One Container App, net of the free grant | **$5.72/mo** | R-04, measured from Container Apps replica/network telemetry against Canada Central Retail Prices API rates (`docs/phase0/findings.md`) |
| Container Apps operating mode | **IDLE**, measured | R-04, reconfirmed 2026-09-01 and 2026-09-08 |
| Container Apps monthly free grant | 180,000 vCPU-s, 360,000 GiB-s | `docs/PLAN.md`, Phase 0 |
| Replica shape | 0.25 vCPU / 0.5 GiB, min-replicas 1, max-replicas 1 | `infra/modules/mock-core-banking.bicep`, and the deployed voice agent |
| Phone number lease | **$1.00/mo** | Measured on the live owned-numbers record, 2026-08-20 |
| Realistic per-minute, call connected | **$0.031/min** | PSTN inbound + ACS streaming + model tokens, Phase 0 |
| Per-run ceiling | **5 minutes** | B4's per-call cap, which `docs/PLAN.md` step 10 names as the ceiling on one demo run |
| Table Storage | **$0.00/mo at this scale — see below** | Retail Prices API, `canadacentral`, `Standard LRS`, read live 2026-09-12 |

### The second container is not another $5.72, and the reason is arithmetic rather than judgement

**The free grant is per subscription, not per app**, and the first container already consumes all of
it. So the second one bills on its whole consumption rather than on its consumption net of a grant:

```
one replica, 24/7:   0.25 vCPU × 3600 s × 730 h  =   657,000 vCPU-s/month
                      0.5 GiB × 3600 s × 730 h   = 1,314,000 GiB-s/month

first app, billable:  657,000 − 180,000 =   477,000 vCPU-s   ratio 657/477 = 1.3774
                    1,314,000 − 360,000 =   954,000 GiB-s    ratio 1314/954 = 1.3774
```

**Both ratios are identical, and that is not a coincidence**: the replica shape (0.25 vCPU / 0.5 GiB)
is exactly the grant's own ratio (180,000 / 360,000), so the grant covers the same fraction of each
meter. That makes the second app's marginal cost a single clean multiple of the first's rather than
two figures that had to be added separately:

**$5.72 × 1.3774 = $7.88/mo** for the second container.

### The recomputed figure

```
fixed = $5.72 (voice agent) + $7.88 (mock-core-banking) + $1.00 (number) = $14.60/mo
headroom to the $25/month ceiling                                        = $10.40/mo
one demo run at B4's 5-minute cap                     = 5 × $0.031       =  $0.155
demo runs/month                          = $10.40 / $0.155              =  67.1
```

**67 demo runs/month** on `docs/PLAN.md` step 10's stated formula.

**45 demo runs/month** on the basis that is directly comparable with the recorded 79.2. That figure
came out of `04-teardown-and-r08.sh`'s own arithmetic, which produced 79.2 where step 10's formula
gives 117.9 for the same inputs — a factor of 0.672 this document cannot account for without
re-reading that script. Both numbers are quoted rather than one of them chosen, because picking the
larger would be choosing the flattering basis and picking the smaller would be pretending to a
precision this has not got.

**The gate is 5** (`docs/PLAN.md`, Phase 0 exit: "if it comes in under 5, Phase 0 stops here"). The
recompute clears it by roughly nine times on the conservative basis.

### The last unpriced input, priced — 2026-09-12

**Read live from the Azure Retail Prices API**, not from memory and not from a pricing page:
`serviceName eq 'Storage' and armRegionName eq 'canadacentral' and productName eq 'Tables' and
skuName eq 'Standard LRS'`. `Standard LRS` is the right row because
`infra/modules/call-records-store.bicep` sets `Standard_LRS` on a `StorageV2` account with
Microsoft-managed keys; the far pricier `Account Encrypted` rows in the same response are a different
encryption tier this account does not use.

| meter | rate (USD) |
|---|---|
| Write, Read, List, Scan, Delete, Batch Write operations | **$0.00036 per 10,000** |
| LRS Data Stored | **$0.05 per GB-month** |

The workload is the daily ledger and the escalation records — one row per day, a read-then-write per
call, a handful of rows per escalation:

```
operations   67 runs/mo × 10 ops/run = 670 ops   →  670/10,000 × $0.00036  = $0.000024/mo
stored       ~1,000 entities × ~1 KB = ~0.001 GB →  0.001 × $0.05          = $0.00005/mo
```

**Under one cent a month, which rounds to $0.00.** The top row of the sensitivity table below is not
a best case, it is the actual case. The table is kept because it is what made the recompute safe to
publish before the rate was known:

| Table Storage allowance | Fixed | Headroom | Runs (formula) | Runs (comparable) | Gate |
|---|---|---|---|---|---|
| **$0.00/mo — measured** | **$14.60** | **$10.40** | **67.1** | **45.1** | **PASSES** |
| $1.00/mo | $15.60 | $9.40 | 60.7 | 40.7 | **PASSES** |
| $5.00/mo | $19.60 | $5.40 | 34.8 | 23.4 | **PASSES** |

**R-08's recompute stands unchanged at 45-67 demo runs/month against a gate of 5**, and it now has no
unpriced input. Two caveats stay attached. Operation counts per call are estimated from the code, not
measured against a real call, and a real call is what closes that. And rates are read on one date from
one API; the figure carries 2026-09-12 for the same reason a percentile carries its N.

### What this changes

- **R-08 moves from PARKED to recomputed.** The 79.2 figure is superseded and kept: it measured a
  one-container system, which is not the system Phase 5 provisions.
- **The $25/month ceiling holds** and was not renegotiated. It is part of what this project
  demonstrates.
- **The two-container shape is what the arithmetic assumes**: 0.25 vCPU / 0.5 GiB, min-replicas 1,
  **max-replicas 1**. The max matters twice — it is what keeps this figure true, and it is what makes
  the ledger's read-then-write correct (`call_records/store.py`). Changing either invalidates both.
- **Table Storage's real rate is no longer owed** — read live 2026-09-12, above.
- **Still owed before anything is applied**: the actual cost of both new resources checked against
  what this predicts once they exist. An ARM 200 OK proves creation, not cost.

---

## R-08, recomputed for Application Insights sharing the shared 5 GB grant — issue #62, 2026-09-13

**Not yet applied — this prices the diff issue #62 prepares (`infra/modules/app-insights.bicep`,
`infra/provision-app-insights.sh`), not a resource that exists yet.** Per `docs/phase6/exit-
criteria.md` D4, workspace-based Application Insights bills through the *same* Log Analytics
ingestion meter container logs already use — it is not a second grant, it is the same 5 GB/month
free allowance, shared. Rates below are restated from where they were already read live, not
re-derived here: `docs/phase6/exit-criteria.md` D4 and `docs/PLAN.md` "Observability tooling," both
sourced from the Azure Retail Prices API (2026-08-21 / 2026-09-11).

| meter | rate |
|---|---|
| Log Analytics ingestion, first 5 GB/month per billing account | **$0/GB** — permanent, not a trial |
| Log Analytics ingestion, beyond 5 GB/month | **$2.76/GB**, `canadacentral` |
| Application Insights data retention | 90 days included (vs. 31 for a generic workspace) |

### What Phase 6 actually adds to that shared meter

D5's shape bounds the worst case rather than requiring a live measurement: one call produces one
`call` span, up to 20 `turn` children (B4's own per-call turn cap), and per-turn `tool_call`/
`core_banking` children. Taking the most pessimistic count that shape allows — 20 turns, each with
one `tool_call` and one `core_banking` child — is 1 + 20 + 20 + 20 = **61 spans/call, worst case**.
A serialized Application Insights telemetry item (envelope + tags + D15's allowlisted attributes,
which are all short strings, ints or booleans — no transcript text, by construction) runs on the
order of 1–2 KB; taking the higher end, **2 KB/span, worst case**:

```
61 spans/call x 2 KB/span              =  122 KB/call, worst case
67 demo runs/month (R-08's own gate)   x 122 KB       =  8.2 MB/month, worst case
```

The two metrics this phase adds (`b4.daily_minutes_used`, `b5.turn_latency_seconds`) carry no
attributes (D14/`telemetry.py`) and add a few hundred bytes/call more — rounds to nothing against
the above.

**8.2 MB/month is ~0.16% of the 5 GB/month free grant**, before container logs (already measured at
"rounds to $0 in practice" for this project's volume — `docs/phase0/findings.md`, "Stage 12 —
auto-created Log Analytics workspace, cost verified") are added back in. Doubling the worst-case span
estimate, or assuming container logs alone now use ten times their historically measured volume,
both still land two orders of magnitude under the grant.

### The recomputed figure

**$0.00/mo added.** The fixed monthly total from the prior recompute above ("R-08, recomputed
against a two-Container-App fixed cost") is unchanged: **$14.60/mo fixed, 45–67 demo runs/month
against a gate of 5.** Application Insights does not move either number, because it shares a grant
with room to spare rather than adding a new billable meter at this project's volume.

**`PROJECT_STATE.md` open item 8 (the Log Analytics auto-provision choice) is settled in this same
pass**: `infra/modules/app-insights.bicep` binds the new resource to the existing
`workspace-rgazurebankingvoiceagenticai1D` explicitly — via `WorkspaceResourceId`, and an `@allowed`
Bicep constraint that accepts no other workspace name — rather than letting a fourth workspace get
auto-provisioned by omission the way the first three were (`docs/phase0/findings.md`, same section).

### What this does not price

- **The actual measured volume**, once real spans exist. This is a worst-case bound derived from the
  code's own shape (D15's table, B4's turn cap), not a measurement — `docs/PLAN.md`'s 200-OK rule
  applies here exactly as it does to delivery: a queried row after the D16 smoke call
  (`docs/phase6/smoke-call-runbook.md`) is what turns this bound into a measurement.
- **Any resource-level charge for Application Insights itself beyond the ingestion meter** — there
  isn't one; workspace-based Application Insights carries no separate per-resource fee, per the same
  Microsoft pricing page `docs/PLAN.md`'s "Observability tooling" section already quotes.
- **The Entra-authenticated ingestion path's own cost, if any** — D10's role question is still open
  (`/research`); this recompute assumes the same ingestion meter applies regardless of which
  authentication path is used, since auth method doesn't change billed data volume.
