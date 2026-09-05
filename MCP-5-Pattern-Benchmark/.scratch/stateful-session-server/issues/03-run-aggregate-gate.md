# 03: Run, aggregate, apply the gate

**What to build:** 3 runs x 2 servers x 8 tasks
(`python -m pipeline --mcp session_baseline ...` /
`--mcp session_server ...`), aggregated with
`src.aggregators.aggregate_specific_results`, then the same gate rule
Phase 1/2 used: stop and drop to a smaller model if the baseline passes 8/8
on all 3 runs.

**Status:** done

- [x] Both servers run 3x against all 8 tasks at gpt-4.1-mini
- [x] Results aggregated per server (success rate, turns, input tokens)
- [x] Gate condition (baseline 8/8 across all 3 runs) checked against
      actual results
- [x] Gate triggered -> same run/aggregate step repeated at gpt-4.1-nano,
      same 8 tasks, outcome recorded

**gpt-4.1-mini** (`results/phase3-gate/`, gitignored), 3 runs x 8 tasks:

| Server | Success rate | Avg turns | Avg input tokens/task |
|---|---|---|---|
| session_baseline (control) | 24/24 (100%) | 5.75 | 6,563.2 |
| session_server | 24/24 (100%) | 5.96 | 6,970.3 |

**Gate triggered:** control 8/8 on all 3 runs -> no headroom at this model.
Recovery path applied per spec: rerun against a smaller model, same 8
tasks.

**gpt-4.1-nano** (`results/phase3-gate-recovery/`, gitignored), 3 runs x 8
tasks:

| Server | Success rate | Avg turns | Avg input tokens/task |
|---|---|---|---|
| session_baseline (control) | 11/24 (45.8%) | 4.00 | 4,444.5 |
| session_server | 15/24 (62.5%) | 5.88 | 7,161.6 |

Not 0/8 on both servers -> no task rewrite triggered. Nano's turn counts
aren't directly comparable to mini's: a chunk of nano's baseline runs fail
by giving up early rather than completing, which drags its average turn
count down without meaning the surviving path was more efficient.

## The honest result

**This module does not confirm ADR 0007 at gpt-4.1-mini, the model Phase 6
reports.** `session_server` cost *more* turns and *more* input tokens than
its own baseline on the identical 8 tasks — the opposite of "the pattern
server should cost less because it never resends state." Carried in from
Ticket 02's live spot-check and confirmed by the full 3-run aggregate, not
a fluke of one task: `start_review` is a mandatory extra tool call the
baseline never needs, and every tool call resends the entire conversation
as input tokens regardless of how large that call's own arguments are. At
2-3 comments per review, the baseline's resend-argument bloat (a few dozen
words repeated) is small next to that fixed per-turn cost. ADR 0007's
resend-cost thesis needs either a task with many more comments per review,
or a different metric than raw input tokens, to become visible — neither
is in scope for this phase.

The nano recovery run adds a real but secondary positive signal:
`session_server`'s success rate held up better under a weaker model
(62.5% vs. baseline's 45.8%) — a session's smaller per-call decision (one
comment at a time) seems to be easier for a weak model to get right than
resending a growing, exact list. That is a genuine property of the
pattern, just not the one ADR 0007 or this module's `CONTEXT.md`
description ("holds working state ... instead of forcing the agent to
resend it") set out to measure.

**Decision: Phase 6 reports gpt-4.1-mini**, same call as Phase 1/2 for the
same reason (ADR `0004-no-composite-score`) — but unlike Phase 1/2, that
mini result here is a **negative finding for the pattern module**: at
this task's scale, the baseline is both cheaper and (at mini) equally
reliable. Phase 6's limitations section should say so plainly rather than
folding it into an average with the four modules that *did* show the
predicted direction.

**Phase 3 is gated and complete.**
