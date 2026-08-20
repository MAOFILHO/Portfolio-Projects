# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 0 — Provisioning & Meter Spike.** Gate passed (`APPROVED: Phase 0`, Marco, 2026-08-20). Working
through `docs/phase0/wizard/01-provision.sh` one stage at a time, stopping at each — Marco's explicit
preference this phase, not a default to assume carries to later phases.

**Stage reached: 7 of 12, this session, 2026-08-20.** Stages 1–4 (pre-flight, R-01, hard gate,
provider registration) done. **First billable-capable resources now exist**: resource group
`rg-azure-banking-voice-agentic-ai`, Azure OpenAI resource `aoai-azure-banking-voice-cc` (S0,
consumption-only, $0/hr idle — per `COSTS.md`), and the real `gpt-realtime-mini` 2025-10-06
`GlobalStandard` deployment, `deploymentState: Running`, `versionUpgradeOption: NoAutoUpgrade`
confirmed (B3 satisfied). **Still nothing metered per-hour** — ACS resource, Container App, and phone
number (Stages 8, 9, 12) don't exist yet.

**R-06 resolved**: DataZoneStandard probe attempted and failed — `InvalidResourceProperties: SKU
'DataZoneStandard' ... not supported by the model 'gpt-realtime-mini' version: '2025-10-06'`. Confirms
`docs/PLAN.md`'s prediction empirically, not just from the pricing/availability tables. Full detail in
`docs/phase0/findings.md`. Feeds ADR-001 (Stage 10, not yet written).

**Wizard bug found and fixed live**: `01-provision.sh`'s Stage 7 called
`az cognitiveservices account deployment update --version-upgrade-option NoAutoUpgrade`, but that
subcommand doesn't exist on the installed CLI (azure-cli 2.87.0 — only create/delete/list/show). The
script's `2>/dev/null || warn` fallback would have silently left the live deployment on
`OnceNewDefaultVersionAvailable` (confirmed that's what create-time actually returns) while only
telling you to go check the portal — a real B3 gap, not a hypothetical one. Fixed to use a direct ARM
REST PATCH instead, applied unconditionally and hard-failing (not warning) if it doesn't stick.
Committed `4dc5966`. This session's live deployment is confirmed corrected to `NoAutoUpgrade` via the
same PATCH.

**Previous session ended without committing two fixes** (found uncommitted in the working tree on
resume, matched their own in-code comments dated 2026-08-20): 01-provision.sh's `PROVISION_TIME` write
moved from Stage 1 to Stage 12 (correct R-04 anchor), and 02-test-calls.sh's `on_error` upgraded to
match 01's report-and-offer-cleanup shape instead of remind-only. Both reviewed and committed this
session (`2e3678a`, `4711c70`). Lesson generalized into `CLAUDE.md` as a standing resume-verification
rule — see there.

**Next action**: Stage 8 — ACS resource + live Toronto-area code inventory (R-05). **Stopping before
Stage 9 (number purchase) per Marco's explicit request — irreversible-ish, review needed first.**

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

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

Still open, unresolved by anything measured yet: **R-02** (Pcm24KMono empirical behavior), **R-03**
(DtmfData during active streaming), **R-04** (Container Apps idle-vs-active billing, 72h window),
**R-05** (live Toronto-area area-code inventory), **R-08** (demo-runs/month, computed from measured
meters — the Phase 0→1 gate). **R-01 resolved** (2026-08-20, decision 14 revised). **R-06 resolved**
(2026-08-20, DataZoneStandard confirmed NOT OFFERED — see Current phase above and
`docs/phase0/findings.md`). **R-07** is a standing fact (`spendingLimit: Off`), not something to
resolve.

## Next actions (in order)

1. Stage 8: ACS resource + live area-code inventory (R-05).
2. Stage 9: **number purchase — irreversible-ish, ongoing $1/mo. Marco wants to review before this
   specific stage runs, flagged separately from the general gate.**
3. Stages 10–12: ADRs, echo app, Container App deploy.
4. Script 2: 3 test calls (human-only — Marco dials).
5. Script 3 (~24h later): Free Services portal check (open item 4), Cost Analysis sanity check.
6. Script 4 (~72h after provisioning): R-04 verdict, R-08 computation, teardown compute (keep number).
