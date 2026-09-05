# Phase 4 — Proxy Aggregator

## Problem Statement

Phases 1-3 each measured a pattern server against a control fronting exactly
one backend namespace. None has yet tested the case a real MCP deployment
faces constantly: one server standing in front of several unrelated upstream
services at once. A control built the way Phases 1-3's was — one flat,
unnamespaced tool per endpoint — would have to list every operation from
every service it fronts, and an agent has to wade through all of it on every
task regardless of which service that task actually needs. Proxy Aggregator
is the module that tests whether namespacing tools by service and scoping
discovery to what a task needs (CONTEXT.md's definition) reduces that cost.

## Solution

Two new backend namespaces, `/runbooks` and `/deploys`, join the existing
`/repos` (Phase 3) as the three services Proxy Aggregator fronts. The control
(`server_wrapper`) is extended with flat, unnamespaced tools for the two new
namespaces, per ADR `0002-baseline-pairing` — no new baseline server. The new
pattern server, `server_proxy_aggregator`, keeps its static MCP surface at
exactly two tools regardless of how many services it fronts: `discover_tools`
returns the operations for one named service, `call_tool` dispatches to one
of them, per ADR `0006-scoped-discovery-in-the-server`. Same eight tasks run
against both surfaces, each exercising at least two of the three services.

## User Stories

1. As the benchmark author, I want `runbooks` (id, repo_id, title, body) and
   `deploys` (id, repo_id, environment, status) tables seeded fresh per task,
   so the pattern server has three real, distinct upstream namespaces to
   front alongside the existing `repos`/`change_requests`.
2. As the benchmark author, I want `GET /runbooks` (optionally filtered by
   `repo_id`) and `GET /runbooks/{id}`, so a runbook can be listed and read.
3. As the benchmark author, I want `POST /deploys`, `GET /deploys/{id}`, and
   `PATCH /deploys/{id}` (status), so a deploy can be created, read, and
   moved through its status.
4. As the benchmark author, I want `server_wrapper` extended with one flat,
   unnamespaced tool per new endpoint (`list_runbooks`, `get_runbook`,
   `create_deploy`, `get_deploy`, `update_deploy_status`) plus
   `get_change_request` for the `/repos` read the aggregator also fronts, so
   the control fronts all three namespaces the same flat way it already
   fronts `/tickets`.
5. As the benchmark author, I want `server_proxy_aggregator`'s static MCP
   surface to be exactly two tools, `discover_tools` and `call_tool`, so
   fronting three (or more) upstream namespaces never grows the tool list the
   agent sees at connect time.
6. As the benchmark author, I want `discover_tools(service)` to return the
   tool specs (name, description, parameters) for one upstream service at a
   time (`repos`, `runbooks`, or `deploys`), so the agent only sees the
   operations relevant to what it's working on, not the union of all three.
7. As the benchmark author, I want `call_tool(service, tool, args)` to
   dispatch to the named operation against that service's namespace, so
   `discover_tools` and `call_tool` together stand in for what would
   otherwise be many individually-listed namespaced tools.
8. As the benchmark author, I want scoped discovery built as a tool the agent
   calls rather than a harness feature that re-lists tools per turn, so the
   harness needs no change and the comparison stays scoped to the MCP surface
   (ADR 0006).
9. As the benchmark author, I want both servers registered as new services
   (`proxy_wrapper`, `proxy_aggregator`) sharing one task/state manager pair,
   so the harness runs them without changes, following Phases 1-3's
   registration pattern.
10. As the benchmark author, I want one proof task that crosses all three
    namespaces on both servers (e.g. check a repo's change request, read the
    relevant runbook, then create and complete a deploy) before writing the
    remaining seven.
11. As the benchmark author, I want eight tasks under
    `tasks/proxy_aggregator/standard/`, each crossing at least two of the
    three namespaces, neutral of tool names on both servers, verified
    through `tasks/utils/backend_state.py` additions for runbooks and
    deploys.
12. As the benchmark author, I want 3 runs x 2 servers x 8 tasks aggregated
    into success rate, turn count and input tokens, and the same gate rule
    applied (stop if the control passes 8/8 on all 3 runs).
13. As the benchmark author, if the gate fails, I want the same
    smaller-model recovery path Phases 1-2 used, so the already-written
    tasks stay fixed and the model is the cheap variable to change.

## Implementation Decisions

- **Backend**: additive schema only — `runbooks` (id, repo_id, title, body),
  `deploys` (id, repo_id, environment, status). Endpoints: `GET /runbooks`,
  `GET /runbooks/{id}`, `POST /deploys`, `GET /deploys/{id}`, `PATCH
  /deploys/{id}` (status). No existing table or endpoint changes.
- **Baseline reuses the control**, per ADR 0002: `server_wrapper` gains 6 new
  flat, unnamespaced tools (`list_runbooks`, `get_runbook`, `create_deploy`,
  `get_deploy`, `update_deploy_status`, `get_change_request`) alongside its
  existing 7, same shape — raw JSON payloads, HTTP status surfaced as error
  text. `get_change_request` was caught missing mid-build: the aggregator's
  `repos.get_change_request` operation had no baseline counterpart, since
  Phase 3's `/repos` reader lives on `session_baseline`, a server Proxy
  Aggregator doesn't reuse. No new baseline server.
- **Pattern server**: `server_proxy_aggregator` exposes exactly two tools.
  `discover_tools(service: "repos" | "runbooks" | "deploys")` returns that
  service's operations. `call_tool(service, tool, args)` dispatches to one of
  them. The underlying operations (`repos.get_change_request`,
  `runbooks.list`, `runbooks.get`, `deploys.create`, `deploys.get`,
  `deploys.update_status`) are never separately listed MCP tools — they only
  exist behind `call_tool` — so the static surface stays at two tools no
  matter how many services get fronted later. This follows directly from ADR
  0006's own reasoning: a per-namespace static tool listing wouldn't need a
  `discover_tools` step at all.
- **Service registration**: `proxy_wrapper` and `proxy_aggregator`, sharing
  one `ProxyAggregatorTaskManager`/`ProxyAggregatorStateManager` pair,
  following the Phase 1-3 registration pattern in `src/services.py`. No
  harness change, matching `docs/PLAN.md`'s phase table.
- **Tasks and neutrality**: eight tasks under
  `tasks/proxy_aggregator/standard/`, each crossing at least two of the three
  namespaces, a `test_task_neutrality_proxy_aggregator.py` twin gate that
  also treats `discover_tools`'s `service` values and `call_tool`'s `tool`
  argument names as tool-identifying strings a task description must not
  leak, verifiers through `tasks/utils/backend_state.py` additions.

## Testing Decisions

- A good test here checks external behavior — did the harness produce a
  `TaskResult`, did `discover_tools` return the right service's operations,
  did `call_tool` change the expected row in Postgres, does a task
  description leak a tool or service name — never internal dispatch logic.
- **Backend HTTP seam**: `FastAPI TestClient` against `backend/app.py`, the
  same throwaway Postgres fixture already in `tests/backend/conftest.py` —
  same seam as `test_tickets_api.py` / `test_change_requests_api.py`. New
  `test_runbooks_api.py` / `test_deploys_api.py`.
- **MCP tool seam**: a real in-memory MCP `ClientSession` against each
  server's `mcp` object, backend wired to the same throwaway Postgres via
  `httpx.ASGITransport` — same seam as `test_server_wrapper.py` /
  `test_server_session.py`. For `server_proxy_aggregator`, tests call
  `discover_tools` and `call_tool` directly and assert on the returned tool
  specs and on backend state after a `call_tool` round trip — no mocking of
  the dispatch itself.
- **Harness/pipeline seam** (unchanged): `python -m pipeline --mcp <server>
  --k N` producing a `TaskResult`, reused as-is.
- **Task-neutrality seam**: a static test scanning `description.md` files
  against both servers' declared tool-identifying strings — `server_wrapper`'s
  12 flat tool names, and `server_proxy_aggregator`'s service names plus the
  per-service tool names reachable through `call_tool`.

## Out of Scope

- Resource Gateway (Phase 5).
- Any backend namespace beyond `repos`/`runbooks`/`deploys`.
- The README results table and chart (Phase 6).
- Harness changes — this module needs none, same as Phases 1-3.

## Further Notes

- Filed to `.scratch/proxy-aggregator/` per `docs/agents/issue-tracker.md`,
  three issues mirroring Phase 2/3's shape: backend+servers+proof task, full
  eight-task suite, run/aggregate/gate. Ticket split and the four reused
  seams above were confirmed with the user before writing this spec.
- The `discover_tools`/`call_tool` two-tool dispatch is the one design
  decision this spec commits to outright rather than leaving open for ticket
  01, since it falls directly out of ADR 0006's stated reasoning.
