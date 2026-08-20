# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 0 — Provisioning & Meter Spike.** Gate passed (`APPROVED: Phase 0`, Marco, 2026-08-20). Working
through `docs/phase0/wizard/01-provision.sh` one stage at a time, stopping at each — Marco's explicit
preference this phase, not a default to assume carries to later phases.

**Stage reached: 9 of 12, this session, 2026-08-20.** Resources that exist: resource group
`rg-azure-banking-voice-agentic-ai`; Azure OpenAI resource `aoai-azure-banking-voice-cc` (S0, $0/hr
idle) with `gpt-realtime-mini` 2025-10-06 `GlobalStandard` deployed (`NoAutoUpgrade` confirmed, B3
satisfied); ACS resource `acs-azure-banking-voice` (`global`/`Canada`, $0/hr); **phone number
`+17059100383`, purchased, $1.00/mo, the project's first genuinely billable resource** (Container App,
Stage 12, is the next one that will bill just for existing — not created yet).

**R-09 added: number irreplaceability, now a hard stop condition.** ACS's Canadian geographic inventory
proved volatile enough this session (10→8 nationwide localities, one gone in ~20min) that a lost number
may not be re-purchasable. `docs/PLAN.md` tracked risks and `CLAUDE.md` stop conditions both now state
the number is never released, by any script, at any phase. `04-teardown-and-r08.sh`'s verification
upgraded to check the number itself (`GET /phoneNumbers`), not just its parent ACS resource — the old
check only proved the container existed. Full write-up (portfolio-quality, for Phase 8): `docs/phase0/
findings.md`, "ACS Canadian phone number inventory is genuinely volatile".

**Decision 13 revised and executed**: Toronto confirmed absent from ACS's Canada-wide geographic
inventory (R-05); DataZoneStandard confirmed NOT OFFERED (R-06). Purchased 705 (North Bay/Sault Ste
Marie, ON) instead — Marco's own stated first preference, live-confirmed via `Search Available Phone
Numbers`, purchase polled to `succeeded` and independently re-confirmed against the live owned-numbers
list (not trusted from the purchase response alone). `purchaseDate: 2026-08-20T21:46:17Z`.
`$0.0085/min` inbound confirmed unchanged (flat national Canada rate) — no `COSTS.md` rate change, no
R-08 recompute. **First billing date not confirmed** — the API exposes `purchaseDate` and
`billingFrequency: monthly` but no next-bill-date field; will be settled by Cost Analysis in script 3.
Full sequence: `docs/phase0/findings.md`, "Stage 9 — number purchased". Ledger: `COSTS.md`, "First
billable resource purchased".

**Five live wizard bugs found and fixed this session**, all the script's own pre-flagged "verify this"
warnings turning out real: Stage 7's `deployment update` CLI subcommand doesn't exist — ARM REST PATCH
instead (`4dc5966`). Stage 8's api-version was stale — corrected (`8533128`). Stage 9's api-version was
also stale, and its purchase step never actually checked success — rewritten to poll the operation
properly, verify against the live owned-numbers list, and on failure auto-search-and-stop rather than
silently substitute a number (`acc9c34`).

**Two-project shared branch caution**: a concurrent session's staged `AWS-Insurance-FNOL-Voice-Agentic-AI`
files were caught by the scope pre-commit hook mid-session, unstaged (index-only) before committing.
Verified every commit this session touches only `Azure-Banking-Voice-Agentic-AI/` paths. Branch
worktree separation agreed with Marco, deliberately deferred to after Phase 0 completes — see open
items.

**Next action**: Stage 10+ (ADRs, echo app, Container App deploy). **Stopped here per explicit
request** — Marco wants to confirm the first billable resource (the number, above) is exactly as
expected before anything else runs.

## Open items

1. **Docker Hub vs ACR** — `01-provision.sh` uses Docker Hub's free tier for the Phase 0 echo-app image
   specifically to avoid `az containerapp up`'s auto-provisioned ~$5/mo ACR Basic tier (unbudgeted in
   `docs/PLAN.md`). That's fine for Phase 0's throwaway spike, torn down in script 4. **Due at Phase 1
   kickoff**: decide deliberately whether the real `voice-agent` image (rebuilt repeatedly, not
   throwaway) stays on Docker Hub or moves to ACR with managed-identity pull — the latter matches
   Phase 7's "no keys" direction (`docs/PLAN.md` Phase 7) but costs a real, budgeted ~$5/mo. Don't let
   Docker Hub persist by default with nobody having chosen it.
2. **Rate-limit meaning unresolved** — the Models API's per-deployment `rateLimits` field (`10
   requests/60s` for the pinned 2025-10-06 deployment, confirmed live on the actual deployment this
   session) doesn't reconcile against Microsoft's documented subscription-level Quota Tier table, which
   doesn't list `gpt-realtime-mini` by name at all. Strong circumstantial evidence points to "request =
   new session", not "request = turn" (see `docs/phase0/findings.md`, "Rate-limit interpretation"), but
   this is not confirmed by an exact documentation quote. **Now actionable** — the AOAI deployment
   exists; check the Foundry portal's Quota page directly, cheap, ~30s, still not done.
3. **`gpt-realtime-1.5` successor path is untested** — named in B3 (`docs/PLAN.md` decision 14) but its
   session-config/event/tool-call shape has never actually been booted against anything. `T-B3-SUCCESSOR-BOOT`
   is recorded as a Phase 2 deliverable (skip-by-default L1 test) but does not exist as code yet — it
   depends on `FakeRealtimeServer`, which Phase 2 itself builds.
4. **Free-tier suppression risk, not yet closed out** — the subscription has an active `freetier`
   promotion (until 2027-02-28). `03-cost-check-24h.sh` Stage 1 (Portal Free Services blade check,
   human-only, no API exists for it) must run and confirm clean **before** any Cost Analysis dollar
   figure from this project is trusted. Not yet run — no resources exist to check yet.
5. **Branch separation recommendation, decision pending** — this session found a concurrent session's
   staged (uncommitted) `AWS-Insurance-FNOL-Voice-Agentic-AI` files sitting in the same shared index,
   caught by the scope pre-commit hook before any commit happened. The hook did its job, but Marco
   doesn't want that race during a provisioning run. Recommended (not yet actioned): separate git
   worktrees per project (`git worktree add` off the same branch, or per-project branches) so two
   concurrent sessions never share one working tree/index — the pre-commit hook stays as a backstop,
   not the primary defense. Marco to decide whether/how to set this up.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

Still open, unresolved by anything measured yet: **R-02** (Pcm24KMono empirical behavior), **R-03**
(DtmfData during active streaming), **R-04** (Container Apps idle-vs-active billing, 72h window),
**R-08** (demo-runs/month, computed from measured meters — the Phase 0→1 gate). **R-01 resolved**
(2026-08-20, decision 14 revised). **R-06 resolved** (2026-08-20, DataZoneStandard confirmed NOT
OFFERED). **R-05 resolved** (2026-08-20, decision 13 revised to 705/North Bay, purchased). **R-09**
(number irreplaceability) is a standing hard rule (never released), not something to resolve — see
Current phase above. **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. Stage 10: write ADR-001 (data residency) and ADR-002 (geography knobs), using R-05/R-06 findings.
2. Stage 11: minimal echo WebSocket app.
3. Stage 12: build, push (Docker Hub — open item 1), deploy to Container Apps. **This is the next
   billable-per-hour resource** — state its rate from `COSTS.md` before it runs, per the standing gate.
4. Script 2: 3 test calls (human-only — Marco dials).
5. Script 3 (~24h later): Free Services portal check (open item 4), Cost Analysis sanity check —
   including confirming the number's actual first bill date and amount, per the "not confirmed" note
   in `COSTS.md`.
6. Script 4 (~72h after provisioning): R-04 verdict, R-08 computation, teardown compute (keep number,
   per R-09 — never released).
