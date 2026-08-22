# Phase 0 evidence

Raw Container App log captures backing R-02/R-03/RTT findings in `docs/phase0/findings.md`. This
directory exists because `ContainerAppConsoleLogs` in Log Analytics has returned zero rows through
two independently-configured delivery paths (`docs/phase0/findings.md`, "Log delivery — still zero
rows...") — these files are the only durable evidence of this phase's call/container activity.

## Files

- `containerapp-logs-<timestamp>-3-test-calls.txt` — a one-shot `az containerapp logs show --tail
  300` snapshot, captured immediately after the first successful call session. Clean, single
  capture, no duplicates. This is the file R-02/R-03 findings are drawn from.

- `containerapp-logs-follow-2026-08-21.jsonl` — an early attempt at continuous coverage via
  `az containerapp logs show --tail 300 --follow`, run manually in a terminal. **Superseded — see
  below.** Kept as-is for what it did capture; do not treat it as gap-free.

- `containerapp-logs-snapshot-2026-08-21.jsonl` — the current, reliable evidence path: a `launchd`
  LaunchAgent runs a plain (non-`--follow`) `--tail 300` pull every 15 minutes and appends it here.

**These two files are not interchangeable — use each for what it's actually good for.** The
committed 3-test-calls capture is the source for call evidence: it's a single clean pull taken
immediately after all 3 calls, so all 3 `CallConnected` events are in it. The snapshot file is the
source for the idle window: continuous coverage from ~22:33 onward, but its `--tail 300` buffer means
anything older than the buffer at the LaunchAgent's *first* pull is gone — confirmed 2026-08-22: call
1's `CallConnected` (22:51:13) scrolled out of the buffer before the first pull and is **not** in the
snapshot file, even though it's in the committed capture. Teardown analysis (R-04 verdict) needs
both files, not just one. Full writeup: `docs/phase0/findings.md`, "Overnight idle window...".

Also note: the LaunchAgent's overnight cadence is **non-uniform**, not a strict 15-minute clock —
confirmed 2026-08-22 it fired roughly every 50 minutes during sleep (`launchd` coalesces
`StartInterval` jobs across sleep). ~10 pulls over ~8h25m overnight vs. the ~34 a strict interval
would give awake. Not a failure and the idle-rate margin still holds; don't read a wide gap between
consecutive snapshot timestamps as a container/log outage. Same writeup in `docs/phase0/findings.md`
covers this and also answers the "not yet confirmed" sleep/wake question below.

## `--follow` is not durable — use the scheduled snapshot instead

`az containerapp logs show --follow` died on its own twice, without being interrupted, both times
after ~5-6 minutes of idle (no real container log activity) — confirmed via a matching, unresolved
upstream bug, [Azure/azure-cli#28267](https://github.com/Azure/azure-cli/issues/28267), and via this
project's own capture file (two connections, each ending after exactly 5
`"No logs since last 60 seconds"` heartbeats, 60s apart, then silent death). Full writeup:
`docs/phase0/findings.md`, "`--follow` is not durable...".

**Current setup**: `~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`, a macOS LaunchAgent
running `az containerapp logs show --tail 300` (no `--follow` — sidesteps the bug entirely, since
it's a one-shot pull, not a long-lived stream that can idle out) every 15 minutes, appended to
`containerapp-logs-snapshot-2026-08-21.jsonl`. 15 minutes is generous margin over the observed idle
rate (~11 lines/hour) while tight enough to absorb an unexpected burst without overflowing the
300-line buffer.

- **Check it's healthy**: `launchctl list | grep azbank` — exit status `0` is healthy; anything else,
  or the label missing entirely, means investigate `~/Library/Logs/azbank-phase0-logsnapshot.err`
  (moved here from `/tmp` deliberately — `/tmp` is cleared on reboot, so a failure at hour 40
  followed by a restart would otherwise take the diagnosis with it).
- **Confirmed 2026-08-22**: the LaunchAgent survives a real sleep/wake cycle and keeps firing —
  ~10 pulls over an overnight ~8h25m stretch, roughly every 50 minutes rather than every 15
  (`launchd` coalesces `StartInterval` jobs across sleep; this is expected behavior, not a defect).
  The idle-rate margin still holds at that spacing. Don't read a wide gap between consecutive
  snapshot-file timestamps as an outage — it's coalescing. Full writeup: `docs/phase0/findings.md`,
  "Overnight idle window...".
- **Stop it** (e.g. at teardown, script 4): `launchctl unload
  ~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`.

## The `--follow` file (and any future re-attempt at `--follow`) WILL contain duplicates

If `--follow` is ever used again despite the above, know that every (re)start replays its own
`--tail 300` window before streaming live, so appending (`>>`, by design — never truncate, a restart
must not lose what's already captured) means those replayed lines land a second time. Dedup before
analysis:

```bash
sort -u containerapp-logs-follow-2026-08-21.jsonl > containerapp-logs-follow-2026-08-21.dedup.jsonl
# or, to preserve original order instead of sorting:
awk '!seen[$0]++' containerapp-logs-follow-2026-08-21.jsonl > containerapp-logs-follow-2026-08-21.dedup.jsonl
```

Each line is a self-contained JSON object with its own `TimeStamp`, so exact-line dedup is safe.

The scheduled snapshot file does **not** need this — each 15-minute pull's `--tail 300` window
naturally overlaps the previous one at idle rates, so it also contains duplicate lines across
consecutive runs, by the same mechanism. Same dedup commands apply to it before analysis.
