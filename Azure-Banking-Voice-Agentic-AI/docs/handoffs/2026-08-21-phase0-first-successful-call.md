# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 0, 2026-08-21 night session

## STOP CONDITIONS — restated verbatim from CLAUDE.md, per its own requirement

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling.
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## Where things stand

**First real answered phone call happened tonight.** All 3 test calls to `+17059100383` connected,
echoed correctly, and DTMF registered on 2 of 3. This followed a chain of same-night bug fixes —
none of this needs re-litigating, it's all in `docs/phase0/findings.md` and the commits below.
`PROJECT_STATE.md` (updated at the end of this session, read it for the authoritative current-state
snapshot — this handoff doc will go stale, that file won't) is the source of truth for what's open.

**R-04's 72h idle-billing window is OPEN**, anchored to `PROVISION_TIME=2026-08-21T22:49:35Z`
(closes ~2026-08-24T22:49:35Z). This value was set **manually**, not by either wizard script's
normal write path — see "why" below. Do not touch it.

## Critical facts the next session needs, cold

1. **`PROVISION_TIME` is a manual value and why.** `01-provision.sh` used to write it on a passing
   `/healthz` check, which turned out to be the wrong gate (container was healthy for over an hour
   while every real call failed — see findings.md "healthz-as-window-gate"). Redesigned to write in
   `02-test-calls.sh` instead, gated on a confirmed `CallConnected` event. But `02-test-calls.sh`
   Stage 4 had a second, independent bug (`--tail 500` against a CLI capped at 300, silently
   swallowed) that meant the gate never got a chance to fire against tonight's real, successful
   calls. Both bugs are now fixed in the script, but `PROVISION_TIME` itself was set by hand this
   session to `2026-08-21T22:49:35Z` — the current Container App revision's actual `createdTime`
   (`az containerapp revision list`), reasoned as the correct anchor because R-04 measures
   idle-vs-active *billing*, which starts when the replica exists, not when someone first dials it.
   Full reasoning: `docs/phase0/findings.md`, "PROVISION_TIME — set manually, not by the normal
   path".

2. **Log Analytics delivers zero rows, through two correctly-configured paths, confirmed after a
   full real-call lifecycle.** Both the native `appLogsConfiguration` (destination: log-analytics,
   correct workspace) and an explicit `az monitor diagnostic-settings create` are wired correctly
   and neither has delivered a single row. This is a confirmed platform-level gap, not a config
   mistake — flagged for real diagnosis before Phase 1 (not fixed, just flagged: a production voice
   agent can't run with no durable logs).

   **[Corrected later the same night — this replaces what this section originally said.]** A
   manually-run `--follow` capture was tried first and found **not durable**: it died on its own
   twice, without being interrupted, each time after ~5-6 minutes of idle. Confirmed as a known,
   unresolved upstream bug ([Azure/azure-cli#28267](https://github.com/Azure/azure-cli/issues/28267))
   plus this project's own empirical evidence (two connections, each ending after exactly 5
   `"No logs since last 60 seconds"` heartbeats). **The durable log-evidence path now is** a
   `launchd` LaunchAgent (`~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) pulling a
   plain (non-`--follow`) `--tail 300` every 15 minutes into
   `docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl` — sidesteps the bug entirely
   since it's a one-shot pull, not a long-lived stream. Check health with `launchctl list | grep
   azbank` (exit `0` = healthy). Both evidence files **will contain duplicate lines** by design
   (the `--follow` file on every restart; the snapshot file across overlapping 15-min pulls at idle
   rates); dedup with `sort -u` or `awk '!seen[$0]++'` before analysing — see
   `docs/phase0/evidence/README.md`. The original `--follow` file has a real, acknowledged gap from
   tonight (Marco was mobile, cafe → home, during part of the window) — it is not continuous and
   should not be read as such; prefer the snapshot file going forward. **Do not commit either file
   periodically** — commit once, at teardown, after the dedup pass. Interim commits would just put
   overlapping snapshots of the same growing file in git history.

3. **`02-test-calls.sh` must NOT be re-run.** Its Stages 1-3 have no skip-if-already-confirmed
   guard — running it unconditionally prompts for 3 fresh real dials before Stage 4's (free,
   read-only) evidence extraction can run at all. Tonight's 3 calls already succeeded; R-02/R-03/RTT
   evidence was extracted **manually** instead (same grep patterns the script now uses, run against
   the committed capture file) specifically to avoid placing unnecessary billable calls against an
   idle-measurement window. This design gap (cheap operation welded to an expensive one, no way to
   separate them) is logged in findings.md, not fixed — candidate fix is an `--extract-only` flag or
   per-call guards, for later.

4. **R-02/R-03 evidence is confirmed, with one open gap.** DTMF confirmed on calls 2 and 3 (6/6
   tones each, clean mid-stream timestamps). **Call 1 registered zero DTMF despite Marco pressing
   keys during it too** — nothing in the logs (duration, frame count, event ordering) explains the
   miss; it's recorded as a genuine open question in findings.md, not resolved either way. An
   earlier draft of that findings.md entry reasoned this away incorrectly (conflated "call 3 wasn't
   scripted for DTMF but worked" with "therefore call 1's miss is explainable") — Marco caught it,
   it's been corrected in place. Don't re-introduce that reasoning.

5. **`03-cost-check-24h.sh` Stage 1 is a human-only step** (a Cost Management Portal check with real
   ingestion lag — nothing to automate). Runs tomorrow, ~24h after `PROVISION_TIME`'s *original*
   healthz-based write tonight, not necessarily 24h after the manually-anchored value — worth
   Marco's own judgment on timing when he runs it, not something to compute automatically.

## Commits this session (chronological, all on `azure-banking-work`)

- `0f8604b` — ECHO_DIR misdirection fix (canonical `docs/echo-app/`, buildx `--platform linux/amd64`,
  manifest gate), README.md, wizard README fix.
- `d855923` — `PROVISION_TIME` re-run guard (superseded later tonight — see below).
- `770c1f3` — `APP_BASE_URL` placeholder-race fix (computed pre-create from `defaultDomain`), update
  branch's secret+revision-suffix fix, diagnostic-settings addition, `PROVISION_TIME` moved out of
  `01-provision.sh` into `02-test-calls.sh`.
- `9e16b81` — reordered `02-test-calls.sh`'s gate to sit after evidence recording, not before.
- `1c67d51` → `9b893eb` (amended) — **the only copy of tonight's R-02/R-03 evidence is committed
  here**: `docs/phase0/evidence/containerapp-logs-2026-08-21T2303Z-3-test-calls.txt`.
- `76938c7` — `--tail 500` → `300` fix (the CLI's real cap), command-failure vs. genuinely-empty
  distinguished, undefined `err()` bug also fixed.
- `b805646` — DTMF prompted on all 3 calls (not just call 2), broken `DTMF_LINES` grep pattern fixed.
- `5159d69` — manual R-02/R-03/RTT findings.md write, evidence README with dedup instructions.
- `a3e98b8` — logged the Stage-1-3/Stage-4 coupling design gap (item 3 above), not fixed.

`docs/PLAN.md` has an uncommitted Observability-tooling section (Azure Monitor OpenTelemetry Distro
vs. LangFuse) — **deliberately left uncommitted**, Marco's instruction: "separate work, commit it on
its own after." Don't sweep it into an unrelated commit.

## Live Azure state (verified, not assumed — re-verify on resume per CLAUDE.md's Resume Discipline)

- Container App `ca-azbank-echo-p0`: exists, healthy, single revision, running and **billing** —
  this is the R-04 measurement subject. Do not restart/update/delete it before the window closes.
- Environment `cae-azure-banking-voice-p0`, ACS `acs-azure-banking-voice`, AOAI
  `aoai-azure-banking-voice-cc`: all present, unchanged.
- Phone number `+17059100383`: owned, `$1.00/mo`, R-09 applies (never released, ever).
- Two Log Analytics workspaces exist in the resource group (`...aixC`, orphaned/unused;
  `...aiCS`, the real one) — the orphan is left in place, not deleted, per earlier-session decision
  not to touch it without asking.

## Suggested skills for the next session

- **`/research`** if `03-cost-check-24h.sh`'s Cost Management API/Portal query needs verifying
  against current Azure docs before running it — this project's standing rule is verify, don't
  assume, and cost-query shapes move.
- **`/code-review`** before Phase 0's exit-criteria gate, once `03`/`04` have run — not needed for
  tonight's fixes, which were reviewed interactively, commit by commit, by Marco throughout.
- **`/handoff`** again at the end of whichever session runs `03-cost-check-24h.sh` and/or
  `04-teardown-and-r08.sh`, before `/clear` — per this project's phase-boundary discipline.

Do not invoke skills proactively beyond what's listed above — this project's `CLAUDE.md` requires
Marco to invoke skills himself; naming them here is informational for the next session, not a queue
of actions to run unprompted.
