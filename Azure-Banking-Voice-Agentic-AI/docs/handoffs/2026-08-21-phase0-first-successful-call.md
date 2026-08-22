# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 0, 2026-08-21 night session (final)

This supersedes the earlier same-night version of this file — that one accumulated corrections
in place as bugs were found; this is the clean final state, same filename, same commit history.

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
echoed correctly, DTMF registered on 2 of 3. That triggered a chain of same-night bug fixes and one
infrastructure change (a local log-capture LaunchAgent) — none of it needs re-litigating, it's all
in `docs/phase0/findings.md` and the commit list below. **`PROJECT_STATE.md` is the authoritative
current-state snapshot** — read it first; this document exists for narrative context and the facts
below that a cold resume needs but that aren't self-evident from `PROJECT_STATE.md` alone.

**R-04's 72h idle-billing window is OPEN**, anchored to `PROVISION_TIME=2026-08-21T22:49:35Z`
(closes ~2026-08-24T22:49:35Z). **This value is manual**, not written by either wizard script's
normal path — reasoning: `docs/phase0/findings.md`, "PROVISION_TIME — set manually...". Do not
touch it; do not re-run `02-test-calls.sh` (no per-call skip guard exists there — it would force 3
more billable calls before its free evidence-extraction stage could even run).

## Critical facts the next session needs, cold

1. **Log Analytics still delivers zero rows** through two independently-correct delivery paths,
   confirmed after a full real-call lifecycle — a genuine platform gap, not a config mistake,
   flagged for real diagnosis before Phase 1 (not fixed, just flagged).

2. **The only durable log-evidence mechanism is a local `launchd` LaunchAgent**, not Log Analytics
   and not a `--follow` stream:
   - `~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist` (local machine config, not in git)
     runs a plain `az containerapp logs show --tail 300` (no `--follow`) every 15 minutes, appending
     to `docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl`.
   - `--follow` was tried first and found **not durable** — a known, unresolved upstream bug
     ([Azure/azure-cli#28267](https://github.com/Azure/azure-cli/issues/28267)) plus this project's
     own empirical evidence (two connections, each dying after exactly 5 idle heartbeats, ~5-6min).
     Its capture file (`containerapp-logs-follow-2026-08-21.jsonl`) is kept but has a real,
     acknowledged gap (Marco was mobile, cafe → home) — not continuous, prefer the snapshot file.
   - **Periodic firing confirmed empirically**, 2026-08-21T22:33:30 local: evidence file mtime
     advanced exactly at T0+900s with no manual action (`docs/phase0/findings.md`, "LaunchAgent —
     StartInterval scare..."). A scare earlier the same night (`launchctl list` showing no
     `StartInterval`/`RunAtLoad` key) turned out to be a red herring — that command **never** echoes
     those keys for any job, confirmed against an unrelated known-scheduled agent
     (`com.google.GoogleUpdater.wake`, identical dump shape). **Don't use `launchctl list <label>`'s
     output to judge whether this is scheduled correctly — it can't tell you that, ever.** Check
     health the only reliable way: does the evidence file's mtime advance across a real 15-min
     interval boundary. `LastExitStatus 0` in `launchctl list` is necessary but not sufficient (it's
     `0` whether the job ran once at load and died, or is firing correctly). Failures:
     `~/Library/Logs/azbank-phase0-logsnapshot.err` (deliberately not `/tmp`, which clears on
     reboot).
   - **NOT yet confirmed to survive a real sleep/wake cycle** — verified only on a machine that
     stayed awake throughout (tonight's interval-firing confirmation above was also on an awake
     machine). Marco was checking this on getting home tonight (commute gap check).
     **Before assuming this is solved, check `containerapp-logs-snapshot-2026-08-21.jsonl`'s
     timestamps for a gap matching any period the laptop actually slept.** If found, log retention
     is still an open problem, not a handled one — don't proceed as if it's fixed without checking.
   - Whether the LaunchAgent's earlier "flat 604 lines" period (before tonight's `bootout`/
     `bootstrap` re-register) reflected a real scheduling gap or a job that had been firing correctly
     all along is **unresolved and unresolvable after the fact** — no evidence either way survives.
     Only the forward-looking fact is settled: it fires on schedule now.
   - Both evidence files contain duplicate lines by design (dedup: `sort -u` or `awk
     '!seen[$0]++'`, details in `docs/phase0/evidence/README.md`). **Neither is committed yet** —
     Marco's explicit instruction: commit once, at teardown (script 4), after the dedup pass, not
     periodically.

3. **R-02/R-03 evidence is confirmed, with one open gap.** DTMF confirmed on calls 2 and 3 (6/6
   tones each). **Call 1 registered zero DTMF despite Marco pressing keys during it too** — nothing
   in the logs explains the miss; recorded as a genuine open question, not resolved either way (an
   earlier draft reasoned it away incorrectly; Marco caught it, it's corrected in
   `docs/phase0/findings.md`). `02-test-calls.sh` now prompts for DTMF on all 3 calls going forward
   (was only call 2) — irrelevant to tonight's already-collected evidence, matters for any future
   test-call session.

4. **`03-cost-check-24h.sh` Stage 1 is human-only** (Cost Management Portal Free Services check,
   real ingestion lag, no API exists for it). Runs tomorrow.

## Commits this session (chronological, all on `azure-banking-work`)

`0f8604b` ECHO_DIR fix · `d855923` PROVISION_TIME guard (superseded) · `770c1f3` APP_BASE_URL
placeholder-race fix + PROVISION_TIME moved to `02-test-calls.sh` · `9e16b81` gate reordered after
evidence recording · `1c67d51`→`9b893eb` (amended) **R-02/R-03 evidence capture committed** ·
`76938c7` `--tail 500`→`300` fix, undefined `err()` fixed · `b805646` DTMF prompt on all 3 calls,
`DTMF_LINES` grep fixed · `5159d69` manual R-02/R-03/RTT extraction, evidence README · `a3e98b8`
logged the Stage-1-3/Stage-4 billable-coupling design gap (not fixed) · `2f86750` first handoff
committed · `fd5f85d` `PROJECT_STATE.md` rewritten for current state · `13376c3`→`bc9a3d2` (amended
— evidence files pulled back out per Marco's standing instruction, self-corrected) `--follow`
retired, `launchd` snapshot introduced · `952dc75` LaunchAgent stderr path fixed, sleep/wake caveat
added everywhere.

`docs/PLAN.md` has an uncommitted Observability-tooling section — **deliberately left uncommitted**,
Marco's instruction: "separate work, commit it on its own after." Don't sweep it into an unrelated
commit.

## Live Azure state (verified, not assumed — re-verify on resume per CLAUDE.md's Resume Discipline)

- Container App `ca-azbank-echo-p0`: healthy, single revision, running and **billing** — the R-04
  measurement subject. Do not restart/update/delete before the window closes.
- Environment `cae-azure-banking-voice-p0`, ACS `acs-azure-banking-voice`, AOAI
  `aoai-azure-banking-voice-cc`: unchanged.
- Phone number `+17059100383`: owned, $1.00/mo, R-09 (never released).
- Two Log Analytics workspaces (`...aiCS` real/linked, `...aixC` orphan, left in place).

## Suggested skills for the next session

- **`/research`** if `03-cost-check-24h.sh`'s Cost Management API/Portal query needs verifying
  against current Azure docs before running it — this project's standing rule is verify, don't
  assume.
- **`/code-review`** before Phase 0's exit-criteria gate, once scripts 3 and 4 have run — not needed
  for tonight's fixes, reviewed interactively, commit by commit, by Marco throughout.
- **`/handoff`** again at the end of whichever session runs `03-cost-check-24h.sh` and/or
  `04-teardown-and-r08.sh`, before `/clear` — per this project's phase-boundary discipline.

Do not invoke skills proactively beyond what's listed above — this project's `CLAUDE.md` requires
Marco to invoke skills himself; naming them here is informational for the next session, not a queue
of actions to run unprompted.
