# Build Plan

Vertical slice first. Each phase ends with a number you can put in the README.
Vocabulary is defined in `CONTEXT.md`. Decisions are recorded in `docs/adr/`.

## Phase 0 — Repo, about 0.5 day

1. Fork MCPMark to `mcp-pattern-benchmark`.
2. Delete `src/mcp_services/*` and `tasks/*` for all 8 inherited services.
   Keep `src/base/`, `src/agents/`, `src/evaluator.py`, `src/aggregators/`,
   `src/factory.py`, `src/services.py`, `pipeline.py`.
3. Keep `LICENSE` unchanged. Add one README line crediting MCPMark.
4. Move `CONTEXT.md` and `docs/adr/` across.

Done when `python -m pipeline --help` still runs and `SERVICES` is empty.

## Phase 1 — Vertical slice: Tool Orchestrator, about 3 days

The slice that tests every assumption at once.

### 1a. Control server against a stub

Runtime risk first. The harness has never run an agent in this repo, so prove
the loop before anything depends on a real backend.

Write `server_wrapper` with its 6 ticket tools returning hardcoded JSON. Register
it in `src/services.py`. Run one task end to end with `--k 1`.

Done when a real agent run produces a `TaskResult` with a turn count and a token
count. Everything after this is content, not risk.

### 1b. Backend

Docker Compose with Postgres plus a FastAPI service. The `/tickets` namespace
only: 6 endpoints.

```
GET   /tickets                     PATCH /tickets/{id}
POST  /tickets                     POST  /tickets/{id}/comments
GET   /tickets/{id}                POST  /tickets/{id}/attachments
```

Seed script resets and reloads the schema per task. Repoint `server_wrapper` at
the real API and drop the stub.

### 1c. Pattern server

`server_orchestrator`: one tool, `coordinate_incident`, which creates the
incident, attaches evidence, assigns an owner and posts the notification in a
single call.

### 1d. Eight tasks

`tasks/tool_orchestrator/standard/<task_id>/` with `meta.json`,
`description.md`, `verify.py`. Both servers run the same 8.

- No `description.md` may name a tool from either server.
- Every `verify.py` reads final state from Postgres through one shared helper,
  `tasks/utils/backend_state.py`. Target 15 lines per verifier.
- Add `tests/test_task_neutrality.py`: fails if any `description.md` contains a
  tool name from either surface.

### 1e. Run and chart

```
python -m pipeline --mcp wrapper      --models claude-haiku-4-5 --k 3 --exp-name slice
python -m pipeline --mcp orchestrator --models claude-haiku-4-5 --k 3 --exp-name slice
python -m src.aggregators.aggregate_results --exp-name slice
```

48 agent runs. Read success rate, turn count and input tokens for both.

### Gate

Stop if the control passes 8 of 8 on all 3 runs. That means no headroom, and the
remaining 4 modules will show flat lines.

**Action on a failed gate: drop to a smaller model, keep the 8 tasks.** Rerun
phase 1d only, about 0.5 day. The tasks are already written by that point, so
the model is the cheaper variable to change. If the smaller model then fails 0
of 8 on both servers, the floor is the problem and the tasks do need rewriting.

## Phases 2 to 5 — One module each, about 2 days per module

Ordered by cost. Each phase adds its pattern server, its 8 tasks, and extends
the backend with the namespace it needs.

| Phase | Module | New backend | New baseline | Harness change |
|---|---|---|---|---|
| 2 | Domain-Specific Adapter | customers in `/tickets` | none, reuses control | none |
| 3 | Stateful Session Server | change requests in `/repos` | stateless server | none |
| 4 | Proxy Aggregator | `/repos`, `/runbooks`, `/deploys` | none, reuses control | none |
| 5 | Resource Gateway | runbook documents | none, reuses control | `list_resources`, `read_resource` |

Phase 5 harness change: add 2 methods to `MCPStdioServer`, then pass resources
into the agent's context alongside tools in all 3 agent paths.

## Phase 6 — README, about 1 day

- One table: 5 rows, each showing control and pattern for the 3 metrics.
- One grouped bar chart: 5 modules on x, 3 bars each for percent change.
- A limitations section: 1 model, 8 tasks per module, synthetic backend,
  Code-First Hybrid Adapter not built, count of re-run crashes.

## Totals

7 servers. 40 tasks. 240 agent runs. About 12 working days.
