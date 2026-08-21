# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 0 — Provisioning & Meter Spike.** Gate passed (`APPROVED: Phase 0`, Marco, 2026-08-20). Working
through `docs/phase0/wizard/01-provision.sh` one stage at a time, stopping at each — Marco's explicit
preference this phase, not a default to assume carries to later phases.

**Stage reached: 10 of 12, this session, 2026-08-20.** Resources that exist: resource group
`rg-azure-banking-voice-agentic-ai`; Azure OpenAI resource `aoai-azure-banking-voice-cc` (S0,
**consumption-billed** — pay-per-token, currently $0 because zero tokens have been consumed, not
because the resource type is free) with `gpt-realtime-mini` 2025-10-06 `GlobalStandard` deployed
(`NoAutoUpgrade` confirmed, B3 satisfied); ACS resource `acs-azure-banking-voice` (`global`/`Canada`,
same consumption-billed/$0-currently basis); **phone number `+17059100383`, purchased, $1.00/mo — the
first resource this project actually *purchased* (flat recurring fee, not usage-based)**, per
`COSTS.md`'s own precise framing. Container App (Stage 12) will be the first resource that bills **for
merely existing over time** (hourly rate, `min-replicas=1`), not the "second billable resource" —
AOAI and ACS are already billable-capable and predate it; corrected 2026-08-21 after stating this
wrong in chat.

**Stage 10 done: ADR-001 and ADR-002 written**, `docs/adr/`. ADR-001 (data residency) carries R-06's
exact error string (SKU not supported, not a quota/permission error) and states the residency claim
both ways deliberately — at-rest data provably Canadian, processing not guaranteed Canadian-only under
Global deployment type — with an explicit instruction not to overstate either direction, and drops the
unconfirmed "30 days" retention figure. ADR-002 (geography knobs) closed the original `dataLocation`
question (no coupling to number purchase, confirmed) but is written around the finding that mattered
more: ACS's Canadian geographic inventory is 10 localities nationwide with no Toronto/GTA presence at
all, and volatile on a ~20min timescale (10→8, Guelph vanished) — the actual cause of decision 13's
revision and R-09. Written as a platform finding for the Phase 8 write-up, not an apology for a changed
plan. `01-provision.sh`'s Stage 10 heredoc corrected to match (was templating a thinner/stale version of
both ADRs) — committed with the ADRs.

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

**Next action**: Stage 11 (minimal echo WebSocket app) and Stage 12 (build/push/deploy to Container
Apps). **Stopped here per explicit request** — Stage 12 starts the hourly meter and the 72h R-04 idle
window; Marco wants to review before that clock starts.

## Open items

1. **Docker Hub vs ACR** — **decided 2026-08-21: Docker Hub Private, deliberate and Phase-0-only.**
   `01-provision.sh` uses Docker Hub's free tier for the Phase 0 echo-app image specifically to avoid
   `az containerapp up`'s auto-provisioned ~$5/mo ACR Basic tier (unbudgeted in `docs/PLAN.md`). Marco
   confirmed Private (not Public) for the throwaway spike, torn down in script 4. Two verifications
   Marco asked for could not be completed with available tooling, recorded honestly rather than
   asserted: (a) the Docker Hub access token's scope can't be checked before it exists — it's created
   interactively by Marco on Docker Hub's own UI at Stage 12 runtime, not generated by this script.
   **Fixed 2026-08-21**: the script's prompt (`01-provision.sh:1027`) now names an explicit scope —
   **Read & Write, not Read-only** (an earlier version of this note wrongly said Read-only; corrected
   after re-checking the script — the same token both `docker push`es the image and is used as the
   Container App's `--registry-password` pull credential later, so it needs both; Delete is never used
   by either step and should not be granted). (b) Whether
   Marco's Docker Hub free-tier private-repo slot is already used by another project (FNOL) is Docker
   Hub account state with no tooling access from here; a repo grep found no evidence FNOL uses Docker
   Hub at all (it appears AWS/ECR-based), but that's not the same as checking the account directly —
   Marco would need to confirm this himself. **Still due at Phase 1 kickoff**: decide deliberately
   whether the real `voice-agent` image (rebuilt repeatedly, not throwaway) stays on Docker Hub or moves
   to ACR with managed-identity pull — the latter matches Phase 7's "no keys" direction (`docs/PLAN.md`
   Phase 7) but costs a real, budgeted ~$5/mo. This Phase 0 choice does not carry forward by default.
   **`azure-identity` dropped from `docs/echo-app/requirements.txt`** (2026-08-21) — pinned but never
   imported anywhere in `app.py` (verified: only stdlib + `fastapi` + `azure.communication.callautomation`
   are imported). Its absence is a deliberate choice, not an oversight: `app.py` authenticates to ACS via
   connection string (`CallAutomationClient.from_connection_string`), and managed-identity auth is the
   same Phase 1 registry/auth decision as the Docker Hub/ACR question directly above — Phase 0's
   throwaway spike doesn't need it either way.
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
5. **Branch separation — done**, not pending. Actioned mid-Phase-0 by the concurrent FNOL session
   (`ae4cb96`, "OI60 closed via git worktree"), not something this project's own session initiated.
   Active work now happens in `~/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`
   (branch `azure-banking-work`); the original checkout at `~/K21/Real-world/...` (branch
   `azure-banking-voice-agentic-ai`) still exists sharing this repo's history but isn't where sessions
   should work. `git worktree list` confirms 3 worktrees exist (this one, the original, and a separate
   FNOL worktree) — verify with that command if this ever seems stale again. **The old checkout's own
   `CLAUDE.md` is known-stale** (still names itself canonical) — Marco's explicit decision 2026-08-21:
   do not sync it now, not before the 72h R-04 window closes. Fix on merge, not before. Settled — don't
   raise this again.
6. **`az` CLI stale `defaults.location=eastus`** (this machine, `~/.azure/config`, not project-scoped)
   silently empties `az resource list -g <rg>` for this project's `canadacentral`/`global` resources —
   root-caused 2026-08-21, full detail `docs/phase0/findings.md` ("`az` CLI stale `defaults.location`").
   No `create` call site in `01-provision.sh` is exposed (audited all 8; explicit or architecturally
   immune). What *is* exposed: `01-provision.sh:234` and `02-test-calls.sh:66`'s `on_error` traps show
   an empty/wrong "what's billing" table on this machine, though the actual delete-offer safety check
   below each is unaffected. Fix (`--location ""` on both call sites) identified, shown as a diff,
   **not yet applied** — pending Marco's sign-off, same as everything else touching these scripts.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

Still open, unresolved by anything measured yet: **R-02** (Pcm24KMono empirical behavior), **R-03**
(DtmfData during active streaming), **R-04** (Container Apps idle-vs-active billing, 72h window),
**R-08** (demo-runs/month, computed from measured meters — the Phase 0→1 gate). **R-01 resolved**
(2026-08-20, decision 14 revised). **R-06 resolved** (2026-08-20, DataZoneStandard confirmed NOT
OFFERED). **R-05 resolved** (2026-08-20, decision 13 revised to 705/North Bay, purchased). **R-09**
(number irreplaceability) is a standing hard rule (never released), not something to resolve — see
Current phase above. **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. Stage 11: minimal echo WebSocket app.
2. Stage 12: build, push (Docker Hub — open item 1), deploy to Container Apps. **This is the next
   billable-per-hour resource** — state its rate from `COSTS.md` before it runs, per the standing gate.
3. Script 2: 3 test calls (human-only — Marco dials).
4. Script 3 (~24h later): Free Services portal check (open item 4), Cost Analysis sanity check —
   including confirming the number's actual first bill date and amount, per the "not confirmed" note
   in `COSTS.md`.
5. Script 4 (~72h after provisioning): R-04 verdict, R-08 computation, teardown compute (keep number,
   per R-09 — never released).
