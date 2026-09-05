# 02: Runbook backend, baseline extension, resource-gateway pattern server, proof task

**What to build:** The Phase 5 foundation per `docs/PLAN.md` and
`docs/specs/phase-5-resource-gateway.md`: `runbooks` gains an
`internal_notes` field, a new `runbook_acknowledgements` table holds the
one write action either surface performs, `server_wrapper` gains a flat
`acknowledge_runbook` tool and starts returning `internal_notes` from its
existing `get_runbook`/`list_runbooks`, and the new pattern server
`server_resource_gateway` exposes each runbook as a sanitized
`runbook://{id}` resource plus `search_runbooks`/`acknowledge_runbook`.
Registered as two new services, `resource_wrapper` and `resource_gateway`,
sharing one task/state manager pair. One proof task exercises the full path
on both servers.

**Blocked by:** 01

**Status:** done

- [x] `runbooks` gains `internal_notes`, additive — no existing column
      changed; new `runbook_acknowledgements` table (id, runbook_id, note)
- [x] `GET /runbooks`, `GET /runbooks/{id}` return `internal_notes`
      unconditionally; new `POST /runbooks/{id}/acknowledgements`,
      `GET /runbooks/{id}/acknowledgements`, mirroring `review_comments`
- [x] `tasks/utils/backend_state.py` gains a reader for acknowledgements
- [x] `server_wrapper` gains one new flat tool,
      `acknowledge_runbook(runbook_id, note)`; its existing
      `get_runbook`/`list_runbooks` tests updated for the new
      `internal_notes` field
- [x] `server_resource_gateway` exposes each runbook as a sanitized
      `runbook://{id}` resource (body only, never `internal_notes`) plus
      `search_runbooks(repo_id)` and `acknowledge_runbook(runbook_id, note)`
- [x] `resource_wrapper`/`resource_gateway` registered in `src/services.py`
      and the launch-dispatch, sharing `ResourceGatewayTaskManager`/
      `ResourceGatewayStateManager`
- [x] One proof task (read a runbook, post an acknowledgement) written and
      passing live against both servers

**Bug found and fixed mid-build, not in ticket 01's scope as written:**
`runbook://{id}` is a FastMCP *template* resource, and the SDK never returns
templates from `list_resources()` (only `list_resource_templates()`) — so the
harness's synthetic `read_resource` tool (built in ticket 01 from
`list_resources()` alone) was empty for `server_resource_gateway`, and a live
run confirmed it: the agent finished the proof task by guessing, never
calling `read_resource` at all. Fixed at the root, in the one shared function
every agent call site routes through (`base_agent._augment_tools_with_resources`/
`_build_read_resource_tool`), not per-server: it now also fetches
`list_resource_templates()` and lists template URIs (with a note to fill in
the placeholder) alongside concrete ones. `MCPStdioServer` gained the
matching `list_resource_templates()`, mirroring `list_resources()`. Re-ran
live after the fix: the agent called `search_runbooks` for the id, then
`read_resource("runbook://1")`, then `acknowledge_runbook` — the resource
primitive is actually exercised now, not bypassed.

**Live proof:** `runbooks/billing_rollback_ack` run via
`python -m pipeline --mcp <service> --models gpt-4.1-mini --tasks
runbooks/billing_rollback_ack --k 1` against a local `docker compose up`
backend — 1/1 passed on both `resource_wrapper` and `resource_gateway`
(results under `results/phase5-ticket02-check*/`, gitignored).

## Comments
