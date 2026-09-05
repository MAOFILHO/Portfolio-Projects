# Phase 1 — Vertical Slice: Tool Orchestrator

## Problem Statement

The repo was just stripped down to a bare harness (Phase 0): the pipeline
entry point runs, but `SERVICES` is empty and no pattern module has ever been
measured end to end. Before investing in four more pattern modules, we don't
know whether the harness can run an agent against a server this repo owns, or
whether a synthetic backend and a pair of hand-written servers can produce a
believable difference between a baseline and a pattern module on the three
metrics (success rate, turn count, input tokens).

## Solution

Build one pattern module, Tool Orchestrator, all the way through: a baseline
server and a pattern server serving the identical reference scenario (ticket
handling), the identical eight tasks, backed by one seeded Postgres instance,
and a chart comparing the two. Prove the harness loop against a stub first,
so the three days spent on the real backend and tasks are spent only after
the highest-risk assumption — that the harness can run an agent against a
server this repo owns at all — is confirmed.

## User Stories

1. As the benchmark author, I want to register a new MCP server in the
   service registry, so that the existing pipeline can run an agent against
   it without harness changes.
2. As the benchmark author, I want a control (baseline) server whose tools
   return hardcoded data, so that I can prove the agent loop works before a
   real backend exists.
3. As the benchmark author, I want one real task run end to end against the
   stub server at `--k 1`, so that I get a `TaskResult` with a turn count and
   a token count as evidence the loop works.
4. As the benchmark author, I want a small Postgres-backed HTTP API scoped to
   one namespace (`/tickets`, 6 endpoints), so that both servers front real,
   stateful data instead of stubs.
5. As the benchmark author, I want a seed script that resets and reloads the
   schema per task, so that every task run starts from identical initial
   state.
6. As the benchmark author, I want the control server repointed at the real
   API once it exists, so that the stub is retired rather than kept as a
   second code path.
7. As the benchmark author, I want a pattern server exposing one tool,
   `coordinate_incident`, that performs the create-attach-assign-notify
   sequence in a single call, so that the Tool Orchestrator module has a
   server to measure.
8. As the benchmark author, I want eight tasks written once and run against
   both servers, so that the only variable between the two runs is the MCP
   surface, not the task content.
9. As the benchmark author, I want no task's `description.md` to name a tool
   from either server, so that the task instructions can't leak which
   surface is easier and bias the agent.
10. As the benchmark author, I want an automated check that fails the build
    if a task description names a tool, so that neutrality doesn't silently
    regress as tasks are edited.
11. As the benchmark author, I want every task's verifier to read final state
    through one shared helper, so that sixteen verifiers (eight tasks × two
    servers) don't each reimplement Postgres access.
12. As the benchmark author, I want each verifier kept small (target ~15
    lines), so that a verifier is reviewable as "did the right row exist,"
    not a second implementation of the task.
13. As the benchmark author, I want three runs of both servers against all
    eight tasks at a fixed model, so that the two-server comparison isn't a
    single noisy sample.
14. As the benchmark author, I want the three runs aggregated into success
    rate, turn count and input tokens per server, so that I can read the
    difference the pattern module produced.
15. As the benchmark author, I want a gate rule that stops the project if the
    control passes all eight tasks on all three runs, so that I don't spend
    eight more days building four modules that will show flat lines against
    a control with no headroom.
16. As the benchmark author, if the gate fails, I want to rerun only the
    eight tasks against a smaller model rather than rewrite them, so that the
    already-written tasks stay the fixed variable and the model is the cheap
    one to change.
17. As the benchmark author, if the smaller model then fails the control
    entirely (0 of 8 on both servers), I want that identified as a task
    problem, not a model problem, so effort goes to rewriting tasks rather
    than trying a third model.

## Implementation Decisions

- **Sequencing**: the control server is stood up against hardcoded stub data
  first and run through the full pipeline at `--k 1` before any backend work
  starts. This step's only success criterion is a `TaskResult` coming back
  with a turn count and a token count populated — content correctness is not
  in scope for this step. Everything downstream (real backend, pattern
  server, all eight tasks) is written only after this passes.
- **Backend**: one Postgres instance behind one small HTTP API, run under
  Docker Compose, seeded fresh per task via a seed script. Only the
  `/tickets` namespace is built for this phase (6 endpoints: list, create,
  get, update, add comment, add attachment). This matches ADR
  `0005-synthetic-backend`.
- **Baseline server** (the "control" in ADR `0002-baseline-pairing`): a flat
  1:1 wrapper, one tool per endpoint (6 tools), vendor-named, unnamespaced,
  raw JSON payloads, HTTP status codes surfaced as error text. Its stub
  version and its real-backend version share the same tool surface — only
  the data source changes when the real API comes online.
- **Pattern server**: one tool, `coordinate_incident`, that performs create
  incident → attach evidence → assign owner → post notification as one
  server-side sequence instead of four agent-driven calls.
- **Service registration**: both servers register as separate entries in the
  existing service registry, following the pattern the harness already uses
  for every other service — no new registration mechanism.
- **Tasks**: eight tasks under a `tool_orchestrator` module, `standard`
  suite, each with a task-instruction file and a verification script. Both
  servers run the identical eight; no per-server task variants.
- **Task neutrality**: enforced by convention (no tool name in any
  instruction file) and checked by an automated test that scans every
  instruction file against both servers' tool name lists and fails the build
  on a match.
- **Verification**: every verifier reads final state through one shared
  Postgres-reading helper rather than each opening its own connection or
  query logic. Target size is a guideline (~15 lines per verifier) to keep
  verifiers reviewable, not a hard limit enforced by tooling.
- **Experiment shape**: 3 runs × 2 servers × 8 tasks = 48 agent runs at one
  fixed model, aggregated by the harness's existing results aggregator into
  per-server success rate, turn count, and input tokens. This follows ADR
  `0004-no-composite-score` — the three metrics are reported side by side,
  never blended.
- **Gate decision**: if the baseline passes 8/8 across all 3 runs, that
  signals no headroom for the pattern server to show improvement against.
  The recovery path is to rerun only the aggregation/run step against a
  smaller model with the same eight tasks, not to rewrite tasks. Only if the
  smaller model then fails the baseline entirely (0/8 on both servers) does
  that become evidence the tasks themselves are too hard and need rewriting.

## Testing Decisions

- A good test here checks external behavior — did the harness produce a
  `TaskResult`, did the verifier find the expected row in Postgres, does a
  task description leak a tool name — never internal call sequences or how a
  tool is implemented.
- **Harness/pipeline seam** (existing, no changes needed): running
  `python -m pipeline --mcp <server> --k N` and reading the resulting
  `TaskResult`'s success flag, turn count, and token usage is the seam for
  both the Phase-1a stub proof and the full 8-task comparison in 1e. This is
  the harness's current top-level seam for every service; Tool Orchestrator
  reuses it rather than adding a new one.
- **Verifier seam**: the shared Postgres-state-reading helper is the one
  place task verification logic touches the database. Both the stub-era
  verifiers (once the real backend lands) and steady-state verifiers go
  through it, so a change to how state is read only happens once.
- **Task-neutrality seam**: a single static test scans all instruction files
  in the module against both servers' declared tool names. This is a
  repo-hygiene gate, not a behavioral test — it has no fixtures and no setup,
  just a string containment check per file.
- Prior art: the harness already has per-service task discovery and a
  `TaskResult`/aggregation pipeline exercised by every existing (now-deleted)
  service; Tool Orchestrator's tests follow that same shape rather than
  introducing a new testing convention.

## Out of Scope

- Domain-Specific Adapter, Stateful Session Server, Proxy Aggregator, and
  Resource Gateway (Phases 2–5) — each is its own follow-on phase.
- Code-First Hybrid Adapter — deferred for the first release per ADR
  `0003-defer-code-first-hybrid`.
- Any backend namespace beyond `/tickets` (`repos`, `runbooks`, `deploys`
  come with later phases).
- The README results table and chart (Phase 6) — this phase produces the
  chart described in step 1e as a working check, not the final published
  artifact.
- Harness changes — Tool Orchestrator is deliberately the module that needs
  none, unlike Resource Gateway's later `list_resources`/`read_resource`
  addition.

## Further Notes

- This phase's own plan already anticipates its exit criteria as a gate, not
  just a "done" checkbox — the spec should be read together with the gate's
  two recovery paths (smaller model, then task rewrite) as part of the
  definition of done, not as a separate contingency.
- No issue tracker or triage label vocabulary was configured in this session
  (no git remote, no tracker setup), so this spec was written to
  `docs/specs/` instead of being filed and labeled `ready-for-agent`. Once a
  tracker is available (e.g. via `/setup-matt-pocock-skills`), file this
  spec's content as the issue and apply that label.
