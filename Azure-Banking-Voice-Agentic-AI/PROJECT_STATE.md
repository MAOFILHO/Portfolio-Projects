# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 0 — Provisioning & Meter Spike.** Gate passed (`APPROVED: Phase 0`, Marco, 2026-08-20). Working
through `docs/phase0/wizard/01-provision.sh` one stage at a time, stopping at each — Marco's explicit
preference this phase, not a default to assume carries to later phases.

**Stage reached: 3 of 12** (the hard gate itself, now passed). Stages 1–2 (pre-flight, R-01) done —
read-only, nothing created. **Nothing billable exists in Azure yet** except `Microsoft.Communication`
provider registration, which Marco triggered himself outside any session, currently `Registering`.

**Next action**: Stage 4 — register `Microsoft.Communication` (free, idempotent if already registering).

## Open items

1. **Docker Hub vs ACR** — `01-provision.sh` uses Docker Hub's free tier for the Phase 0 echo-app image
   specifically to avoid `az containerapp up`'s auto-provisioned ~$5/mo ACR Basic tier (unbudgeted in
   `docs/PLAN.md`). That's fine for Phase 0's throwaway spike, torn down in script 4. **Due at Phase 1
   kickoff**: decide deliberately whether the real `voice-agent` image (rebuilt repeatedly, not
   throwaway) stays on Docker Hub or moves to ACR with managed-identity pull — the latter matches
   Phase 7's "no keys" direction (`docs/PLAN.md` Phase 7) but costs a real, budgeted ~$5/mo. Don't let
   Docker Hub persist by default with nobody having chosen it.
2. **Rate-limit meaning unresolved** — the Models API's per-deployment `rateLimits` field (`3
   requests/60s` for the active pin) doesn't reconcile against Microsoft's documented subscription-level
   Quota Tier table, which doesn't list `gpt-realtime-mini` by name at all. Strong circumstantial
   evidence points to "request = new session", not "request = turn" (see `docs/phase0/findings.md`,
   "Rate-limit interpretation"), but this is not confirmed by an exact documentation quote. Check the
   Foundry portal's Quota page once the Phase 0 AOAI deployment exists (Stage 5–7) — cheap, ~30s.
3. **`gpt-realtime-1.5` successor path is untested** — named in B3 (`docs/PLAN.md` decision 14) but its
   session-config/event/tool-call shape has never actually been booted against anything. `T-B3-SUCCESSOR-BOOT`
   is recorded as a Phase 2 deliverable (skip-by-default L1 test) but does not exist as code yet — it
   depends on `FakeRealtimeServer`, which Phase 2 itself builds.
4. **Free-tier suppression risk, not yet closed out** — the subscription has an active `freetier`
   promotion (until 2027-02-28). `03-cost-check-24h.sh` Stage 1 (Portal Free Services blade check,
   human-only, no API exists for it) must run and confirm clean **before** any Cost Analysis dollar
   figure from this project is trusted. Not yet run — no resources exist to check yet.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

Still open, unresolved by anything measured yet: **R-02** (Pcm24KMono empirical behavior), **R-03**
(DtmfData during active streaming), **R-04** (Container Apps idle-vs-active billing, 72h window),
**R-05** (live Toronto-area area-code inventory), **R-06** (DataZoneStandard confirm/deny), **R-08**
(demo-runs/month, computed from measured meters — the Phase 0→1 gate). **R-01 resolved** (2026-08-20,
decision 14 revised). **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. Stage 4: register `Microsoft.Communication` (free).
2. Stages 5–7: resource group, Azure OpenAI resource, R-06 DataZone probe, real `gpt-realtime-mini`
   2025-10-06 deployment.
3. Stage 8: ACS resource + live area-code inventory (R-05).
4. Stage 9: **number purchase — irreversible-ish, ongoing $1/mo. Marco wants to review before this
   specific stage runs, flagged separately from the general gate.**
5. Stages 10–12: ADRs, echo app, Container App deploy.
6. Script 2: 3 test calls (human-only — Marco dials).
7. Script 3 (~24h later): Free Services portal check (open item 4), Cost Analysis sanity check.
8. Script 4 (~72h after provisioning): R-04 verdict, R-08 computation, teardown compute (keep number).
