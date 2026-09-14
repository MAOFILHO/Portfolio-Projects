# Phase 1 archive — the working voice agent

Phase 1's closed record as `PROJECT_STATE.md` carried it, moved here 2026-09-09 under decision 18
(`CLAUDE.md`). **This is the state file's residue, not Phase 1's narrative** — Phase 1 had already
been written up properly at the time, and those documents remain the account of what happened:

- `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` — the exit criteria, whether each held, and the open-items
  triage (Part 1) that says which of the still-open items block what.
- `docs/phase1/research-aoai-realtime-wire-format.md` — the wire format confirmed live, which
  `realtime/session.py` still cites rather than re-deriving.
- `docs/handoffs/2026-08-27-phase1-logpath-resolved.md` — the app-side log path, resolved.
- `docs/handoffs/2026-09-07-phase1-b4-guard-and-review-findings.md` — the B4 guard and that round's
  review findings.

## Closed state

**Phase 1 is the demonstrable deliverable and still works** — reconfirmed at Phase 2's sign-off,
2026-09-08. It is the thing a caller actually reaches when they dial the number, and every phase
since has been held to not breaking it.

Compute was re-provisioned for Phase 1's own work after Phase 0's teardown, so Phase 0's teardown is
not the current resource state. The container image lineage from there: Phase 1 ran `:latest`, Phase
2 replaced it with `:p2` on 2026-09-07 and `:p3` on 2026-09-08 (`docs/phase2/archive.md`). What is
running now is in `PROJECT_STATE.md` under "Live Azure state".

## Phase 1-era items that are still open

They stay in `PROJECT_STATE.md`'s open-items list rather than being archived here, because they are
unresolved rather than historical: the missing ACS-side call-diagnostics path, `02-test-calls.sh`'s
missing skip guard, R-03's permanently unresolved Call-1 DTMF anomaly, the Docker Hub versus ACR
decision that never happened, the intermittent interrupt-the-caller defect, and the parked dead-air
delay before the agent speaks first.
