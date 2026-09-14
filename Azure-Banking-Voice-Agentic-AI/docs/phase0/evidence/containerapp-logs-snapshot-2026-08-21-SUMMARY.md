# Summary: containerapp-logs-snapshot-2026-08-21.jsonl

Recorded 2026-08-28 when the raw file was untracked from git (see below). This summary is
committed in its place; the raw file stays on local disk only.

## Raw file stats

| | |
|---|---|
| Total lines | 51,981 |
| Size | 6,549,916 bytes (6.2 MB) |
| Date range (real content) | 2026-08-22T01:53:42 → 2026-08-25T01:15:46 |

## Line breakdown

- **51,944 lines** — real log content, one JSON object per line with its own `TimeStamp`. Example:
  ```
  {"TimeStamp": "2026-08-22T01:53:42.08012", "Log": "Connecting to the container 'ca-azbank-echo-p0'..."}
  ```
- **33 lines, contiguous at the tail** (lines 51,949–51,981) — post-teardown polling errors, after
  the Container App was deleted 2026-08-24. Example:
  ```
  ERROR: Not Found({"error":{"code":"ResourceNotFound","message":"The Resource 'Microsoft.App/containerApps/ca-azbank-echo-p0' under resource group 'rg-azure-banking-voice-agentic-ai' was not found. ..."}})
  ```
- **4 lines, scattered mid-file** (not teardown-related — transient network errors during normal
  polling): 3× `ConnectionResetError` at lines 3323, 22652, 49532; 1× DNS resolution failure to
  `login.microsoftonline.com` at line 35337.

51,944 + 33 + 4 = 51,981. Fully accounted for.

## Where the full raw content lives

The complete 51,944-line capture is preserved **permanently** in commit `07faf3b` ("phase0: teardown
complete..."), the only commit that ever touched this file — blob `03fa5a0a`, 6,541,039 bytes
uncompressed / ~805 KB compressed in the pack. As of 2026-08-28 the file is added to `.gitignore` and
`git rm --cached`, so future commits won't track it — this is why: the poller that wrote it is
confirmed dead (see below), so the file cannot grow further, and untracking it loses nothing since
`07faf3b` already holds every line permanently. The file itself remains on this machine's disk,
unmodified, at its original path.

## Open item: LaunchAgent plist absent, unexplained

Not a conclusion, just what was observed 2026-08-28:

- The poller's plist (`~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) is **absent from
  disk** — no such file.
- Its error log (`~/Library/Logs/azbank-phase0-logsnapshot.err`) is also absent.
- `launchctl list | grep -i azbank` returns **no output** — no label registered with `launchd` at
  all.
- `docs/phase0/wizard/04-teardown-and-r08.sh` (lines 414–426) only ever runs `launchctl unload` on
  this plist if it finds the file — it never removes the file itself. So the plist's absence from
  disk is **not explained by any script in this repo**. No crontab entry either (ruled out as an
  alternate mechanism). How or when the file was actually removed is unknown.

Combined with the last real content line's timestamp (2026-08-25T01:15:46Z), the poller has not run
in the three days since — but the mechanism of its stopping remains an open question.
