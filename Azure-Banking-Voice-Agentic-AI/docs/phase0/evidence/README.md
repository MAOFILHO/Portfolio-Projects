# Phase 0 evidence

Raw Container App log captures backing R-02/R-03/RTT findings in `docs/phase0/findings.md`. This
directory exists because `ContainerAppConsoleLogs` in Log Analytics has returned zero rows through
two independently-configured delivery paths (`docs/phase0/findings.md`, "Log delivery — still zero
rows...") — right now, these files and the CLI's own ~300-line streaming buffer are the only places
this phase's call evidence exists at all.

## Files

- `containerapp-logs-<timestamp>-3-test-calls.txt` — a one-shot `az containerapp logs show --tail
  300` snapshot, captured immediately after a call session to beat the buffer scrolling past it.
  Clean, single capture, no duplicates.

- `containerapp-logs-follow-<date>.jsonl` — a long-running `az containerapp logs show --tail 300
  --follow` capture, appended to (`>>`, never truncated) across the R-04 72h observation window.

## The `--follow` file WILL contain duplicate lines — dedup before analysis

Every time the `--follow` capture is (re)started — laptop sleep, dropped connection, terminal
closed and reopened — it first replays its own `--tail 300` window before continuing to stream live.
Appending (`>>`, by design, so a restart never loses what's already captured) means those replayed
lines land in the file a second time. This is deliberate: duplicate lines are harmless and
recoverable; truncating on restart would not be.

**Before analysing this file, deduplicate first:**

```bash
sort -u containerapp-logs-follow-2026-08-21.jsonl > containerapp-logs-follow-2026-08-21.dedup.jsonl
# or, to preserve original order instead of sorting:
awk '!seen[$0]++' containerapp-logs-follow-2026-08-21.jsonl > containerapp-logs-follow-2026-08-21.dedup.jsonl
```

Each line is a self-contained JSON object with its own `TimeStamp`, so exact-line dedup is safe —
two lines are only identical if they really are the same log event replayed, never two distinct
events that happen to collide.

**What a restart can still lose, even with append-and-dedup**: only the most recent 300 lines are
replayed on reconnect. If the app produced more than 300 log lines during a gap the capture wasn't
running for (e.g. a burst of real call activity while a laptop was asleep), whatever's older than
the last 300 lines from that gap is gone — this file protects against the terminal/process dying,
not against a long enough outage that outpaces the replay window.
