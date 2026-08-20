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

**B3 checked end-to-end, and the gap promoted to a hard Phase 2 requirement.** Live deployment matches
`docs/PLAN.md` decision 14 exactly. Reading the documented startup guard literally found it keyed on
deployment *name* only, not name+version — R-01 already showed one name can span versions with
different retirement dates/rate limits, so a name-only guard wouldn't catch a same-name version drift.
No longer just a design note: `docs/PLAN.md`'s B3 code block and Phase 2 description, and `CLAUDE.md`'s
B3 row, all updated (2026-08-20) to require the guard read the live deployment's actual model version
at boot and key on `(name, version)` together. Full detail: `docs/phase0/findings.md`, "B3 end-to-end
check".

**R-05/R-06 resolved. Decision 13 revised, not blocked** — Toronto confirmed absent from ACS's entire
Canada-wide geographic-locality inventory (R-06: DataZoneStandard also confirmed NOT OFFERED). Number
choice revised to **705 (North Bay, ON)** — Marco's own stated first preference, checked and found
live; the originally-considered fallback (Guelph, 226) evaporated from the inventory *during this same
session* (present at Stage 8, gone ~20 minutes later on re-check, confirmed not a fluke). A real,
purchasable 705 number was confirmed via `Search Available Phone Numbers` (not just the locality
lookup): `+17054829832`, geographic, inbound-only, $1.00/mo, hold expires ~15min from the check —
**not yet purchased**, and this specific hold has likely expired by now; Stage 9 must re-search before
buying. Per-minute inbound rate confirmed unchanged ($0.0085/min, single Canada-wide national rate per
Microsoft's PSTN pricing doc) — no `COSTS.md` change, no R-08 recompute triggered. `docs/PLAN.md`
decision 13, the R-05 risk row, and Phase 0 steps 4–5 all updated. Full evidence:
`docs/phase0/findings.md`, "R-05" and "R-05 supplemental".

**Three live wizard bugs found and fixed this session** (all were the script's own pre-flagged "verify
this" warnings turning out to be real, not hypothetical): Stage 7's `deployment update` CLI subcommand
doesn't exist (azure-cli 2.87.0) — fixed via ARM REST PATCH, `4dc5966`. Stage 8's api-version was stale
(`2022-01-11-preview2` → 400) — corrected to `2025-06-01`, plus the script now always dumps the real
locality list on a 404, `8533128`.

**Two-project shared branch caution, this session**: `git add` for one Azure file picked up 6 already-
staged `AWS-Insurance-FNOL-Voice-Agentic-AI` files not written by this session (a concurrent session
working that project on the same shared branch/working tree). The scope pre-commit hook caught it
before commit; unstaged them with `git reset HEAD --` (index-only, didn't touch their working-tree
content), committed only the Azure file. **Verified**: every one of this session's 8 commits touches
only `Azure-Banking-Voice-Agentic-AI/` paths (checked via `git show --stat` on each) — no contamination
occurred. Branch-separation recommendation given to Marco, decision pending — see open items.

**Previous session ended without committing two fixes** — found uncommitted on resume, reviewed and
committed this session (`2e3678a`, `4711c70`). Lesson generalized into `CLAUDE.md` as a standing
resume-verification rule.

**Next action**: Stage 9 — number purchase. **Stopped per explicit request**: Marco wants to see the
exact number and confirmed rate before the purchase call runs. Fresh `Search Available Phone Numbers`
call required first (the confirmed hold above has likely expired) — if Toronto has reappeared in that
re-check, stop and report before buying anything, per Marco's standing instruction.

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
OFFERED). **R-05 resolved** (2026-08-20, Toronto absent from ACS's Canada-wide geographic inventory;
decision 13 revised to 705/North Bay, live-confirmed purchasable — no longer blocking). **R-07** is a
standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. Stage 9: **number purchase, 705 (North Bay, ON) per revised decision 13 — irreversible-ish, ongoing
   $1/mo. Marco wants to see the exact number and confirmed rate before this runs.** Must re-run
   `Search Available Phone Numbers` fresh immediately before purchasing (the confirmed hold from this
   session has likely expired) and re-check Toronto one more time — if it's reappeared, stop and report
   before buying anything.
2. Stages 10–12: ADRs, echo app, Container App deploy.
3. Script 2: 3 test calls (human-only — Marco dials).
4. Script 3 (~24h later): Free Services portal check (open item 4), Cost Analysis sanity check.
5. Script 4 (~72h after provisioning): R-04 verdict, R-08 computation, teardown compute (keep number).
