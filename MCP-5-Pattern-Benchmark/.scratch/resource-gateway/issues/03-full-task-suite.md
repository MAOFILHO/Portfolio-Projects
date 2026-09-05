# 03: Full eight-task suite, both servers, neutrality enforced

**What to build:** The remaining seven tasks, bringing the module to eight
total under `tasks/resource_gateway/standard/`, each ending in an
`acknowledge_runbook` call. Both `server_wrapper` and
`server_resource_gateway` run the identical eight. Mirrors Phase 2 ticket
02 / Phase 3 ticket 02 / Phase 4 ticket 02.

**Blocked by:** 02

**Status:** done

- [x] Eight tasks total under `tasks/resource_gateway/standard/`, each with
      its own instruction file and verification script, each requiring a
      runbook read followed by an `acknowledge_runbook` call
- [x] No task's instruction file names a tool from either server or the
      `runbook://` URI scheme
- [x] All eight verifiers read final state through
      `tasks/utils/backend_state.py`, and also fail if the acknowledgement's
      note contains the runbook's `internal_notes` text
- [x] Both servers pass their intended tasks when run through the pipeline
- [x] `test_task_neutrality_resource_gateway.py` scans every task's
      instruction file against both servers' tool-identifying strings and
      the `runbook://` scheme, and fails the build on a match

**Live pipeline pass run in ticket 04** (this session had no model API key
at the time this ticket was written; a key was configured for ticket 04,
so the run happened there instead, 3x per server against all 8 tasks —
see that ticket for the table). Both servers pass a majority of the 8
tasks; the shared failures trace to the pre-existing repo-id-guessing gap
(no repo name→id lookup tool), same limitation accepted in Phases 2-4,
not a defect in these 8 tasks' authoring.

## Comments
