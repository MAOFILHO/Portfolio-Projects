# 04: Run, aggregate, apply the gate

**What to build:** 3 runs x 2 servers x 8 tasks at a fixed model, aggregated
into success rate, turn count and input tokens, with the gate rule applied.
Mirrors Phase 2 ticket 03 / Phase 3 ticket 03 / Phase 4 ticket 03.

**Blocked by:** 03

**Status:** done

- [x] Both servers run 3x against all 8 tasks at the chosen model
- [x] Results aggregated per server (success rate, turns, input tokens)
- [x] Gate condition (control `resource_wrapper` 8/8 across all 3 runs)
      checked against actual results — not met, see table below
- [x] Gate not triggered -> no smaller-model recovery run needed (see
      Decision below for why)

**gpt-4.1-mini** (`results/phase5-gate/`, gitignored), 3 runs x 8 tasks:

| Server | Success rate | Avg turns | Avg input tokens/task |
|---|---|---|---|
| resource_wrapper (control) | 10/24 (41.7%) | 2.88 | 2,814.2 |
| resource_gateway | 15/24 (62.5%) | 4.08 | 2,559.3 |

**Gate not triggered:** control never reached 8/8 on any of the 3 runs
(4/8, 4/8, 2/8) — no ceiling, so the recovery path (smaller model, same 8
tasks) was not needed.

## The honest result

**This module's result runs the opposite direction from Phase 4's.**
Spot-checked failures on both servers trace to the same pre-existing gap
carried from ticket 01/02: neither surface gives the agent a way to
resolve a repo name (e.g. "checkout-web") to its numeric `repo_id`, so
`list_runbooks`/`search_runbooks` gets a guessed id and returns the wrong
repo's runbooks. That gap depresses both servers, same as Phase 2-4's
accepted limitation — but here `resource_gateway` clears it more often
(5/8 on every one of its 3 runs) than `resource_wrapper` does (4/8, 4/8,
2/8, and never the same 3 tasks twice). A plausible mechanism, not fully
traced across all 24 task-runs: `list_resources` surfaces every runbook's
title at connect time for free, giving the agent a discovery path the
control's blind `list_runbooks(repo_id)` tool call doesn't have — worth a
deeper look if this module gets revisited, but out of scope here.

**Decision: ticket 01/02's choice not to add a repo lookup tool stands.**
The gap still depresses both servers' pass rates, so the comparison
stays fair even though neither number is clean — same reasoning as
Phase 4. Unlike Phase 4, though, this is a genuine positive finding for
the pattern module: `resource_gateway` succeeds more (62.5% vs 41.7%)
*and* costs slightly less per task (2,559 vs 2,814 input tokens) than its
own control, on the identical 8 tasks. Phase 6 should report this
module's result as a positive finding, not average it in with Phase 4's
negative one.

**Phase 5 is gated and complete.**

## Comments
