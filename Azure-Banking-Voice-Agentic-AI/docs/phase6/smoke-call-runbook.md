# D16 smoke call — runbook

**Not the acceptance call.** `docs/phase6/exit-criteria.md` D16 is explicit: this is a synthetic
proof of delivery, nobody is grading it, and it is not a rerun of Phase 5's acceptance call (D1
rejected riding that call for Phase 6's purposes). It proves the trace in D5's shape reaches
`workspace-rgazurebankingvoiceagenticai1D` at all. It proves nothing about whether a *real* call
produces that tree correctly — that is a separate, later question.

**Prerequisite**: `infra/provision-app-insights.sh` has been run (by Marco, after review) and its
last line printed successfully. Until then there is no workspace row to find, and this call would
just be an ordinary test call against Phase 5's already-working system.

**This document cannot make the call or run the query for you.** Both need a human — Marco, on the
phone, and Marco, in the portal or the CLI — which is exactly why this is a runbook and not a script.

---

## 1. What to say on the call

Dial **`+17059100383`**. Roughly two minutes. Two elements only, mirroring the shape D5/D13 actually
trace (a pre-auth refusal and an authenticated intent), not a script that tries to exercise
everything:

| step | what you do | what should happen | what this exercises |
|---|---|---|---|
| 1 | After the greeting, before entering any PIN, ask for your balance | The agent refuses and asks for the PIN instead — no balance is spoken, no tool call reaches the core-banking client | The pre-auth refusal (B1's gate), traced as a `tool_call` span with `gate_decision` recording the refusal, or a call-level `end_reason`/`closed_path` if the call ends here instead — either is fine, this step's only requirement is that no balance is ever spoken |
| 2 | Key **`1234`** on the keypad (the demo PIN — `mock-core-banking/azbank_core_banking/db.py`'s `DEMO_PIN`, public in source, not a secret this call is protecting) | The PIN auto-submits on the fourth digit (no `#` needed) and the agent confirms you're authenticated | The `call` span's `auth_state` attribute moves to `Authenticated`; nothing about the PIN itself appears anywhere it's traced (B2) |
| 3 | Ask for your account balance | The agent states a balance | One authenticated intent — a `tool_call` span (`tool_name` = the balance tool, `outcome_class` on success is not one of the four failure classes, so it may simply be absent) and a `core_banking` child span for the HTTP call it makes |
| 4 | Say goodbye / hang up | The call ends normally | The `call` span closes; `turn_count`/`duration_ms` get their final values |

**If anything derails** (a boot defect, a misheard PIN, a dropped call) — Phase 5's acceptance day
found two real defects exactly this way (`docs/phase5/exit-check.md` item 24). That is this call
doing its job, not this call failing. Redeploy the fix and call again; there is no grading to protect.

**Do not** try to exercise all four intents or the closed-path cases in this call — that is the
acceptance call's job (already done, Phase 5), not this one's. D16 asks for one of each, not
everything.

---

## 2. What to note during the call

Right after hanging up, capture from the container logs (`az containerapp logs show --name
ca-azbank-echo-p0 --resource-group rg-azure-banking-voice-agentic-ai --type console --tail 100`):

- The **correlation id** for this call (one of the 6-of-48 log lines that carries it,
  `PROJECT_STATE.md`'s D14 note) — this is the thread that ties the container log to the trace, and
  it is the value to search for in the workspace query below.
- Roughly what time the call happened (UTC), to scope the query's time window.

---

## 3. What to query afterward, in `...1D`

**Query the workspace, don't assume the exporter's 200 OK meant delivery** — the same rule
`CLAUDE.md` states for diagnostic settings applies here twice over (`docs/phase6/exit-criteria.md`
D16's own header note): once for the Application Insights resource's ARM create, once for the
exporter's own reported success.

Azure Portal → Log Analytics workspaces → `workspace-rgazurebankingvoiceagenticai1D` → Logs, or
`az monitor log-analytics query --workspace <customerId> --analytics-query "..."` (the workspace's
`customerId`, `bf520f2c-e2bc-4488-8965-9317a7922c74` per `PROJECT_STATE.md`, not its resource name,
is what that CLI verb wants).

**Which table an OpenTelemetry span or metric lands in is not asserted here as a settled fact** —
workspace-based Application Insights routes spans across `AppDependencies`/`AppRequests`/`AppTraces`
depending on span kind, and this project has never queried it live before. Rather than guess one
table and risk a false "nothing arrived," start broad:

```kusto
union AppDependencies, AppRequests, AppTraces, AppExceptions, AppMetrics, AppEvents
| where TimeGenerated > ago(1h)
| where * has "<the correlation id you captured above>"
| order by TimeGenerated asc
```

(Kusto's `has` across a `union` scans every column that's actually a string on each table; on a
table where the correlation id isn't a real column this just contributes no rows, which is fine.)

**What confirms delivery**: at least one row, containing the correlation id, whose timestamp lines
up with the call. From there:

- Find the `call` span specifically (`Name == "call"` or wherever the span name lands depending on
  which table it's in) and check its attributes/`Properties`/custom dimensions match D15's table
  exactly: `correlation_id, connection_id, auth_state, end_reason, turn_count, duration_ms,
  closed_path_taken, closed_path_cause` — and nothing else. This is the live counterpart to the CI
  allowlist-exactness test (issue #61); the CI test proves the code does this against an in-memory
  exporter, this is the first time it's checked against what actually landed in Azure.
- Search the same rows (not just the `call` span's attributes — every column, every table this
  call's correlation id touched) for the literal PIN (`1234`) and, if you can determine it, the
  calling number. **This must come back with zero matches.** If it doesn't, stop — do not proceed to
  wiring anything else, and treat it as a B2 breach requiring immediate investigation, per
  `docs/PLAN.md`'s standing severity for any B2 finding.
- Check `AppMetrics` (or wherever `b4.daily_minutes_used` / `b5.turn_latency_seconds` actually land)
  for a data point from this call's time window.

**Record the actual result** — which table(s) the spans landed in, what the query returned, whether
the attribute set matched D15 exactly, whether the PIN/number scan came back clean — the way
`docs/phase5/exit-check.md` recorded its acceptance-call evidence. That write-up is what turns
criterion 6/7/8/12 in `docs/phase6/exit-criteria.md`'s proposed exit table from "code exists" into
"delivery proven," which is the whole point of D16 existing separately from a code review.

---

## 4. What this runbook does not cover

- Assigning the IAM role for Entra-authenticated ingestion (D10) — still an open `/research`
  question. This call's telemetry goes through the connection-string fallback
  (`AZURE_MONITOR_AUTH=connection_string`, wired by `infra/provision-app-insights.sh`), not identity.
- Re-running or substituting for Phase 5's acceptance call.
- Any teardown step. This call adds no new resource; it exercises one already provisioned.
