# 01: Prove the harness loop against a stub control server

**What to build:** A control server (`server_wrapper`) with its six ticket
tools returning hardcoded JSON, registered as a real service the pipeline can
target — including adding the service's launch dispatch alongside the
harness's existing per-service branches (today it branches on how to launch
each third-party server: `npx`, `pipx`, `docker`; this adds the branch for a
locally-authored Python server run over stdio). One task is written and run
end to end at `--k 1`. Correctness of the task's outcome is not the point yet
— proving the agent-to-server loop works, before any of it depends on a real
backend, is.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] `server_wrapper` exposes 6 tools, one per `/tickets` endpoint, vendor-named, returning hardcoded JSON payloads — TDD'd against a real in-memory MCP session, `tests/test_server_wrapper.py`
- [x] `server_wrapper` is registered as a service the pipeline can select via `--mcp` (`wrapper`)
- [x] The harness's per-service launch dispatch has a branch that starts `server_wrapper` over stdio — confirmed against a real subprocess, all 6 tools listed and callable
- [x] One task (instruction + verification script) exists for this service — `tickets/list_open_tickets`
- [x] `python -m pipeline --mcp wrapper --models gpt-4.1-mini --k 1` completes and produces a `TaskResult` with a populated turn count and token usage — confirmed: 2 turns, 791 tokens (761 in / 30 out), task passed. Results at `results/slice-1a/gpt-4-1-mini__wrapper/run-1/`.

## Bug found and fixed along the way

`src/agents/mcpmark_agent.py`'s LLM call unconditionally sent `enforcer_mode`/`think_mode` (Moonshot/Kimi-specific request fields) to every provider. OpenAI's API rejects unrecognized fields, so every OpenAI-model run failed at the first LLM call. Gated those two fields to Moonshot models only — the one call site that had them (`react_agent.py`'s completion path doesn't). Not covered by a test yet since it's outside this ticket's agreed seam (`server_wrapper`'s tools); worth a regression test if we pick this back up.
