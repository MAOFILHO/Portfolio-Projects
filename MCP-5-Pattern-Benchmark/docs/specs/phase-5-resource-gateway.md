# Phase 5 — Resource Gateway

## Problem Statement

Phases 1-4 each measured a pattern server against a flat control returning raw
tool payloads. None has tested MCP's other primitive — Resources — even
though `CONTEXT.md` already names Resource Gateway as one of the five modules
in scope, and the harness itself has never surfaced a resource to an agent.
None has tested a case where a naive design can leak something a
well-designed one structurally cannot: a runbook that carries an
internal-only note alongside its customer-safe guidance. Resource Gateway is
the module that tests whether exposing runbook content as a native MCP
resource, sanitized at the server boundary, produces a real safety
difference from a flat tool that returns everything it's given.

## Solution

The `runbooks` table gains one field, `internal_notes`, never present in the
pattern server's resource but always present in the control's flat tool. A
new `runbook_acknowledgements` table (id, repo_id via runbook, runbook_id,
note) holds the one write action either surface performs. The control
(`server_wrapper`) gains a flat `acknowledge_runbook` tool, and its existing
`get_runbook`/`list_runbooks` tools start returning `internal_notes`. The new
pattern server, `server_resource_gateway`, exposes each runbook as a native
MCP resource (`runbook://{id}`) containing only the sanitized body, plus two
narrow tools: `search_runbooks` (query, scoped by repo) and
`acknowledge_runbook` (write). The harness itself changes for the first time
in this benchmark: `MCPStdioServer` gains `list_resources`/`read_resource`,
wired into all 3 agent call sites so resources surface to the agent the same
way tools already do. Same 8 tasks run against both surfaces; each verifier
checks the acknowledgement landed and that its note never contains the
withheld internal-only text.

## User Stories

1. As the benchmark author, I want `runbooks` extended with an
   `internal_notes` field, so the backend can hold content a well-designed
   surface should never forward to the agent.
2. As the benchmark author, I want a new `runbook_acknowledgements` table
   (id, runbook_id, note), so there's one write action every task can verify
   against, on both surfaces.
3. As the benchmark author, I want `GET /runbooks/{id}` and
   `GET /runbooks?repo_id=` to return `internal_notes` unconditionally, so
   sanitization is a choice each MCP server makes, not something baked into
   the backend.
4. As the benchmark author, I want `POST /runbooks/{id}/acknowledgements`
   and `GET /runbooks/{id}/acknowledgements`, so an acknowledgement can be
   written and read back, mirroring the existing `review_comments` shape.
5. As the benchmark author, I want `server_wrapper`'s existing
   `get_runbook`/`list_runbooks` tools to return `internal_notes` unchanged
   from the backend, so the control stays a flat 1:1 wrapper that hides
   nothing (per ADR 0002).
6. As the benchmark author, I want `server_wrapper` extended with one new
   flat tool, `acknowledge_runbook(runbook_id, note)`, so the control can
   complete the same tasks the pattern server can.
7. As the benchmark author, I want a new pattern server,
   `server_resource_gateway`, exposing each runbook as a native MCP resource
   at `runbook://{id}` containing only its `body`, so the agent can read
   runbook guidance without ever receiving `internal_notes`.
8. As the benchmark author, I want `server_resource_gateway` to expose
   `search_runbooks(repo_id)`, so the agent can find the right runbook for a
   repo without wading through every resource by hand.
9. As the benchmark author, I want `server_resource_gateway` to expose
   `acknowledge_runbook(runbook_id, note)`, so the pattern server's one write
   action mirrors the control's exactly, keeping the comparison fair.
10. As the benchmark author, I want `MCPStdioServer` extended with
    `list_resources()`/`read_resource(uri)`, mirroring its existing
    `list_tools()`/`call_tool()`, so the harness itself can surface
    resources to an agent for the first time.
11. As the benchmark author, I want resources passed into the agent's
    context alongside tools in all 3 agent call sites (both
    `mcpmark_agent.py` call sites and `react_agent.py`'s), so every agent
    path sees what a real MCP client would see, not just the tool list.
12. As the benchmark author, I want `resource_wrapper`/`resource_gateway`
    registered as new services in `src/services.py`, sharing one
    task/state manager pair, so the harness runs them without further
    change, following Phases 1-4's registration pattern.
13. As the benchmark author, I want one proof task that has the agent read a
    runbook resource and post an acknowledgement, verified live against
    both servers, before writing the remaining seven.
14. As the benchmark author, I want 8 tasks under
    `tasks/resource_gateway/standard/`, each requiring the agent to read a
    runbook and post an acknowledgement, neutral of tool/resource-URI names
    on both servers, verified through `tasks/utils/backend_state.py`
    additions for acknowledgements.
15. As the benchmark author, I want every task's verifier to also fail if
    the acknowledgement's note contains the runbook's `internal_notes` text,
    so sanitization becomes a measured property, not a cosmetic label.
16. As the benchmark author, I want a `test_task_neutrality_resource_gateway.py`
    gate scanning task descriptions against both servers' tool names and the
    `runbook://` URI scheme, so neutrality holds the same way it does for
    every other module.
17. As the benchmark author, I want a real, no-mock unit test for
    `MCPStdioServer`'s new methods against an actual subprocess-backed MCP
    server, so the harness change has a fast TDD loop instead of only a
    live pipeline run as its test.
18. As the benchmark author, I want 3 runs x 2 servers x 8 tasks aggregated
    into success rate, turn count and input tokens, with the same gate rule
    (stop if the control passes 8/8 on all 3 runs) applied.
19. As the benchmark author, if the gate triggers, I want the same
    smaller-model recovery path used in earlier phases, so the
    already-written tasks stay fixed and the model is the cheap variable to
    change.

## Implementation Decisions

- **Backend**: additive schema only — `runbooks.internal_notes` (text,
  default empty), new `runbook_acknowledgements` (id, runbook_id, note). No
  existing table or endpoint dropped. `GET /runbooks`, `GET /runbooks/{id}`
  keep their path and method, response gains `internal_notes`. New
  `POST /runbooks/{id}/acknowledgements`, `GET /runbooks/{id}/acknowledgements`,
  mirroring `review_comments`'s exact shape.
- **Baseline reuses the control**, per ADR 0002: `server_wrapper`'s
  `get_runbook`/`list_runbooks` responses gain `internal_notes` with no
  other shape change; one new flat tool, `acknowledge_runbook(runbook_id,
  note)`.
- **Pattern server**: `server_resource_gateway` uses FastMCP's native
  `@mcp.resource("runbook://{id}")` template resource (confirmed supported
  by the installed SDK — `FastMCP.resource()` registers a template when the
  URI contains `{param}` matching the function's parameters) returning only
  `body`. Two tools: `search_runbooks(repo_id)` (query, repo-scoped only, no
  keyword search) and `acknowledge_runbook(runbook_id, note)` (write) — no
  separate single-item read tool, since `read_resource` already covers that.
- **Harness change**: `MCPStdioServer` gains `list_resources()`/
  `read_resource(uri)`, thin wrappers over the SDK `ClientSession` methods of
  the same name (already present in the installed SDK), mirroring the
  existing `list_tools()`/`call_tool()` implementation exactly. Both
  `mcpmark_agent.py` call sites and `react_agent.py`'s single call site fetch
  resources the same way they fetch tools and fold them into the agent's
  context. Resource discovery is free (fetched once at connect, like tools);
  `read_resource` costs a turn like any tool call.
- **Service registration**: `resource_wrapper`/`resource_gateway`, sharing
  one `ResourceGatewayTaskManager`/`ResourceGatewayStateManager` pair,
  following the Phase 1-4 registration pattern in `src/services.py`.
- **Cross-module impact**: Phase 4's two existing `server_wrapper` tests
  (`test_list_runbooks_returns_runbooks_for_a_repo_from_the_real_backend`,
  `test_get_runbook_returns_a_runbook_that_only_exists_in_the_real_backend`)
  assert exact dict equality on `get_runbook`/`list_runbooks`'s current
  shape; both need their expected literals updated to include
  `internal_notes` — an update to match the new shape, not a behavior
  change.
- **Tasks and neutrality**: 8 tasks under `tasks/resource_gateway/standard/`,
  each ending in an `acknowledge_runbook` call, a
  `test_task_neutrality_resource_gateway.py` twin gate that also treats the
  `runbook://` URI scheme as a tool-identifying string a task description
  must not leak.

## Testing Decisions

- A good test here checks external behavior — did `read_resource` return
  only the sanitized body, did the control's tool return `internal_notes`
  too, did the right acknowledgement row land, does its note leak the
  withheld text — never internal dispatch logic.
- **Backend HTTP seam**: `FastAPI TestClient` against `backend/app.py`, same
  throwaway Postgres fixture as `test_runbooks_api.py` — same seam as
  `test_change_requests_api.py`/`test_deploys_api.py`. Extend
  `test_runbooks_api.py` for `internal_notes`; new
  `test_runbook_acknowledgements_api.py`.
- **MCP resource/tool seam**: real in-memory `ClientSession` via
  `create_connected_server_and_client_session` against each server's `mcp`
  object, backend wired through `httpx.ASGITransport` — same seam as
  `test_server_wrapper.py`/`test_server_proxy_aggregator.py`. For
  `server_resource_gateway`, tests call `session.list_resources()`/
  `read_resource(uri)` directly and assert the returned content excludes
  `internal_notes`; for `server_wrapper`, tests assert its tools include it.
- **Harness seam — new to this codebase**: a real, subprocess-backed test of
  `MCPStdioServer.list_resources()`/`read_resource()` against one of the
  actual pattern servers over real stdio — no stub session, no mock — since
  nothing in the codebase tests this class directly today; it's only ever
  been exercised through full, real-LLM pipeline runs.
- **Task-neutrality seam**: static scan of `description.md` files against
  both servers' declared tool-identifying strings — `server_wrapper`'s flat
  tool names (13, after `acknowledge_runbook`) and
  `server_resource_gateway`'s tool names plus the `runbook://` URI scheme.
- **Harness/pipeline seam** (unchanged): `python -m pipeline --mcp <server>
  --k N` producing a `TaskResult`, reused as-is.

## Out of Scope

- Any backend namespace or field beyond `internal_notes` and
  `runbook_acknowledgements`.
- MCP prompts (the third MCP surface type) — resources and tools only, per
  the harness-change scope this phase commits to.
- Resource content beyond text (no binary/blob resources).
- Keyword search in `search_runbooks` — repo-scoped filtering only.
- The README results table and chart (Phase 6).

## Further Notes

- Filed to `.scratch/resource-gateway/` per `docs/agents/issue-tracker.md`.
  Ticket split happens next via `/to-tickets`.
- This spec's seams and decisions were grilled over several rounds with the
  user before writing: the sanitization mechanic (Q2), its verification
  shape (Q3), the redacted field and write-tool schema (Q4-Q6), and the four
  test seams above (confirmed separately, after the harness's actual MCP SDK
  capabilities were checked rather than assumed). Recorded in `CONTEXT.md`
  ("Internal notes", "Runbook acknowledgement") and
  `docs/adr/0008-sanitization-is-a-measured-property.md`.
- This is the first module whose verifier checks content shape (a
  forbidden-substring scan) rather than pure state equality, and the first
  harness change since Phase 0 — both are deliberate, scoped growth, not
  incidental scope creep.
