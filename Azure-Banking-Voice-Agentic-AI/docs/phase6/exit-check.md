# Phase 6 — exit check, against `docs/phase6/exit-criteria.md`

**Status, 2026-09-15: all 14 criteria met.** Every entry condition (`docs/phase6/exit-criteria.md`'s
own table) closed the same day — B2 widening signed off and implemented (issue #65), and the
25-commit human review (`e42c063..HEAD`) done in full. Nothing in this table is a projection: the
CI-provable criteria are read from a passing suite run today, and the four that need a live call are
read from `docs/phase6/d16-smoke-call-result.md`, not from a verbal report.

| | |
|---|---|
| Commits | `git log c7bc403..HEAD -- Azure-Banking-Voice-Agentic-AI` — 16, scoped past the monorepo-move boundary |
| voice-agent tests | **521 pass**, 3 skipped by design (Phase 5 close: 491) |
| mock-core-banking tests | **90 pass**, still with the voice agent uninstalled |
| B1 | **18 distinct attack ideas → 593 concrete cases**, 542 reaching an attempt, **0 breaches** — unchanged from Phase 5, re-run today |
| B2 | **0 occurrences**, now across all four OpenTelemetry content channels and two values (PIN, caller phone number) — issue #65 |
| B3 | Unchanged this phase; last re-verified live 2026-09-11 (Phase 5 close), still ~6.8 months from retirement |
| B4 | Unchanged this phase — blocking in CI, by construction |
| B5 | Frozen at Phase 5 close (N=13, real-call pool). Phase 6 adds the production measurement *path*; it does not re-set the number (D12) |
| `make lint`, B3 static check | clean, passing |

---

## Criterion by criterion

| # | criterion | evidence |
|---|---|---|
| 1 | Application Insights exists in Canada Central, workspace-based, bound to `...1D` | ✅ `appi-azure-banking-voice`, `location: 'canadacentral'` (`infra/modules/app-insights.bicep`), `provisioningState: Succeeded`, created 2026-09-14. A queried row exists (see #6) — the 200-OK rule is satisfied by more than the ARM read alone. |
| 2 | R-08 recomputed against one shared 5 GB grant, before provisioning | ✅ `COSTS.md`, 2026-09-13, applied 2026-09-14 (`infra/modules/app-insights.bicep`): bound to the existing `...1D` workspace rather than auto-provisioning a fourth one. Worst case **+$0.00/mo**, fixed total unchanged at $14.60/mo. |
| 3 | Open item 16 answered from the packages' source before FastAPI instrumentation is enabled | ✅ `docs/phase6/research-content-capture.md`, 2026-09-13, cited to source: none of FastAPI/httpx/requests instrumentation captures bodies by default or via any opt-in flag at the pinned release. |
| 4 | Open item 15 answered, or `RequestResponse` left disabled with that recorded | ✅ Settled as "undocumented" 2026-09-13 — no Microsoft primary source describes `RequestResponse`'s content coverage for the realtime API. Resolved via the stated fallback: it stays disabled, satisfying the criterion's own escape clause. |
| 5 | Exporter authenticates via the system-assigned identity, or the fallback is recorded with its Phase 7 debt | ✅ *Fallback branch.* `AZURE_MONITOR_AUTH=connection_string` is what's deployed; D10's Entra-identity path is open `/research`, named explicitly as Phase 7 debt (`PROJECT_STATE.md` next action 5) — not a silent shortcut. |
| 6 | One trace per call, root spanning the media socket, children per D5 | ✅ D16 smoke call: 17 spans, one trace (`OperationId 0fbed5fc19c793d970e889a2758792ee`) — 1 `call` span, 8 `turn`, 2 `tool_call`, 3 `core_banking` plus their HTTP children. Read out of `...1D`, not asserted from a 200 OK. |
| 7 | Attribute keys across all spans are exactly the D15 table | ✅ Blocking CI (`AllowlistSpanProcessor`'s exactness suite) **and** live: D16's `call` span attributes matched D15's table exactly — `correlation_id, connection_id, auth_state, end_reason, turn_count, duration_ms, closed_path_taken`, `closed_path_cause` correctly absent. |
| 8 | B2: 0 occurrences of the PIN or the phone number across all four channels | ✅ Issue #65, 2026-09-15 (`2458da3`). Channel 1 (span attribute) and channel 2 (span-event attribute) scanned in `tests/test_zz_b2_leak_scan.py`, each with a rehearsal proving the scanner catches a plant; channel 3 (OTel logging pipeline) and channel 4 (completion-hook upload) asserted absent in `tests/test_b2_content_recording.py`. |
| 9 | The relay runs correctly with the exporter unreachable | ✅ Blocking CI — `BatchSpanProcessor` behind every real exporter (never `SimpleSpanProcessor`), so an unreachable/hanging/raising exporter degrades to "nothing exported," never to a changed call outcome (ADR-004). |
| 10 | No named constraint is enforced by telemetry | ✅ Blocking CI — `tests/test_telemetry.py`'s `NoConstraintIsEnforcedByTelemetry` re-runs a gate refusal and a B4 turn-cap trip with telemetry configured and with it absent, asserts the two runs identical. Every other B1/B2/B4 suite runs with telemetry never configured at all. |
| 11 | The closed path is traced and its two causes are distinguished | ✅ Blocking CI — `closed_path_taken`/`closed_path_cause` on the `call` span, the latter set only when the former is `True` (`session.py:300-302`), pinned by the D15 allowlist-exactness suite. Live evidence (D16) confirms the *absent* case is correctly absent when the closed path didn't fire. |
| 12 | B4's daily ledger and B5's turn latency exist as metrics | ✅ D16 smoke call: `b5.turn_latency_seconds` (×2) and `b4.daily_minutes_used` (×1) present in the window, read out of `...1D`. |
| 13 | Six glossary terms in `CONTEXT.md` | ✅ `CONTEXT.md`'s Observability section: Telemetry, Trace, Span, Attribute, Allowlist, Redaction filter — six, each with its own _Avoid_ list. |
| 14 | One ADR: telemetry observes, never governs | ✅ `docs/adr/ADR-004-telemetry-observes-never-governs.md`. |

**All 14 met. None with a stated limit** — unlike Phase 5's B5/acceptance-call criteria, nothing here
was accepted at less than what it asked for.

---

## What this phase also closed, beyond its own numbered criteria

Two items PROJECT_STATE.md carried as blockers on Phase 6's *entry*, closed on exit day instead of
before start, by Marco's own choice to let #61's code land first:

- **B2 widening sign-off and implementation** (issue #65) — not one of the 14 numbered criteria
  above (it's a named-constraint change, tracked separately in "Constraint changes"), but load-bearing
  for #8's "four channels" language, which presupposes the widened wording.
- **`git log e42c063..HEAD`, human-reviewed** — all 58 commits (95 files), via `/code-review`. One
  drift found and fixed (`CLAUDE.md`'s B1 row had gone stale after issue #48); no B1/B2 code-level
  violations anywhere in the range.

One more piece of debt paid down, not asked for by any numbered criterion: **`ADR-005`**, recording
the shared core-banking client (issue #35) and the `escalate_to_human`-while-anonymous corollary of
B1 — both decisions were already live in code and in `docs/PLAN.md`, neither had ever been written up.

---

## Carried forward, unchanged

- **D10's Entra-identity ingestion path** — Phase 7 debt, named at criterion 5 above.
- **The 19 open items in `PROJECT_STATE.md`'s "Open items" list** — none newly introduced by this
  phase, none blocking; the usual accepted backlog (stale `az` CLI default, Docker Hub vs ACR, a
  handful of unconfirmed DTMF/frame-ordering edge cases).
- **B5 stays frozen on the Phase 5 real-call pool (N=13)** — this phase built the production
  measurement path and did not re-set the number, per D12.

---

## Needs Marco

**Sign-off to close Phase 6.** Distinct from `APPROVED: Phase 6` (given 2026-09-12, which covered
only the billable-resource gate to begin) — this is the decision that the phase's own exit criteria,
tallied above, are actually met.
