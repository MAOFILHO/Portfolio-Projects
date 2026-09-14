# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 6, 2026-09-14

**Working directory the next session must land in:**
`/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`,
branch `azure-banking-work`. Verify with `git branch --show-current` and `git worktree list` —
don't trust this line.

## STOP CONDITIONS — absolute, no exceptions (restated verbatim, CLAUDE.md)

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2). These always get a human look before they land, no
  matter how mechanical the change appears.
- The phone number `+17059100383` is never released, by any script, at any phase, for any reason.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds ≤400 lines / ~20 KB.
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## What this session did

Reviewed and hardened an already-in-flight fix in `azbank_voice_agent/realtime/session.py`:
`escalate_to_human` used to end the call the instant the tool returned, before the model's closing
line ever played — callers heard silence instead of an apology (a live regression against issue
#48's spec, found 2026-09-14).

Two `/code-review` rounds ran (parallel Standards + Spec sub-agents each round). Round 1 confirmed
the silence fix itself was sound but found two edge cases in how the ended call got *classified*.
Both were fixed and tested this session:

1. The escalation's closing-remark `response.done` could also trip B4's 20-turn cap; checking the
   cap first mislabeled the call `end_reason="cost_cap"` instead of `"escalated"`. Fixed by
   checking escalation completion first.
2. If the event stream ended (fake ran out of events / a real clean close) while an escalation was
   still pending its closing line, the call fell through unclassified as `"model_ended"`. Fixed by
   raising `EscalationRequested` there too.

Round 2 (on the full diff, all three fixes together) found no hard standards violations and
confirmed both edge cases above are closed — but surfaced one new, deliberately **unfixed** gap
(Marco's call, to avoid scope creep): a genuine dropped connection (caller hangs up mid-apology, or
the socket errors rather than closing cleanly) can still bypass both checks and mislabel as
`"caller_hangup"` or a bare `"error"`. `FakeRealtimeServer` has no fixture for an abnormal close, so
this isn't even testable as the fake stands today.

**Commits made this session** (read these instead of re-deriving the diff):
- `fe1bb82` — the fix itself + 4 new tests (`tests/test_whole_call.py`,
  `tests/test_telemetry.py::EscalationEndReasonIsDistinguished`).
- `a6373ab` — `PROJECT_STATE.md` open item 19, recording the dropped-connection gap above.

Full suite green throughout: 517 (voice-agent) + 90 (mock-core-banking) tests, lint clean, B1's
593-case red-team corpus 0 breaches.

## Outstanding work (see `PROJECT_STATE.md` for the full current list — not duplicated here)

Highlights relevant to where this session left off:
- **Open item 19** (new, this session): the dropped-connection mislabel. Needs a `FakeRealtimeServer`
  fixture for an abnormal socket close (`ConnectionClosedError`/`WebSocketConnectionClosedError`,
  not `StopAsyncIteration`) before it can even be tested, let alone fixed.
- **Issue #62**: Application Insights is live and wired; the D16 smoke call still needs to be *redone*
  against the current revision and its rows queried in `...1D` to confirm delivery — nothing has
  queried a row yet (`PROJECT_STATE.md` §Live Azure state).
- **B2 widening sign-off** — still not given; blocks part of Phase 6's design.
- **`git log e42c063..HEAD`** — 25 commits still owed a human read.
- **ADR not yet written**: the shared core-banking client / `escalate_to_human`-while-anonymous
  corollary (`PROJECT_STATE.md` §Next actions item 3).
- **`/research`**: the IAM role App Insights ingestion needs for the Entra-identity auth path (D10) —
  currently on the connection-string fallback, a named Phase 7 debt.

## Suggested skills for the next session

- **`/research`** if the next session designs the abnormal-socket-close fixture (needs to confirm
  the exact exception shapes `openai.resources.realtime` raises on a real drop — round 2's Spec
  reviewer already found the primary-source names: `ConnectionClosedError`,
  `WebSocketConnectionClosedError` — verify before building the fixture on that alone).
- **`/wizard`** for the D16 smoke call itself (needs a real dialed call and Marco's hands) and for
  any resumed provisioning work.
- **`/code-review`** before any Phase 6 exit-criteria check, per this project's standing rule — no
  exceptions, including changes that feel small.
- Do **not** self-invoke any skill — CLAUDE.md's skill-discipline section is explicit that Marco
  triggers skills, Claude names them and stops.
