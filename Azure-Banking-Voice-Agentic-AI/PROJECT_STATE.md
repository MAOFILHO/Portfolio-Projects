# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 0 — Provisioning & Meter Spike.** All 12 stages of `01-provision.sh` complete. Container App
`ca-azbank-echo-p0` is deployed, healthy, and **first real answered phone call happened
2026-08-21** — all 3 test calls to `+17059100383` connected, echoed correctly, DTMF registered on 2
of 3. Full session narrative: `docs/handoffs/2026-08-21-phase0-first-successful-call.md`,
`docs/phase0/findings.md` (everything from Stage 7 onward, including all bugs found/fixed this
session, is there — not duplicated here).

**R-04's 72h idle-billing window is still open** (wall-clock), anchored to
`PROVISION_TIME=2026-08-21T22:49:35Z` (closes ~2026-08-24T22:49:35Z) — but **R-04 and R-08 are both
already ANSWERED ahead of that close**, measured directly from Azure Monitor telemetry and the Retail
Prices API on 2026-08-22, not left for Monday's script 04 run to discover. That run is now
**confirmation + teardown, not discovery**. Full method and numbers: `docs/phase0/findings.md`, "R-04
— Container Apps compute cost..." and "R-08 — demo runs/month, recomputed...".

- **R-04: IDLE** (Replicas metric shows zero scale-to-zero gaps; RxBytes/TxBytes stay under PLAN.md's
  own 1,000 B/s active threshold for every interval except the prior test call's expected tail). The
  bigger finding: Container Apps' standing free compute grant (180,000 vCPU-s/360,000 GiB-s per
  month) covers only ~8.3 days (~27.6%) of this app's continuous runtime each month — it is *not*
  "compute is free," since `min-replicas=1` runs all month for real telephony. Net-of-grant monthly
  cost at the IDLE rate: **$5.72/mo** (Canada Central Retail Prices API rates, confirmed 2026-08-22).
- **R-08: ~79–114 demo runs/month, gate PASSES.** Recomputed on the corrected R-04 basis (fixed
  $6.72/mo [Container Apps + number] + $6/mo eval ceiling, $12.28/mo left for calls).
- **PLAN.md's Budget section is now confirmed stale** (not just estimated vs. measured): its
  $4.29/mo–$14.31/mo Container Apps figures reproduce exactly against **US East** retail rates, not
  Canada Central where every resource in this project actually lives (ADR-001/decision 12) — a
  region mismatch present since the 2026-08-19 scoping commit, not a rate change since. Correcting
  PLAN.md itself is a future approved edit (out of scope this session) — see open item 4 below.

Resources live: resource group `rg-azure-banking-voice-agentic-ai`; AOAI
`aoai-azure-banking-voice-cc` (`gpt-realtime-mini` 2025-10-06 GlobalStandard, NoAutoUpgrade); ACS
`acs-azure-banking-voice`; phone number `+17059100383` (owned, $1.00/mo, R-09 — never released);
Container Apps environment `cae-azure-banking-voice-p0`; Container App `ca-azbank-echo-p0`
(min-replicas=1, **billing now, this is the R-04 measurement subject**); two Log Analytics
workspaces (`...aiCS` is the real one, linked; `...aixC` is an orphan, left in place).

**Next action**: `04-teardown-and-r08.sh`, ~72h after provisioning (~2026-08-24 afternoon) — R-04/R-08
confirmation, teardown of compute (keeping the number, R-09), dedup + one-time commit of both
evidence files. `03-cost-check-24h.sh` already ran 2026-08-22: `FREETIER_CLEAN=yes` (Container Apps
confirmed structurally absent from the subscription's free-services table, not just zero usage —
open item 4 below, closed), `COST_SANITY_CHECK=pass` (answered by the assistant this session, not
Marco — flagged in `docs/phase0/findings.md`).

**Three latent bugs found and fixed this session, all in the wizard scripts, none yet exercised
live**: `03-cost-check-24h.sh`'s `FREETIER_CLEAN` was read before ever being assigned as a real shell
variable (crash under `set -u`, same shape as the earlier `DATAZONE_OK` bug); both `03-` and
`04-teardown-and-r08.sh` called `az costmanagement query`, which doesn't exist in the installable
`costmanagement` CLI extension (fixed via `az rest` against the Cost Management Query REST API
directly); `04-teardown-and-r08.sh` called `ask()` three times without ever defining it (guaranteed
crash the moment Stage 1 ran, caught before Monday's one live run, not during it).

## Open items

1. **Log Analytics delivers zero rows — confirmed platform gap, needs real diagnosis before Phase
   1.** Both the native `appLogsConfiguration` path and an explicit `az monitor diagnostic-settings`
   resource are correctly configured (verified: right workspace, right categories enabled) and
   neither has delivered a single row, even after a full real-call lifecycle. `--follow`-based
   capture was tried and found **not durable** — known unresolved upstream bug
   ([Azure/azure-cli#28267](https://github.com/Azure/azure-cli/issues/28267)), empirically dies
   after ~5-6min idle every time. **The durable log path now** is a `launchd` LaunchAgent
   (`~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) pulling a plain `--tail 300`
   every 15min into `docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl`. **Periodic
   firing confirmed empirically 2026-08-21T22:33:30 local** (mtime advanced exactly at T0+900s with
   no manual action — `docs/phase0/findings.md`, "LaunchAgent — StartInterval scare..."). **Do not
   use `launchctl list <label>`'s output to check this** — it never echoes `StartInterval`/
   `RunAtLoad` for any job, scheduled correctly or not (verified against an unrelated known-scheduled
   agent), and `LastExitStatus 0` can't distinguish "ran once, dead" from "firing every 15min." The
   only reliable check: does the evidence file's mtime advance across an interval boundary.
   **Confirmed 2026-08-22 to survive a real sleep/wake cycle** — fired ~10 times over an overnight
   ~8h25m stretch, roughly every 50min rather than every 15 (`launchd` coalesces `StartInterval`
   jobs across sleep; expected, not a defect). Idle-rate margin still holds at that spacing; a wide
   gap between consecutive snapshot timestamps is coalescing, not an outage. Contains duplicate
   lines across overlapping pulls by design; dedup instructions in `docs/phase0/evidence/README.md`.
   **The committed 3-test-calls capture and the snapshot file are not interchangeable** — call 1's
   `CallConnected` scrolled out of the snapshot's `--tail 300` buffer before the LaunchAgent's first
   pull and is only in the committed capture; teardown needs both files (`docs/phase0/evidence/
   README.md`, `docs/phase0/findings.md` "Overnight idle window...").
   **Do not commit either evidence file periodically** — commit once, at teardown, after the dedup
   pass. A production voice agent cannot run on Phase 1 with no durable logging; this needs a real
   fix, not a workaround, before then.
2. **`02-test-calls.sh` must not be re-run this window.** Its Stages 1-3 have no
   skip-if-already-confirmed guard, so it unconditionally prompts for 3 fresh billable calls before
   Stage 4's (free, read-only) evidence extraction can run — a design gap (cheap operation welded to
   an expensive one) logged in `docs/phase0/findings.md`, not fixed. Candidate fix for later: an
   `--extract-only` flag, or per-call `_existing` guards matching `01-provision.sh`'s shape.
3. **R-03 has one open, unexplained gap.** Calls 2 and 3 both registered 6/6 DTMF tones cleanly.
   Call 1 registered zero despite Marco pressing keys during it too — nothing in the logs (duration,
   frame count, event ordering) explains the miss. Recorded as genuinely unresolved in
   `docs/phase0/findings.md`, not reasoned away (an earlier draft incorrectly did so; corrected).
4. **PLAN.md's Budget section is stale — needs an approved edit.** The Container Apps
   $4.29/mo–$14.31/mo figures (and everything chained from them: COSTS.md's hourly-equivalents, the
   "honest result including evals" table's $11.29/$21.31/$13.71/$3.69) were computed against US East
   retail rates, not Canada Central where this project's resources actually live. Confirmed
   2026-08-22 by reproducing PLAN.md's own grant-netting method against both regions' live Retail
   Prices API rates — US East reproduces $4.29/$14.31 to the cent, Canada Central gives $5.72/$20.03.
   Not done here (`docs/PLAN.md` stayed out of scope this session); full derivation in
   `docs/phase0/findings.md`, "R-04 — Container Apps compute cost...".
5. **Docker Hub vs ACR — decided for Phase 0 only.** Private repo, free tier, avoids `az containerapp
   up`'s auto-provisioned ~$5/mo ACR. **Still due at Phase 1 kickoff**: decide deliberately whether
   the real `voice-agent` image stays on Docker Hub or moves to ACR with managed-identity pull (the
   latter matches Phase 7's "no keys" direction, `docs/PLAN.md` Phase 7, but costs a real ~$5/mo).
6. **Rate-limit meaning unresolved** — the Models API's per-deployment `rateLimits` field (`10
   requests/60s`) doesn't reconcile against Microsoft's documented subscription-level Quota Tier
   table. Strong circumstantial evidence points to "request = new session" (`docs/phase0/
   findings.md`, "Rate-limit interpretation"), not confirmed by an exact doc quote. Check the Foundry
   portal's Quota page directly — cheap, ~30s, still not done.
7. **`gpt-realtime-1.5` successor path is untested** — named in B3 (`docs/PLAN.md` decision 14) but
   never actually booted against anything. `T-B3-SUCCESSOR-BOOT` is a Phase 2 deliverable, depends on
   `FakeRealtimeServer`, which Phase 2 itself builds.
8. **`az` CLI stale `defaults.location=eastus`** (this machine only, `~/.azure/config`) silently
   empties `az resource list -g <rg>` for this project's resources in `on_error`'s "what's billing"
   table in both wizard scripts — the actual delete-offer safety check beneath it is unaffected. Fix
   (`--location ""`) identified, shown as a diff, **not yet applied** — pending sign-off.
9. **Phase 1 decision**: `az containerapp env create` always auto-provisions a Log Analytics
   workspace with no `--logs-destination`/`--logs-workspace-id` flag passed — $0 in practice at this
   project's volume, but see open item 1: the auto-provisioned path doesn't even deliver logs, so
   Phase 1 needs a deliberate choice here regardless of cost.
10. **R-03 residual promoted to a Phase 1 entry criterion (2026-08-24).** Call 1's zero DTMF tones
    remains unresolved (open item 3); the cold-start/scale-from-zero hypothesis was tested against
    existing evidence and ruled out (single cold start, 80s before Call 1's `IncomingCall`, single
    revision/replica ID throughout — `docs/phase0/findings.md`, "R-03 residual — cold-start/
    scale-from-zero hypothesis ruled out"). The two candidates that remain — DTMF not sent vs. sent
    but unrecognized upstream by ACS — can only be distinguished by ACS-side call diagnostics, which
    depend on open item 1's Log Analytics zero-rows gap being fixed first. **Blocked on open item 1;
    no further diagnostic calls should be placed until that path works** — app-side logs are
    downstream of ACS's decode fork and cannot separate the two candidates. Full disposition:
    `docs/phase0/findings.md`, "R-03 residual — promoted to a Phase 1 entry criterion".

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-02 and R-03 confirmed** 2026-08-21 (real calls, real echo, DTMF on 2/3 — see open item 3 for the
one gap). **R-04 ANSWERED 2026-08-22 (IDLE), ahead of the 72h window's wall-clock close** — measured
from telemetry, not Cost Analysis dollars; see Current phase above. **R-08 ANSWERED 2026-08-22:
~79–114 demo runs/month, gate PASSES** — recomputed from measured meters, not the naive estimate.
**R-01, R-05, R-06 resolved** (2026-08-20). **R-09** (number irreplaceability) is a standing hard
rule, not something to resolve. **R-07** is a standing fact (`spendingLimit: Off`), not something to
resolve.

## Next actions (in order)

1. `04-teardown-and-r08.sh`, ~72h after `PROVISION_TIME` (2026-08-21T22:49:35Z, i.e. ~2026-08-24
   afternoon): confirmation of the R-04/R-08 answers already measured above (not discovery), teardown
   of compute (keep the number — R-09, never released), dedup + one-time commit of both evidence
   files (per open item 1).
2. A future approved session: correct `docs/PLAN.md`'s Budget section per open item 4 (US East →
   Canada Central).
