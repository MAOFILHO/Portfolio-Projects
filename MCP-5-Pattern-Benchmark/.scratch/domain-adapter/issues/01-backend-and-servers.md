# 01: Customer-aware backend, baseline extension, pattern server

**What to build:** The Phase 2 foundation per `docs/PLAN.md`: a `customers`
table joined to `/tickets` (id, name, tier), a `GET /tickets/{id}/customer`
endpoint, `server_wrapper` (the reused Tool Orchestrator baseline) extended
with one new tool `get_ticket_customer`, and the new pattern server
`server_domain_adapter` exposing one semantic tool, `resolve_customer_ticket`,
that resolves a ticket with tier-appropriate routing (`priority-support` +
`[PRIORITY]`-tagged note for premium, `support-standard` otherwise) in one
call instead of the baseline's three (get customer, update ticket, add
comment). Registered as two new services, `domain_wrapper` and
`domain_adapter`, sharing one task/state manager pair. One proof task,
`customer_resolutions/acme_printer_fixed`, exercises the full path.

**Status:** done

- [x] `customers` table + `tickets.customer_id`, additive — no existing
      response column changed, so Phase 1's gated tests are untouched
- [x] `GET /tickets/{id}/customer`, 404 on unknown ticket or no link
- [x] `server_wrapper` gains `get_ticket_customer`; still the same 6 ticket
      tools otherwise (reused as the Phase 2 baseline per ADR 0002)
- [x] `server_domain_adapter` exposes exactly one tool, `resolve_customer_ticket`
- [x] `domain_wrapper` and `domain_adapter` registered in `src/services.py`
      and `src/agents/mcpmark_agent.py`'s launch-dispatch, sharing
      `DomainAdapterTaskManager`/`DomainAdapterStateManager`
- [x] One task passes verification through the shared `backend_state` helper
- [x] Task-neutrality gate extended (twin of `test_task_neutrality.py`) so no
      task can name a tool from either surface
- [x] Full test suite green (67 passed), including all of Phase 1's tests —
      no regression from reusing `server_wrapper`

**Design decision confirmed with the user:** one semantic tool (not several),
matching Tool Orchestrator's shape rather than a broader multi-tool surface,
to keep this phase's scope to about the same size as Phase 1's.

**Live proof:** `--mcp domain_wrapper --k 1` and `--mcp domain_adapter --k 1`
against gpt-4.1-mini, both 1/1 pass. `domain_wrapper` took 3 turns / 1,859
input tokens; `domain_adapter` took 2 turns / 712 input tokens.

Caught and fixed a real bug during the live run: the task's own policy
wording ("post a note starting with the tag `[PRIORITY]`") led the agent to
tag the note itself even on the pattern surface, and `resolve_customer_ticket`
tagged it again on top — stored comment came back
`"[PRIORITY] [PRIORITY] ..."`. Root cause: the tool can't assume it's the
only place tagging happens, since task instructions must stay identical
across both servers (task neutrality) and therefore must state the policy in
full for the baseline's sake. Fixed by making the tag idempotent
(`resolve_customer_ticket` skips tagging if the note already starts with
`[PRIORITY]`), verified by both a new unit test and a second live run showing
a single tag.

**Not done yet (next tickets):** the remaining 7 tasks, a real `--k 3`
agent run against both `domain_wrapper` and `domain_adapter`, aggregation,
and the neutrality gate check against actual results (mirrors Phase 1
tickets 04–05).
