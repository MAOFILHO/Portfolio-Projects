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

**R-04's 72h idle-billing window is OPEN**, anchored to `PROVISION_TIME=2026-08-21T22:49:35Z`
(closes ~2026-08-24T22:49:35Z). **This value is manual, not written by either wizard script's normal
path** — `02-test-calls.sh`'s intended `CallConnected`-gated auto-write never got the chance to fire
against tonight's real calls (a since-fixed `--tail 500` bug silently emptied its log pull every
run). Anchored to the Container App's actual revision `createdTime` — the moment it started billing
— not `CALL1_TIME`. Do not touch it; do not re-run `02-test-calls.sh` (see open item 8).

Resources live: resource group `rg-azure-banking-voice-agentic-ai`; AOAI
`aoai-azure-banking-voice-cc` (`gpt-realtime-mini` 2025-10-06 GlobalStandard, NoAutoUpgrade); ACS
`acs-azure-banking-voice`; phone number `+17059100383` (owned, $1.00/mo, R-09 — never released);
Container Apps environment `cae-azure-banking-voice-p0`; Container App `ca-azbank-echo-p0`
(min-replicas=1, **billing now, this is the R-04 measurement subject**); two Log Analytics
workspaces (`...aiCS` is the real one, linked; `...aixC` is an orphan, left in place).

**Next action**: `03-cost-check-24h.sh`, ~24h after provisioning — Stage 1 is a human-only Portal
Free Services check (open item 4), then a Cost Analysis sanity check.

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
   only reliable check: does the evidence file's mtime advance across an interval boundary. **NOT yet
   confirmed to survive a real sleep/wake cycle** (verified only on a machine that stayed awake) —
   before trusting this is solved, check the snapshot file's timestamps for a gap matching any period
   the laptop actually slept; if found, treat log retention as still unsolved. Contains duplicate
   lines across overlapping pulls by design; dedup instructions in `docs/phase0/evidence/README.md`.
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
4. **Free-tier suppression risk, not yet closed out** — the subscription has an active `freetier`
   promotion (until 2027-02-28). `03-cost-check-24h.sh` Stage 1 (Portal Free Services blade check,
   human-only, no API exists for it) must run and confirm clean **before** any Cost Analysis dollar
   figure from this project is trusted.
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

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-02 and R-03 confirmed** 2026-08-21 (real calls, real echo, DTMF on 2/3 — see open item 3 for the
one gap). **R-04 in progress** — 72h window open, closes ~2026-08-24T22:49:35Z. **R-08** still
pending — needs Cost Analysis data from script 3. **R-01, R-05, R-06 resolved** (2026-08-20). **R-09**
(number irreplaceability) is a standing hard rule, not something to resolve. **R-07** is a standing
fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. `03-cost-check-24h.sh`, ~24h after provisioning: Free Services portal check (open item 4), Cost
   Analysis sanity check — including confirming the number's actual first bill date/amount.
2. `04-teardown-and-r08.sh`, ~72h after `PROVISION_TIME` (2026-08-21T22:49:35Z, i.e. ~2026-08-24
   afternoon): R-04 verdict, R-08 computation, teardown (keep the number — R-09, never released).
   Commit both evidence files (deduped) as part of this script's work, per open item 1.
