# Phase 3 — Stateful Session Server

## Problem Statement

Phases 1 and 2 both reused the same control server for their baseline (ADR
`0002-baseline-pairing`), so neither has yet exercised a module whose whole
point is a baseline that behaves differently, not just a smaller tool
surface. Stateful Session Server is that module: it claims an agent pays
fewer input tokens when a server remembers its working state across turns
instead of forcing the agent to resend it. ADR `0007-stateful-baseline-is-a-server`
already fixed the shape of the comparison; this phase builds it.

## Solution

A new backend namespace, `/repos`, holding change requests (a pull-request-style
review target) and their review comments. Two new servers front it: a
stateless baseline whose one write tool takes the full comment list as an
argument on every call, and a pattern server that opens a session, appends one
comment per call, and submits from state the server already holds. Same eight
tasks run against both, per ADR `0004-no-composite-score`'s three metrics.

## User Stories

1. As the benchmark author, I want a `/repos` namespace (`repos`,
   `change_requests`, `review_comments`) seeded fresh per task, so both
   servers front real, stateful review data instead of stubs.
2. As the benchmark author, I want a baseline server with one read tool and
   one write tool whose write tool's argument is the full comment list so
   far, so that every call the agent makes resends everything already said,
   per ADR 0007.
3. As the benchmark author, I want a pattern server with `start_review`,
   `add_comment`, and `submit_review` tools, where `add_comment` takes only
   the new comment, so that the agent never resends prior turns' comments.
4. As the benchmark author, I want the pattern server's in-progress session
   state held in the server process's memory, not in Postgres, so that the
   backend keeps holding no MCP-layer concepts (matching `backend/app.py`'s
   existing boundary) and the only durable state is the final submitted
   review.
5. As the benchmark author, I want both servers registered as new services
   (`session_baseline`, `session_server`) sharing one task/state manager
   pair, so the harness runs them without changes.
6. As the benchmark author, I want one proof task exercising the full path
   (find a change request, post its review comments, submit a verdict) on
   both servers before writing the remaining seven.
7. As the benchmark author, I want eight tasks under `stateful_session`,
   neutral of tool names on both servers, verified through
   `tasks/utils/backend_state.py` additions, mirroring Phase 1/2.
8. As the benchmark author, I want 3 runs x 2 servers x 8 tasks aggregated
   into success rate, turn count and input tokens, and the same gate rule
   applied (stop if the baseline passes 8/8 on all 3 runs).

## Implementation Decisions

- **Backend**: additive schema only — `repos`, `change_requests` (id,
  repo_id, title, diff, status), `review_comments` (id, change_request_id,
  body). Endpoints: list/get change requests, patch status, post/get review
  comments. No existing table or endpoint changes.
- **Baseline is its own server**, not the reused control, per ADR 0002 — the
  module under test is the baseline's behavior itself, not a smaller tool
  surface. `get_change_request(id)` reads; `save_review(change_request_id,
  comments: list[str], verdict: str | None)` writes nothing to Postgres when
  `verdict` is `None` (a checkpoint call, pure validation) and persists all
  comments plus the status patch when `verdict` is set. It never remembers
  anything between calls — confirmed with the user as the design (see
  `.scratch/stateful-session-server/issues/01-backend-and-servers.md`).
- **Pattern server** holds session state in an in-memory dict keyed by a
  generated `session_id`, confirmed with the user in preference to a
  Postgres sessions table (the backend stays free of MCP-layer concepts, and
  verification only needs the final submitted state).
- **Service registration**: `session_baseline` and `session_server`, sharing
  one `StatefulSessionTaskManager`/`StatefulSessionStateManager` pair,
  following the Phase 1/2 registration pattern in `src/services.py`.
- **Tasks and neutrality**: eight tasks under `tasks/stateful_session/standard/`,
  a `test_task_neutrality_stateful_session.py` twin gate, and verifiers
  through `tasks/utils/backend_state.py`.

## Testing Decisions

- **Backend HTTP seam**: `FastAPI TestClient` against `backend/app.py`,
  backed by the real throwaway Postgres fixture already in
  `tests/backend/conftest.py` — same seam as `test_tickets_api.py`.
- **MCP tool seam**: an in-memory MCP `ClientSession` against each server's
  `mcp` object, backend wired to the same throwaway Postgres via
  `httpx.ASGITransport` — same seam as `test_server_wrapper.py` /
  `test_server_orchestrator.py`. No subprocess, no LLM, no mocking of either
  server's own HTTP client.
- **Harness/pipeline seam** (unchanged): `python -m pipeline --mcp <server>
  --k N` producing a `TaskResult`, reused as-is.
- **Task-neutrality seam**: a static test scanning `description.md` files
  against both servers' declared tool names, twin of the existing gate.

## Out of Scope

- Proxy Aggregator and Resource Gateway (Phases 4-5).
- Any backend namespace beyond `/repos`.
- The README results table and chart (Phase 6).
- Harness changes — this module needs none, same as Phases 1-2.

## Further Notes

- Filed to `.scratch/stateful-session-server/` per `docs/agents/issue-tracker.md`,
  three issues mirroring Phase 2's shape: backend+servers+proof task,
  full eight-task suite, run/aggregate/gate.
