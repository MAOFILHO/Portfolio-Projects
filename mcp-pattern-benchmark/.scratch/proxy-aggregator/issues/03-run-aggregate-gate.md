# 03: Run, aggregate, apply the gate

**What to build:** 3 runs x 2 servers x 8 tasks at a fixed model, aggregated
into success rate, turn count and input tokens, with the gate rule applied.
Mirrors Phase 1 ticket 05 / Phase 2 ticket 03 / Phase 3's equivalent.

**Blocked by:** 02

**Status:** done

- [x] Both servers run 3x against all 8 tasks at gpt-4.1-mini
- [x] Results aggregated per server (success rate, turns, input tokens)
- [x] Gate condition (control `proxy_wrapper` 8/8 across all 3 runs) checked
      against actual results — not met, see table below
- [x] Gate not triggered -> no smaller-model recovery run needed (see
      Decision below for why)

**gpt-4.1-mini** (`results/phase4-gate/`, gitignored), 3 runs x 8 tasks:

| Server | Success rate | Avg turns | Avg input tokens/task |
|---|---|---|---|
| proxy_wrapper (control) | 16/24 (66.7%) | 7.38 | 14,432.7 |
| proxy_aggregator | 9/24 (37.5%) | 18.29 | 27,681.0 |

**Gate not triggered:** control never reached 8/8 on any of the 3 runs
(6/8, 5/8, 5/8) — no ceiling, so the recovery path (smaller model, same 8
tasks) was not needed.

## The honest result

**This module's live numbers repeat and sharpen ticket 01's and ticket
02's warning, they don't newly discover it.** Every failure on both
servers traces to the same gap carried forward from ticket 02: neither
server can resolve a repo name or a change-request title to its numeric
id, so the agent has to guess among 4 repo ids or 8 change-request ids.
That cost lands on both servers, but far harder on `proxy_aggregator`:
2.5x the turns (18.29 vs 7.38) and 1.9x the input tokens (27,681 vs
14,433) per task, because a wrong guess costs an extra `call_tool` error
round-trip on top of the wrong-id round-trip the control also pays, and
`discover_tools` adds turns before any guessing even starts.

**Decision: ticket 02's Option B stands.** The id-guessing gap depresses
both servers' pass rates, so the control-vs-pattern comparison stays fair
even though neither number is clean — same reasoning that justified not
reopening ticket 01 for a lookup tool. But unlike Phase 2/3's gate
recoveries (a *secondary* signal from a deliberately harder model), this
result is Phase 4's *primary* gpt-4.1-mini data, and it's a clear negative
finding: `proxy_aggregator` costs more AND succeeds less than its own
control on the identical 8 tasks. Phase 6 reports gpt-4.1-mini per ADR
`0004-no-composite-score`, same as every other phase, but its limitations
section should state this module's result as a negative finding, not
average it in with the modules that showed the predicted direction.

**Phase 4 is gated and complete.**

## Comments
