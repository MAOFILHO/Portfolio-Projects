# 01: Repos backend, stateless baseline, session pattern server

**What to build:** The Phase 3 foundation per `docs/PLAN.md` and
`docs/specs/phase-3-stateful-session-server.md`: a `/repos` namespace
(`repos`, `change_requests`, `review_comments`), the new baseline server
`server_baseline` (own server, not the reused control, per ADR 0002) exposing
`get_change_request` and a stateless `save_review` that takes the full
comment list every call, and the pattern server `server_session` exposing
`start_review` / `add_comment` / `submit_review` backed by in-memory session
state. Registered as two new services, `session_baseline` and
`session_server`, sharing one task/state manager pair. One proof task
exercises the full path on both servers.

**Status:** done

- [x] `repos`, `change_requests`, `review_comments` tables, additive —
      no existing table changed
- [x] `GET /repos/{repo_id}/change-requests`, `GET /change-requests/{id}`,
      `PATCH /change-requests/{id}` (status), `POST
      /change-requests/{id}/comments`, `GET /change-requests/{id}/comments`
- [x] seed script seeds repos + change requests, mirroring
      `INITIAL_CUSTOMERS`/`INITIAL_TICKETS`
- [x] `tasks/utils/backend_state.py` gains `get_change_request`,
      `find_change_request_by_title`, `list_review_comments`
- [x] `server_baseline` exposes exactly two tools; `save_review` persists
      nothing when `verdict` is omitted
- [x] `server_session` exposes exactly three tools; `add_comment` never
      resends prior comments; state lives in an in-memory dict, not Postgres
- [x] `session_baseline`/`session_server` registered in `src/services.py`,
      `src/agents/base_agent.py`'s STDIO_SERVICES, and
      `src/agents/mcpmark_agent.py`'s launch-dispatch
- [x] One proof task passes verification through `backend_state` on both
      servers
- [x] Full test suite green (120 passed), no regression on Phase 1/2 tests

**Design decisions confirmed with the user:**
- Session state lives in the pattern server's process memory, not a Postgres
  table (see phase-3 spec's Implementation Decisions).
- The baseline is its own server per ADR 0002, not a reuse of `server_wrapper`
  — this module's whole point is the baseline's resend behavior.

**Live proof:** `--mcp session_baseline --k 1` and `--mcp session_server --k 1`
against gpt-4.1-mini, both 1/1 pass. `session_baseline` took 3 turns / 1,451
input tokens; `session_server` took 4 turns / 1,996 input tokens.

Caught and fixed a real bug during the live run: `save_review`'s first
version had no docstring, so the agent called it three times with only the
new comment each time (reasonable append-style guess) instead of resending
the full list `save_review` actually requires — the first two comments were
silently discarded, verification failed. Root cause: a stateless tool's
"resend everything" contract isn't guessable from its name or a
task-neutral description; the tool's own MCP-level docstring is the only
place that contract can legally live without leaking into `description.md`.
Fixed by documenting the contract on `save_review` itself; re-run passed.

**Not yet proven (flag for Ticket 02):** on this one small task, the smart
model collapsed the baseline into one `save_review` call carrying both
comments, so the "baseline resends growing state" cost ADR 0007 predicts
didn't show up in the turn/token numbers above — `session_server` was
actually pricier here (4 turns vs 3) because a 2-comment review has little
for the session pattern to amortize. The eight-task suite needs at least one
task that forces genuinely separate turns (e.g. reacting to diff content
revealed one file at a time) for the baseline's resend cost to be
observable, not just theoretically true. Carrying this into Ticket 02.

**Not done yet (next tickets):** the remaining seven tasks, a real `--k 3`
agent run against both servers, aggregation, and the neutrality gate check
against actual results (mirrors Phase 1/2 tickets 04-05).

## Comments
