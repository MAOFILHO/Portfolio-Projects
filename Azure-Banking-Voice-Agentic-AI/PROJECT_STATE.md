# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 0 — Provisioning & Meter Spike.** Gate passed (`APPROVED: Phase 0`, Marco, 2026-08-20). Working
through `docs/phase0/wizard/01-provision.sh` one stage at a time, stopping at each — Marco's explicit
preference this phase, not a default to assume carries to later phases.

**Stage reached: 8 of 12, this session, 2026-08-20.** Stages 1–4 done. Resources that now exist:
resource group `rg-azure-banking-voice-agentic-ai`; Azure OpenAI resource `aoai-azure-banking-voice-cc`
(S0, $0/hr idle) with the real `gpt-realtime-mini` 2025-10-06 `GlobalStandard` deployment
(`deploymentState: Running`, `versionUpgradeOption: NoAutoUpgrade` confirmed — B3 satisfied); ACS
resource `acs-azure-banking-voice` (`location: global`, `dataLocation: Canada`, $0/hr). **Still nothing
metered per-hour** — Container App and phone number (Stages 9, 12) don't exist yet.

**B3 checked end-to-end** (deployed reality vs. code's expectation): live deployment matches
`docs/PLAN.md` decision 14 exactly. No application code exists yet to check on the other side (Phase 2
deliverable, confirmed by repo search — consistent with the phase plan, not a gap). Reading the
documented guard literally surfaced a design note for Phase 2: `ALLOWED_REALTIME_MODELS` keys on
deployment *name* only, not name+version, so it wouldn't by itself catch a same-name version drift
(R-01 already showed `gpt-realtime-mini` has ≥2 versions live). Full detail in
`docs/phase0/findings.md`, "B3 end-to-end check".

**R-05/R-06 resolved, one is a blocker.** R-06: DataZoneStandard confirmed NOT OFFERED (live probe
failed, `InvalidResourceProperties`). R-05: **Toronto is absent from ACS's entire Canada-wide
geographic-locality inventory** — not filtered out, not sold out, not present at all (10 localities
total in all of Canada; nearest is Guelph, ON, area code 226). **Decision 13 ("Canada local geographic,
Toronto area 416/647/437/905/289") cannot be fulfilled as written against current ACS inventory** —
needs Marco's decision before Stage 9 runs, not a silent substitution. Full raw evidence (queries,
responses, the endpoint sanity-check) in `docs/phase0/findings.md`, "R-05 — live Toronto-area
area-code inventory".

**Two live wizard bugs found and fixed this session** (both were the script's own pre-flagged "verify
this" warnings turning out to be real): Stage 7's `deployment update` CLI subcommand doesn't exist
(azure-cli 2.87.0) — fixed via ARM REST PATCH, `4dc5966`. Stage 8's api-version was stale
(`2022-01-11-preview2` → 400) — corrected to `2025-06-01`, plus the script now always dumps the real
locality list on a 404 instead of a bare unexplained error, `8533128`.

**Two-project shared branch caution, this session**: `git add` for one Azure file picked up 6 already-
staged `AWS-Insurance-FNOL-Voice-Agentic-AI` files not written by this session (a concurrent session
apparently working that project on the same shared branch/working tree). The scope pre-commit hook
caught it before commit; unstaged them with `git reset HEAD --` (index-only, did not touch their
working-tree content) and committed only the Azure file. Worth remembering this branch is shared
in real time, not just historically.

**Previous session ended without committing two fixes** — found uncommitted on resume, reviewed and
committed this session (`2e3678a`, `4711c70`). Lesson generalized into `CLAUDE.md` as a standing
resume-verification rule.

**Next action**: awaiting Marco's decision on decision 13 (R-05's finding) before Stage 9 can even be
scoped, plus his review/authorization of Stage 9 itself regardless — irreversible-ish, explicitly
flagged separately from the general gate. **Stopped here per explicit request.**

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
**R-08** (demo-runs/month, computed from measured meters — the Phase 0→1 gate). **R-01 resolved**
(2026-08-20, decision 14 revised). **R-06 resolved** (2026-08-20, DataZoneStandard confirmed NOT
OFFERED). **R-05 resolved but blocking** (2026-08-20, Toronto absent from ACS's Canada-wide geographic
inventory — decision 13 needs Marco's call before Stage 9; see Current phase above). **R-07** is a
standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. **Marco decides on decision 13** (R-05's finding: no Toronto-area geographic number available) —
   options on the table, none chosen: (a) a different Canadian geographic locality (none are
   Toronto-area — nearest found is Guelph, ON, area code 226), (b) Canada toll-free instead of
   geographic, (c) re-check at purchase time in case inventory has shifted (not verified as static).
2. Stage 9: **number purchase — irreversible-ish, ongoing $1/mo. Marco wants to review before this
   specific stage runs, flagged separately from the general gate.** Blocked on item 1 above.
3. Stages 10–12: ADRs, echo app, Container App deploy.
4. Script 2: 3 test calls (human-only — Marco dials).
5. Script 3 (~24h later): Free Services portal check (open item 4), Cost Analysis sanity check.
6. Script 4 (~72h after provisioning): R-04 verdict, R-08 computation, teardown compute (keep number).
