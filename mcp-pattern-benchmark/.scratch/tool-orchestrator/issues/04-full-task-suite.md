# 04: Full eight-task suite, both servers, neutrality enforced

**What to build:** The remaining seven tasks, bringing the module to eight
total under `tool_orchestrator/standard/`, each with its own instruction file
and verification script. Every verifier reads final state through one shared
helper rather than each opening its own Postgres access. Both `server_wrapper`
and `server_orchestrator` run the identical eight tasks. An automated check is
added that fails if any task's instruction file names a tool from either
server, so neutrality can't silently regress as tasks are edited later.

**Blocked by:** 03

**Status:** done

- [x] Eight tasks total exist under `tool_orchestrator/standard/`, each with an instruction file and a verification script
- [x] No task's instruction file names a tool from `server_wrapper` or `server_orchestrator`
- [x] All eight verifiers read final state through one shared state-reading helper
- [x] Both servers pass their intended tasks when run through the pipeline
- [x] An automated test scans every task's instruction file against both servers' tool names and fails the build on a match

The original `list_open_tickets` smoke task (Ticket 01) was retired: it was
read-only, so `server_orchestrator`'s one write-only tool had no way to
attempt it and its verify.py didn't check the agent's behavior at all. All
eight tasks are now `incidents/<scenario>`: a new incident report the agent
must create a ticket for, attach evidence to, assign an owner, and notify
about -- the one shape both a 4-call wrapper flow and a 1-call
`coordinate_incident` can actually complete, so it's a fair comparison.

Verified end to end against the real backend: both servers 8/8
(`results/slice-1d-check/`). Turn/token counts already show the expected
gap per task -- wrapper ~4 turns/~2,770 tokens, orchestrator ~2 turns/~900
tokens -- which is the difference Phase 1e's aggregation is meant to surface
across 3 runs.
