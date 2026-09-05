# 01: Runbooks + deploys backend, baseline extension, pattern server

**What to build:** The Phase 4 foundation per `docs/PLAN.md` and
`docs/specs/phase-4-proxy-aggregator.md`: `runbooks` (id, repo_id, title,
body) and `deploys` (id, repo_id, environment, status) tables and their
endpoints, `server_wrapper` extended with 6 new flat tools
(`list_runbooks`, `get_runbook`, `create_deploy`, `get_deploy`,
`update_deploy_status`, `get_change_request`), and the new pattern server
`server_proxy_aggregator` exposing exactly two tools, `discover_tools` and
`call_tool`, fronting `repos`/`runbooks`/`deploys` behind them. Registered
as two new services, `proxy_wrapper` and `proxy_aggregator`, sharing one
task/state manager pair. One proof task crossing all three namespaces
exercises the full path on both servers.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `runbooks`, `deploys` tables, additive — no existing table changed
- [x] `GET /runbooks`, `GET /runbooks/{id}`, `POST /deploys`,
      `GET /deploys/{id}`, `PATCH /deploys/{id}` (status)
- [x] seed script seeds runbooks + deploys, mirroring
      `INITIAL_CUSTOMERS`/`INITIAL_TICKETS`
- [x] `tasks/utils/backend_state.py` gains readers for runbooks and deploys
- [x] `server_wrapper` gains the 6 new flat tools (including
      `get_change_request`, needed since the aggregator's `repos` operation
      had no baseline counterpart otherwise); still unnamespaced, raw JSON
      payloads, same shape as its existing 12 tools
- [x] `server_proxy_aggregator` exposes exactly two tools:
      `discover_tools(service)` returns that service's operations,
      `call_tool(service, tool, args)` dispatches to one of them — no
      per-namespace tool is separately listed
- [x] `proxy_wrapper`/`proxy_aggregator` registered in `src/services.py` and
      the launch-dispatch, sharing `ProxyAggregatorTaskManager`/
      `ProxyAggregatorStateManager`
- [x] One proof task (crossing repos + runbooks + deploys,
      `deploys/billing_rollback_ready`) written and passing live against
      both servers (see Live proof below)
- [x] Task-neutrality gate extended (`test_task_neutrality_proxy_aggregator.py`)
      so no task can name a tool or service identifier from either surface
- [x] Full test suite green (191 passed), no regression on Phase 1-3 tests

**Live proof:** `--mcp proxy_wrapper --k 1` and `--mcp proxy_aggregator --k 1`
against gpt-4.1-mini, both 1/1 pass (`results/phase4-ticket01-check/`).
`proxy_wrapper` (control): 6 turns / 6,024 input tokens. `proxy_aggregator`
(pattern): 24 turns / 37,610 input tokens.

**This is the opposite direction from every other phase.** Phases 1-3 all
showed the pattern server *cheaper* than its control; here the pattern
server cost 4x the tokens and turns on this single task. Root cause, from
the transcript: the model called `call_tool` directly with guessed service
names (`"repos"`/`"deploys"` right, but tool names like `get_repository`,
`list_runs`, `find_by_title` wrong) instead of calling `discover_tools`
first, burning many error-and-retry turns before landing on the real
operation names. A first live run (before item 4 in this checklist's
final form) failed outright the same way, which is what drove adding
`discover_tools()`'s no-args service listing and the "valid services/tools"
error text — that fix got the model to the right *service* names, not
reliably to the right *tool* names within a service.

**Carrying into Ticket 02:** this is n=1 on one task with one model, so it
is not yet evidence the module fails its own thesis — but ticket 02's
8-task run needs to watch whether this pattern holds. If it does, the fix
is very likely tightening `discover_tools`'s returned operation
descriptions (or nudging tool-call order via the tool docstrings) rather
than a task rewrite, since the earlier failed run showed the *services*
becoming discoverable already changed the outcome from a hard failure to a
pass.

**Bugs found and fixed along the way:**
1. `server_wrapper` had no `/repos` reader at all — the aggregator's
   `repos.get_change_request` operation had no baseline counterpart, since
   Phase 3's `/repos` reader lives on `session_baseline`, a server this
   module doesn't reuse. Added `get_change_request` to `server_wrapper` (6th
   new tool, not 5 as first scoped) so the A/B comparison stays fair.
2. `call_tool`'s return type annotation of bare `dict` silently produced
   `structuredContent: None` (FastMCP needs a concrete type like
   `dict[str, Any]` to serialize structured output) — caught by the first
   `call_tool` test, not by the type checker.
3. The proof task's first draft leaked the aggregator's own `deploys`
   namespace identifier in its prose ("guidance on billing-service
   deploys") — caught by the neutrality gate, fixed by rewording.
4. Caught by the first live run, not by any unit test: `discover_tools`
   required a `service` argument, so a model that didn't already know a
   valid service name had no way to ask "what services exist?" and failed
   the task outright, guessing names like `"version-control"`. Fixed by
   making `service` optional — no args lists the 3 valid services — and by
   making both tools' unknown-service/unknown-tool errors list the valid
   options, so a wrong guess is recoverable within the same run.

**Phase 4 ticket 01 is complete.** See the Live proof note above for the
turn/token result carried into ticket 02.

## Comments
