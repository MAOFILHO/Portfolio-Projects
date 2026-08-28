# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 1 log-path investigation, 2026-08-27

**Canonical path**: `/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`,
branch `azure-banking-work`. Verify with `git branch --show-current` / `git worktree list` before
doing anything — don't trust this line to have stayed current (`CLAUDE.md`'s own instruction).

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

## Scope note

This session's conclusions land in this one new file only. `docs/PLAN.md`, `PROJECT_STATE.md`, and
`docs/phase0/findings.md` were **not modified** — Marco decides what propagates into those files and
when. Nothing here should be read as those files having been updated; where this doc's findings
contradict something those files currently say, that's flagged explicitly below, not silently fixed.

All investigation was **read-only, live `az` queries** against the still-existing Log Analytics
workspaces (the compute — Container App, Container Apps environment — was already torn down as of
the 2026-08-24 closeout; workspaces and their retained data are not affected by that teardown). No
resource was created, deleted, or modified. No calls were placed.

---

## Root cause: table-name mismatch, not workspace mismatch

The 2026-08-24 closeout handoff flagged an **untested** hypothesis: that the diagnostic setting might
target one Log Analytics workspace while every Phase 0 query checked the other
(`workspace-rgazurebankingvoiceagenticaixC`, orphan, customerId `e42c142b-ab5f-42ed-8b54-8834c2e23895`
vs. `workspace-rgazurebankingvoiceagenticaiCS`, the linked one, customerId
`2a41795f-cd94-48bd-af3d-f669edf84c61`).

**That hypothesis was tested this session, directly, and ruled out.** Live `az monitor log-analytics
query` against **both** workspace GUIDs for the Phase 0 window (2026-08-19 → 2026-08-26):

- `e42c142b-...` (aixC, orphan): **zero rows**, every table, `Usage` included.
- `2a41795f-...` (aiCS, the documented "real" one): **non-zero** — `ContainerAppConsoleLogs_CL`:
  2743 rows, `ContainerAppSystemLogs_CL`: 71 rows, `Usage`: 67 rows.

So the workspace that Phase 0's diagnostic-setting config and `appLogsConfiguration` targeted really
was the one that received data. **The actual root cause of the "zero rows" finding is a table-name
mismatch**: every Phase 0 query checked the unsuffixed table names (`ContainerAppConsoleLogs`,
`ContainerAppSystemLogs`) — confirmed directly, `ContainerAppConsoleLogs | count` on `aiCS` returns
`0` — while the real data landed in **`_CL`-suffixed custom-log tables**
(`ContainerAppConsoleLogs_CL`, `ContainerAppSystemLogs_CL`). A 3-row sample of `ContainerAppConsoleLogs_CL`
confirms it's genuinely this project's data: `ContainerAppName_s: "ca-azbank-echo-p0"`, boot lines
including `PHASE0_LOG_DTMF_VALUES='<unset>' -> raw DTMF tone values will NOT be logged this run`,
timestamped `2026-08-21T21:56:44Z`. Row shape (`SourceSystem: "RestAPI"`, empty `_ResourceId`/`MG`)
is the signature of custom-log-table ingestion — i.e. the CAE's native `appLogsConfiguration` path
delivered successfully, just into a differently-named table than any Phase 0 query ever checked.

**This supersedes the 2026-08-24 closeout handoff's framing** ("check the two-workspace hypothesis
before any deeper investigation") — that framing is now stale; the workspace was never wrong.

---

## RESOLVED — diagnostic-setting delivery, 2026-08-27 follow-up

**Verdict (b): `azbank-p0-console-logs` never delivered.** It was created successfully — ARM write
`Microsoft.Insights/diagnosticSettings/write`, `2026-08-21T22:49:51Z`, operationId
`b3ca2af3-eb5d-41a1-80a4-11e287951451`, `200 OK` — against the correct workspace (customerId
`2a41795f-cd94-48bd-af3d-f669edf84c61`, confirmed live). But the recovered ARM request body contains
no `logAnalyticsDestinationType` key, matching `01-provision.sh:1097-1102`, which omits
`--export-to-resource-specific`:

```bash
az monitor diagnostic-settings create \
  --name "azbank-p0-console-logs" \
  --resource "$CAE_ID" \
  --workspace "$LOGS_WORKSPACE_RESOURCE_ID" \
  --logs '[{"category":"ContainerAppConsoleLogs","enabled":true},{"category":"ContainerAppSystemLogs","enabled":true}]' \
  --output none
```

`az monitor diagnostic-settings create --help` states the flag's own default plainly: without it,
export goes to "the default dynamic schema table called `AzureDiagnostics`" — not to a
resource-specific unsuffixed table, and not to any `_CL` table (`_CL` is the native
`appLogsConfiguration` path's mechanism, unrelated to Diagnostic Settings). So the setting's default
destination was `AzureDiagnostics`.

**Evidence the destination received nothing, strongest first:**

1. `az monitor log-analytics workspace table show ... -n ContainerAppConsoleLogs` reports the table
   **present in the workspace's table catalog** (schema provisioned, `retentionInDays: 30`,
   `provisioningState: Succeeded`) but with **zero ingestion** — a direct measurement of the table's
   own state, not an inference from a query result.
2. Corroborating: a bare KQL `| count` against `AzureDiagnostics` and against both unsuffixed
   category tables (`ContainerAppConsoleLogs`, `ContainerAppSystemLogs`) all return
   `PathNotFoundError` (never-materialized) rather than `0` — consistent with zero rows ever
   ingested, but this is inference from an error string/symptom, not a direct measurement the way (1)
   is.

**Consequence**: all Phase 0 console/system data (2743+71 rows) came exclusively from the native
`appLogsConfiguration` → `_CL` path. The "both delivery paths verified correct" claim in `findings.md`
and `PROJECT_STATE.md` is disproven, not just unverified. **Those files are UNEDITED and still
contain it** — flagged here as a pending correction for Marco to approve, not applied:

- `docs/phase0/findings.md:2148-2149,2157`: *"Confirmed this is not a configuration mistake on this
  project's end — both the native path and the explicit fallback are correctly wired"* ... *"Both
  delivery paths are configured exactly as documented and neither has delivered a single row"* — the
  second half ("neither has delivered") was and remains correct; the first half ("correctly wired" /
  "configured exactly as documented") is the disproven part — the diagnostic setting was missing
  `--export-to-resource-specific`, which is not what the two category names alone imply.
- `PROJECT_STATE.md:61-63`: *"Both the native `appLogsConfiguration` path and an explicit `az monitor
  diagnostic-settings` resource are correctly configured (verified: right workspace, right categories
  enabled) and neither has delivered a single row"* — same disproven claim: "correctly configured" is
  not supported once destination-table mode is accounted for.

**Method note, carry forward**: a bare `count` on a never-materialized table throws
`PathNotFoundError`; a `union isfuzzy=true` query over the same table degrades to `0` instead. Last
session's "`ContainerAppConsoleLogs | count` = 0" and this session's `PathNotFoundError` on the same
table are the same underlying fact (zero rows), surfaced differently by query syntax — not a
contradiction.

**Consequence for Phase 1 planning**: the held-back `docs/PLAN.md` "Observability tooling" section
(Azure Monitor OpenTelemetry Distro → Application Insights, recommended over LangFuse) stays held
back, unchanged from the 2026-08-24 handoff's position — but for a sharper reason now. That section's
recommendation implicitly assumes the Log Analytics ingestion pipeline in general is sound. It is —
but only through the native `appLogsConfiguration` path, which is a different mechanism than what a
Diagnostic Settings resource (the pattern Application Insights integration would likely also lean on)
provides. That question is no longer open: the diagnostic-setting path is now confirmed non-functional
as configured (see "RESOLVED" above). Any Phase 6 observability design that leans on a Diagnostic
Settings resource must include `--export-to-resource-specific` (or otherwise account for
`AzureDiagnostics`-mode delivery) and must be validated by querying for rows after a known emission,
not by confirming the setting exists.

---

## R-03 status: narrowed, not resolved

What this session's export adds: **Call 1 was a normal-shaped call**, not a truncated or erroring one.
Measured directly (not derived): `WS open` 22:51:13.426 → `WS closed` 22:51:37.860 = **24.434s**.
Audio was echoing throughout (steady `frame N echoed` lines at ~1/sec for the full duration). It
terminated the same way Calls 2 and 3 did — `MediaStreamingStopped` → app's own `WS closed
... dtmf_tones=0` → `CallDisconnected`, in that order, no exception, no error line, no timeout
indicator anywhere in the window. Call 1's runtime (24.434s) exceeded Call 2's first-digit offset
(10.226s) by ~2.4×, and fell short of Call 3's first-digit offset (33.944s) — so on elapsed time alone
it's not the case that Call 1 ended too early to plausibly have received a digit near where Call 2 got
its first one.

**Both branches remain open.** This app-side data is still structurally downstream of the fork where
ACS decodes DTMF tones — a `dtmf_tones=0` counter at WS close cannot distinguish "no tone was ever
sent" from "ACS decoded a tone and chose not to forward it." Nothing recovered this session changes
that structural limitation; it only rules out "the call was too short/broken to have received one,"
which was never actually one of the two branches in contention.

**Resolution path, unchanged from the standing Phase 1 entry criterion**: ACS-side call diagnostics
for Call 1's specific correlationId, **`2d5e7f5c-39ae-46ef-b3d8-feadf93ec651`**, showing whether ACS
itself detected/decoded any DTMF tone during that call's media stream, independent of what it chose
to forward to the app. That data source does not exist in either Log Analytics workspace (confirmed:
only `ContainerAppConsoleLogs_CL`, `ContainerAppSystemLogs_CL`, `Usage` have rows for this window,
both app-side) — it would have to come from ACS itself.

**On what was instructed vs. what's recorded**: `docs/phase0/wizard/02-test-calls.sh` instructs DTMF
pressing **individually for all three calls** (Stage 1/2/3 each carry their own instruction block,
same generic `"e.g. 1  2  3"` example each time) — Call 1 is not the unprompted one. Separately, three
committed documents (`findings.md`, `PROJECT_STATE.md`, the 2026-08-21 handoff) state as fact that
Marco pressed keys on Call 1. That statement is a **first-person operator account**, not a
system-captured artifact — it isn't the wizard script's `confirm()` gate result (not written to any
tracked file) and it isn't a digit-value log. **No digit values exist for any of the three calls**:
`PHASE0_LOG_DTMF_VALUES` was confirmed `<unset>` on both replica boot banners this session (the only
two boots in the captured window), meaning raw tone-value logging was off for the entire evidence
set, not just Call 1.

---

## Method notes for whoever reads these rows next

The raw export lives at `docs/phase0/evidence/loganalytics-export/` (`console.jsonl`, `system.jsonl`
— gitignored, not committed; see Open Items below). Two things that will bite anyone re-analyzing it:

1. **Sort by the embedded `HH:MM:SS,mmm` clock inside `Log_s`, not by `TimeGenerated`.**
   `TimeGenerated` is Log Analytics' ingestion timestamp — it's batched and does not preserve true
   event order. Concretely: DTMF digits #5 and #6 in Call 2 share one identical `TimeGenerated` value
   but their embedded `t=` values are inverted in ingestion order (#6 printed before #5). The embedded
   per-line clock is the actual causal write-time from the app and is the only reliable ordering axis
   found this session — even it isn't monotonic *across* different log statement types within the same
   ingestion batch (e.g. a `CallConnected` callback line can embed a later clock value than a
   `MediaStreamingStarted` line that prints after it), so re-sort explicitly; don't trust either raw
   file order or `TimeGenerated` order.
2. **`t=` (elapsed seconds since stream start) appears only on DTMF digit-arrival lines** — nowhere
   else in either table. Frame-echo lines carry a `frame_count` but no `t=`. Don't interpolate a `t=`
   for untimed lines.
3. **Media cadence**: ~49.98 frames/sec (49.9756, from n=12 paired `(frame_count, t=)` samples off the
   DTMF lines across Calls 2 and 3 — Call 1 contributed none, having no DTMF lines of its own),
   consistent with 20ms PCM audio frames. Cross-validated against each call's own measured
   `WS open`→`WS closed` wall-clock duration; agreement within 0.06s on all three calls.

---

## Open items — listed as open, not investigated further this session

1. **`launchd` log-snapshot agent** (`com.azbank.phase0.logsnapshot.plist`) appended 33 new lines to
   `docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl` after this session started —
   all `ERROR: ... Microsoft.App/containerApps/ca-azbank-echo-p0 ... was not found`, last entry
   timestamped `2026-08-25T01:15Z`. **This session did not verify whether the agent is currently
   running** — only that it had appended those lines by the time `git status` was checked. Do not
   assert it is or isn't running now; check `launchctl list | grep azbank` (or equivalent) before
   making that claim.
2. **Event Grid retry pattern, uninvestigated.** correlationId `977a7c0f-e073-4eb0-82a2-87620d53ec13`
   re-fires `IncomingCall` repeatedly at expanding intervals (10s → 30min → hours) across **both**
   replicas (`vm6ylxz` and `kkp0zzb`), spanning roughly 21 hours (2026-08-21T21:59Z →
   2026-08-22T20:46Z) — the shape of an unacknowledged webhook delivery under Event Grid's exponential
   backoff. Not the three real test calls (those have their own distinct correlationIds). Not
   investigated beyond noticing the pattern this session.
3. **The 52k-line committed `.jsonl` snapshot** — `docs/phase0/evidence/containerapp-logs-snapshot-2026-08-21.jsonl`,
   already flagged in the 2026-08-24 closeout handoff as an open sizing question. Still open, still
   undecided. The new `docs/phase0/evidence/loganalytics-export/` directory created this session is
   **gitignored, not committed** specifically so it doesn't preempt that decision either way.

---

## Redactions

None needed — no API keys, tokens, or credentials appear in this document. Correlation IDs, resource
names, and the phone number's existence are project infrastructure identifiers, not personal data.
The Azure SDK request/response header dumps referenced (but not reproduced in full here) already carry
`'REDACTED'` placeholders at source, from the app's own logging.
