# 05: Run, aggregate, apply the gate

**What to build:** Three runs of both servers against all eight tasks at one
fixed model (48 agent runs total), aggregated into per-server success rate,
turn count, and input tokens. The gate decision is then applied: if the
control (`server_wrapper`) passes 8 of 8 on all 3 runs, that's evidence of no
headroom, and the recovery path is a rerun of this same run/aggregate step
against a smaller model with the same eight tasks — not a task rewrite. Only
if the smaller model then fails the control entirely (0 of 8 on both servers)
does that become grounds to rewrite the tasks instead.

**Blocked by:** 04

**Status:** done

- [x] Both servers are run 3 times each against all 8 tasks at the chosen model
- [x] Results are aggregated into success rate, turn count, and input tokens per server, reported side by side (no blended score)
- [x] The gate condition (control 8/8 across all 3 runs) is checked against the actual results
- [x] If the gate fails, the same run/aggregate step is repeated against a smaller model with the same 8 tasks, and that outcome is recorded

Reused `src/aggregators/aggregate_specific_results.py` as-is (per-`<model>__<service>`
directory aggregation already matches this project's results layout) rather
than adapting the legacy `aggregate_results.py`, whose `service_mappings`
assumes one tasks-directory per service -- doesn't fit `wrapper` and
`orchestrator` sharing `tasks/tool_orchestrator/`.

**gpt-4.1-mini** (`results/phase1-gate/`, gitignored), 3 runs x 8 tasks:

| Server | Success rate | Avg turns | Avg input tokens |
|---|---|---|---|
| wrapper (control) | 24/24 (100%) | 3.79 | 2,427 |
| orchestrator | 24/24 (100%) | 2.00 | 809 |

Gate triggered: control 8/8 on all 3 runs -> no headroom at this model.
Recovery path applied per spec: rerun against a smaller model, same 8 tasks.

**gpt-4.1-nano** (`results/phase1-gate-recovery/`, gitignored), 3 runs x 8 tasks:

| Server | Success rate | Avg turns | Avg input tokens |
|---|---|---|---|
| wrapper (control) | 1/24 (4.2%) | 3.67 | 2,401 |
| orchestrator | 23/24 (95.8%) | 2.00 | 962 |

Not "0 of 8 on both servers" (orchestrator succeeds) -> no task rewrite
triggered. Checked a failing wrapper transcript: gpt-4.1-nano hallucinated
task completion without calling any tool at all, on a 4-call task -- a real
capability failure, not a task-design bug. `coordinate_incident`'s 1 call
lets the same model succeed almost every time.

**Decision: Phase 6 reports gpt-4.1-mini**, not the nano recovery run. Per
ADR `0004-no-composite-score`, a pattern module is expected to change task
*cost*, not whether a task is possible -- mini's 100%=100% with 47% fewer
turns and 67% fewer input tokens is the cleaner illustration of that thesis
than nano's dramatic but noisy (n=3, one 7/8 run) success-rate gap. The nano
run stays recorded above as the gate's recovery-path evidence, not as the
headline result.
