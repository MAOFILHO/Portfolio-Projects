# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 0, 2026-08-22 session

## STOP CONDITIONS — restated verbatim from CLAUDE.md, per its own requirement

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.** No teardown
  path may include a number-release/delete call. Added 2026-08-20 (R-09, `docs/PLAN.md`): ACS's
  Canadian geographic-number inventory has been observed to lose entire localities within ~20 minutes
  — unlike every other resource in this project, an equivalent replacement may not be purchasable if
  this number is ever lost. Qualitatively different from the general "no billable resource without
  approval" rule above: this isn't about cost, it's about irreplaceability.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling (below).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## Where things stand

**`PROJECT_STATE.md` is the authoritative current-state snapshot — read it first.** This document is
narrative context and the facts a cold resume needs that aren't self-evident there alone. Full method
and numbers for everything below: `docs/phase0/findings.md`, sections "Free Services blade retirement
and the free-tier suppression question," "R-04 — Container Apps compute cost...," and "R-08 — demo
runs/month, recomputed...".

**R-04 and R-08 are both ANSWERED, ahead of the 72h wall-clock window's close.** The window itself
(`PROVISION_TIME=2026-08-21T22:49:35Z`, anchored manually from the Container App revision's actual
`createdTime` — not written by either wizard script's normal path, don't touch it) closes
~2026-08-24T22:49:35Z. Monday's `04-teardown-and-r08.sh` run is **confirmation + teardown, not
discovery** — the answers already exist:

- **R-04: IDLE.** Measured directly from Azure Monitor telemetry (`Replicas` metric: zero
  scale-to-zero gaps; `RxBytes`/`TxBytes`: every 15-min interval stays under PLAN.md's own stated
  1,000 B/s active threshold except the one expected to carry the prior test call's tail), not from
  Cost Management dollars. **The bigger finding**: Container Apps' standing monthly free compute
  grant (180,000 vCPU-s / 360,000 GiB-s) covers only ~8.3 days (~27.6%) of this app's continuous
  runtime per month — not the whole month, since `min-replicas=1` runs continuously for real inbound
  telephony. Net-of-grant monthly cost at the IDLE rate, Canada Central Retail Prices API rates:
  **$5.72/mo**.
- **A ~$0 Cost Management reading Monday is expected, not a broken check** — it's the free-grant
  effect above, not free-tier suppression (see below) and not (necessarily) lag.
- **R-08: ~79–114 demo runs/month, gate PASSES.** Recomputed from the R-04 figures above (fixed
  $6.72/mo [$5.72 Container Apps + $1 number] + $6/mo eval-budget ceiling, $12.28/mo left for calls),
  not left as PLAN.md's naive $30–160/mo estimate.
- **Free-tier promotion ruled out for Container Apps.** The old direct blade
  (`#view/Microsoft_Azure_GTM/ModernFreeServicesBlade`) is retired (404). Marco performed the live
  check himself via the replacement path (Subscriptions → this subscription → Overview → "Top free
  services by usage" → "View all free services") — Container Apps does not appear anywhere in the
  57-row covered-meter table (structurally absent, not just zero usage). `FREETIER_CLEAN=yes` in
  `.env.phase0` reflects this.
- **PLAN.md's Budget section is confirmed stale, not just estimated-vs-measured.** Its
  $4.29/mo–$14.31/mo Container Apps figures reproduce exactly (to the cent) against **US East**
  Retail Prices API rates run through PLAN.md's own grant-netting method — not Canada Central, where
  every resource in this project actually lives (ADR-001/decision 12). Confirmed not a rate change
  (both regions' rates have been stable since 2022-06-01) — a region mismatch present since the
  original 2026-08-19 scoping commit (`2b577e1`), which itself records no derivation for these two
  figures (unlike ACS's, which cites an exact calculator API URL). **`docs/PLAN.md` was kept out of
  scope this session** (per explicit instruction) — correcting it is a future approved edit. Don't
  re-derive this from scratch; it's fully worked out in `findings.md`.

## Four latent script bugs found and fixed this session (none yet exercised live — Monday is the
first real run of `04-teardown-and-r08.sh` with these fixes in place)

1. **`03-cost-check-24h.sh`: `FREETIER_CLEAN` unbound-variable crash.** `write_env()` only persists
   to `.env.phase0` — it does not set the shell variable in the running process. `FREETIER_CLEAN` was
   read directly a few lines later, in the same run, under `set -u` → crash. Same shape as the earlier
   `DATAZONE_OK` bug in `01-provision.sh`. Fixed by assigning it as a real shell variable at the
   decision point; also turned the old binary clean/covered prompt into a three-state one
   (clean/covered/could-not-verify) so "could not check" no longer silently reads as "covered."
2. **`az costmanagement query` doesn't exist**, in both `03-cost-check-24h.sh` and
   `04-teardown-and-r08.sh`. The installable `costmanagement` CLI extension (v1.0.0) only has
   `export` and `show-operation-result` — this command always silently fell into "no cost data yet,"
   indistinguishable from real ingestion lag but actually a CLI/extension mismatch. Fixed via `az
   rest` directly against the Cost Management Query REST API (confirmed working, live-tested against
   this subscription, no extension needed).
3. **`04-teardown-and-r08.sh`: `ask()` called three times, never defined anywhere in the script.**
   Guaranteed crash ("ask: command not found", fatal under `set -e`) the moment Stage 1 ran — caught
   this session, before Monday's one live run, not during it. Now defined; also used to suggest a
   default fixed-monthly value (from the R-04 telemetry measurement) that Monday's run can accept
   with Enter or override.
4. Stage 1's R-04 verdict logic no longer eyeballs Cost Management dollars — it's computed from
   telemetry (see above), with Cost Management kept as a labeled cross-check only, explicitly noted
   as expected-$0 rather than a pass/fail signal.

All four fixes were validated before being trusted: the verdict/grant-cost Python blocks were
extracted from the actual script file and run against this session's real captured Azure Monitor
data (reproduces IDLE, 0 gaps, 1 expected over-threshold interval); all three new `az rest` calls
were live-tested against the real subscription.

## Operational state to know before running anything Monday

- **The phase0 log-snapshot LaunchAgent is still running** (`~/Library/LaunchAgents/
  com.azbank.phase0.logsnapshot.plist`, local machine config, not in git). `04-teardown-and-r08.sh`'s
  Stage 5 now unloads it *before* deleting the Container App it polls — added this session, wasn't
  there before. If Monday's run is interrupted before reaching that unload step, unload it manually
  (`launchctl unload ~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) once the Container
  App is gone, so it doesn't keep firing against a deleted resource.
- **Both evidence files remain uncommitted, by design** — `docs/phase0/evidence/
  containerapp-logs-follow-2026-08-21.jsonl` and `...-snapshot-2026-08-21.jsonl`. Marco's standing
  instruction: commit once, at teardown, after the dedup pass, never periodically. Script 04's new
  Stage 6 now does both the dedup (`awk '!seen[$0]++'`, safe — each line is a self-contained JSON
  object with its own `TimeStamp`) and the one commit automatically.
- **Do not re-run `02-test-calls.sh`.** No skip-if-already-confirmed guard exists on its Stages 1-3 —
  it would force 3 more billable calls before its free evidence-extraction stage could even run.
- **Stage 3's cost-sanity confirm in `03-cost-check-24h.sh` was answered by the assistant this
  session, not Marco** — flagged in `findings.md` so the record is accurate. Not re-asked; Marco can
  override `COST_SANITY_CHECK` in `.env.phase0` by hand if he disagrees on review.
- Live Azure state (verified this session, not assumed — re-verify on resume per CLAUDE.md's Resume
  Discipline): Container App `ca-azbank-echo-p0` healthy, single revision, running continuously since
  creation (confirmed via the `Replicas` metric — no restarts, no scale-to-zero), still billing — the
  R-04 measurement subject, do not restart/update/delete before Monday. Environment
  `cae-azure-banking-voice-p0`, ACS `acs-azure-banking-voice`, AOAI `aoai-azure-banking-voice-cc`:
  unchanged. Phone number `+17059100383`: owned, $1.00/mo, R-09 (never released). Two Log Analytics
  workspaces (`...aiCS` real/linked, `...aixC` orphan, left in place) — still zero rows delivered,
  still an open item (`PROJECT_STATE.md` open item 1), unrelated to this session's work.

## Commits this session (chronological, all on `azure-banking-work`)

`10b26fb` three-state free-tier check, `az rest` cost queries, first R-04 telemetry measurement ·
`5b351b8` script 04's R-04 telemetry verdict + `az rest` fix + `ask()` crash fix + R-08 recompute ·
`51e9ddc` US-East-vs-Canada-Central rate discrepancy settled, `PROJECT_STATE.md` updated.

`docs/PLAN.md` has an uncommitted, pre-existing modification from before this session (not touched
here, kept out of scope throughout per explicit instruction) — don't sweep it into an unrelated
commit; it's a separate piece of work.

## Suggested skills for the next session

- **`/handoff`** again at the end of whichever session actually runs `04-teardown-and-r08.sh` (Monday
  or later, once ~72h have genuinely passed) — before `/clear`, per this project's phase-boundary
  discipline.
- **`/code-review`** before Phase 0's exit-criteria gate is declared closed, once script 4 has
  actually run — the three bug fixes above were reviewed interactively this session, not yet via a
  formal review pass.
- **`/research`** only if something about the Cost Management REST API or Container Apps metrics
  shape needs re-verifying against current Azure docs before trusting a number — this project's
  standing rule is verify, don't assume from memory.

Do not invoke skills proactively beyond what's listed above — this project's `CLAUDE.md` requires
Marco to invoke skills himself; naming them here is informational for the next session, not a queue
of actions to run unprompted.
