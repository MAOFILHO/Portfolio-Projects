# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/` and
`docs/handoffs/`, never here. Check this file's size before every edit — ceiling is ≤400 lines/~20KB;
move the oldest closed material out to `docs/phase0/` first if an addition would exceed it.

## Current phase

**Phase 1 — Agentic conversation prototype. Approved by Marco 2026-08-29** (`APPROVED: Phase 1`,
per `docs/PLAN.md`'s revised Phase 1 definition, 2026-08-28). Scope: agent turn loop over the
existing AOAI realtime deployment, tool calling (`get_balance`/`transfer`/`list_accounts`) over
in-memory mock accounts, the `app.py:86` try/except fix. DTMF, PIN/auth, B1 gate, evals,
observability explicitly out of scope this phase (`docs/PLAN.md` Phase 1, "Out of scope"). The
revised Phase 1 definition also resolves `docs/phase0/EXIT-AND-PHASE1-ENTRY.md` Part 3's three
open decisions: (a) scope = app.py fix only, not DTMF disambiguation; (b) R-03 dropped as an entry
criterion (known open question, not a blocker); (c) budget not gated explicitly in advance —
`04-teardown-and-r08.sh`'s own Stage 3 stop condition is the enforcement point, with an explicit
instruction to measure operating mode after the first real conversation before further spend. Not
yet started — no code written, no compute re-provisioned. Nothing here is billable yet.

**Mock accounts module done, TDD'd, green: `voice-agent/accounts.py` + `tests/test_accounts.py`**
(`make test`, stdlib unittest, 7 tests) — `list_accounts`/`get_balance`/`transfer` over a
module-level dict, unknown-account and non-positive-amount both raise, insufficient funds refuses
in speech without mutating. No tool-calling layer or agent loop wired to it yet.

**`/research` done: `docs/phase1/research-aoai-realtime-wire-format.md` (2026-08-29, live-sourced,
430+ lines).** Confirms audio format is an exact match (`audio/pcm`/`pcm16` @ 24kHz mono = ACS's
`Pcm24KMono`, no resampling needed) and documents the full tool-calling event flow
(`response.function_call_arguments.done` → `conversation.item.create`
`function_call_output` → `response.create`).

**RESOLVED 2026-08-29 by live probe: `gpt-realtime-mini` `2025-10-06` DOES support function/tool
calling on Azure.** What had been a load-bearing open question (doc inference from Azure's
changelog wording suggested `2025-10-06` might lack parity with the newer `2025-12-15` version) was
settled empirically, not by more reading: a WebSocket session against the live
`aoai-azure-banking-voice-cc` deployment, declaring one trivial tool (`get_time`), got the tool
echoed back verbatim in `session.updated` and a full `response.function_call_arguments.delta` →
`.done` sequence when prompted — zero error events. Raw log:
`docs/phase1/evidence/tool-calling-probe-2026-08-29.json`; narrative:
`docs/phase1/research-aoai-realtime-wire-format.md`'s "RESOLVED" callout. **No B3 pin change
needed — Phase 1's tool-calling scope is buildable against the current deployment as-is.** No new
Azure resource was created for this check (existing deployment, kept live at Phase 0 teardown for
exactly this purpose, `04-teardown-and-r08.sh:397`).

Five smaller open questions remain, none blocking bridge-building: session.update shape ambiguity
between an older flat schema and the GA nested one (this probe used and confirmed the GA nested
shape works); which session fields are `session.update`-settable; input/output format symmetry not
stated as a hard rule; `semantic_vad` reliability on Azure (untested — `server_vad` is the
confirmed-working default, used in this probe's session too). Full detail in the research doc.

**First real Phase 1 call, 2026-09-01: all 6 `docs/PLAN.md` exit-test rows PASS** (balance query,
transfer, mutated-balance re-check, overdraft refusal, unknown-account refusal, clean call end) —
table with results in `docs/PLAN.md`, Phase 1 REVISED section. Open defect found on this call: see
open item 12 below. Step 5's operating-mode reading was also taken on this call — RxBytes/TxBytes idle-baseline (~180
KB/15min) before the call, call itself visible as a ~23 MB spike (Replicas held at 1.0 throughout,
but that's not idle/active evidence: `--min-replicas 1 --max-replicas 1` means it can't read
anything else regardless); full data in
`docs/phase1/evidence/first-call-operating-mode-2026-09-01.md`.
**Not yet a verdict** — PLAN.md's method needs a second reading ~1h after the first; until then the
R-08 branch decision (`docs/PLAN.md`, Phase 1 section) has nothing to act on.

## Phase 0 — closed, retained for reference until moved to `docs/phase0/`

**Phase 0 — Provisioning & Meter Spike.** All 12 stages of `01-provision.sh` complete. Container App
`ca-azbank-echo-p0` is deployed, healthy, and **first real answered phone call happened
2026-08-21** — all 3 test calls to `+17059100383` connected, echoed correctly, DTMF registered on 2
of 3. Three earlier inbound calls that day were dropped by the `APP_BASE_URL` placeholder race,
fixed same-day in `770c1f3`, before these three connected. Full session narrative:
`docs/handoffs/2026-08-21-phase0-first-successful-call.md`,
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

1. **Log Analytics: root cause found 2026-08-27, corrects an earlier claim on this line.** The
   native `appLogsConfiguration` path is correctly configured (verified: right workspace, right
   categories enabled) and is the source of all Phase 0 console/system data (2743+71 rows, in
   `_CL`-suffixed tables). The explicit `az monitor diagnostic-settings` resource
   (`azbank-p0-console-logs`) was NOT correctly configured, contrary to what this line previously
   said: created without `--export-to-resource-specific`, it defaulted to the `AzureDiagnostics`
   table and delivered nothing. Full evidence: `docs/handoffs/2026-08-27-phase1-logpath-resolved.md`.
   `--follow`-based
   capture was tried and found **not durable** — known unresolved upstream bug
   ([Azure/azure-cli#28267](https://github.com/Azure/azure-cli/issues/28267)), empirically dies
   after ~5-6min idle every time. **The `launchd` LaunchAgent poller is dead, as of 2026-08-28** — not
   loaded (`launchctl list` shows no matching label), and its plist
   (`~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) is absent from disk (script 04 only
   ever unloads this plist, never removes it, so the absence is unexplained — open item, see the
   summary file below). Last real write: 2026-08-25T01:15:46Z. Its evidence file
   (`docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl`, 51,981 lines) is preserved
   permanently in commit `07faf3b`; as of 2026-08-28 it's untracked (`.gitignore`) and local-disk-only
   — breakdown and the open plist-absence item are in
   `docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21-SUMMARY.md`. A production voice agent
   cannot run on Phase 1 with no durable logging; this needs a real fix, not a workaround, before
   then.
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
10. **SUPERSEDED 2026-08-28: R-03 residual is no longer a Phase 1 entry criterion.** `docs/PLAN.md`'s
    revised Phase 1 explicitly drops it ("known open question, not a Phase 1 blocker — it concerns
    the deleted echo app, and Call 1's evidence no longer exists to settle it"). Left unresolved
    permanently for Call 1 specifically; Calls 2/3 already confirm DTMF works in the common case.
    ACS-side diagnostics were never configured and this decision means they won't be, for this
    question. Full history: `docs/phase0/EXIT-AND-PHASE1-ENTRY.md` Part 3(b).
11. **`docs/echo-app/app.py:86` — `answer_call()` has no `try`/`except` and no fallback (open
    defect for Phase 1, not fixed).** Any ACS rejection propagates unhandled, returns `500` to
    Event Grid, and drops the call silently — the caller hears ringing until timeout, no
    `reject_call`/busy signal. The `APP_BASE_URL` placeholder race that triggered this exact path is
    fixed (`770c1f3`); the missing error handling that let it drop calls silently is not. Phase 1
    builds its own call-handling logic directly on this handler.
12. **Agent interrupts the caller — open defect, found on the first real call, 2026-09-01, not
    fixed.** The agent talks too fast and cuts in before the caller finishes a sentence. Scoped as a
    turn-detection/VAD configuration issue on the realtime session (`server_vad` settings — silence
    duration, prefix padding, threshold), not an architecture problem: all 6 exit-test rows still
    passed despite it. Fix is config tuning on the existing session setup, not new code.

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
