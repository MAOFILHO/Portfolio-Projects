# 03: Pattern server on the same backend

**What to build:** The pattern server for this module, `server_orchestrator`,
exposing one tool, `coordinate_incident`, that performs create incident →
attach evidence → assign owner → post notification as a single server-side
call instead of four agent-driven ones. It's registered the same way as
`server_wrapper` (service entry plus launch-dispatch branch) and fronts the
same backend from Ticket 02. The same single task used in Tickets 01–02 is
run against it and passes — proving one task can be served correctly by both
surfaces before the suite is scaled to eight.

**Blocked by:** 02

**Status:** done

- [x] `server_orchestrator` exposes exactly one tool, `coordinate_incident`
- [x] The tool performs the full create/attach/assign/notify sequence against the Ticket 02 backend in one call
- [x] `server_orchestrator` is registered as a service the pipeline can select via `--mcp`, with its own launch-dispatch branch
- [x] The single existing task passes when run against `server_orchestrator`

`coordinate_incident` maps the four steps onto Ticket 02's existing
endpoints: create -> POST /tickets, attach -> POST .../attachments, assign
-> PATCH (assignee), notify -> POST .../comments (no separate
incidents/evidence/notifications namespace exists yet, by design -- Tool
Orchestrator's variable is call count, not tool naming; that's the
Domain-Specific Adapter pattern, Phase 2). Verified end to end with
`--mcp orchestrator --k 1` against the real backend (results/slice-1c-check),
same as Ticket 01's proof.
