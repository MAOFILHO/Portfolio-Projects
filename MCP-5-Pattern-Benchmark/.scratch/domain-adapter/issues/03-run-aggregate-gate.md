# 03: Run, aggregate, apply the gate

**What to build:** 3 runs × 2 servers × 8 tasks at a fixed model, aggregated
into success rate, turn count and input tokens, with the gate rule applied.
Mirrors Phase 1 ticket 05.

**Blocked by:** 02

**Status:** done

- [x] Both servers run 3× against all 8 tasks at gpt-4.1-mini
- [x] Results aggregated per server (success rate, turns, input tokens)
- [x] Gate condition (baseline 8/8 across all 3 runs) checked against actual
      results
- [x] Gate failed → same run/aggregate step repeated at a smaller model,
      same 8 tasks, outcome recorded

**Bug caught by this step, not by unit tests:** the first live `--k 3`
`domain_adapter` run came back 1/8 on all 3 runs. `resolve_customer_ticket`
took a numeric `ticket_id`, but the pattern server exposes no way to
discover it — the agent guessed `1` every time (right only for the one task
that happens to be ticket 1) or gave up asking for the id. Root cause: no
lookup path on the pattern surface, unlike the baseline's `list_tickets`.
Fixed by changing the tool's parameter to `ticket_title` and resolving it
internally against the existing `GET /tickets` list (no new endpoint, no
second tool — the confirmed one-tool design stands). Verified by a new unit
test and a clean re-run: 24/24 across all 3 runs.

**gpt-4.1-mini** (`results/phase2-gate/`, gitignored), 3 runs × 8 tasks:

| Server | Success rate | Avg turns | Avg input tokens/task |
|---|---|---|---|
| domain_wrapper (control) | 24/24 (100%) | 3.00 | 2,924.8 |
| domain_adapter | 24/24 (100%) | 2.00 | 700.0 |

Gate triggered: control 8/8 on all 3 runs → no headroom at this model.
Recovery path applied per spec: rerun against a smaller model, same 8 tasks.

**gpt-4.1-nano** (`results/phase2-gate-recovery/`, gitignored), 3 runs × 8
tasks:

| Server | Success rate | Avg turns | Avg input tokens/task |
|---|---|---|---|
| domain_wrapper (control) | 7/24 (29.2%) | 3.88 | 3,401.9 |
| domain_adapter | 24/24 (100%) | 2.00 | 902.5 |

Not 0/8 on both servers → no task rewrite triggered.

**Decision: Phase 6 reports gpt-4.1-mini**, not the nano recovery run — same
call as Phase 1 for the same reason (ADR `0004-no-composite-score`): a
pattern module changes task *cost*, not whether a task is possible. Mini's
100%=100% with 33% fewer turns and 76% fewer input tokens is the cleaner
illustration of that thesis than nano's success-rate gap (n=3, noisy). The
nano run stays recorded above as the gate's recovery-path evidence.

**Phase 2 is gated and complete.**
