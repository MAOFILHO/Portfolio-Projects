# 01: README report — table, chart, limitations

**What to build:** Phase 6 per `docs/PLAN.md`: one table (5 rows, control vs.
pattern for 3 metrics), one grouped bar chart (5 modules, 3 bars each for
percent change), and a limitations section, all in the top-level README.

**Status:** done

- [x] Table: 5 modules, control and pattern success rate / turns / input
      tokens, sourced from each module's locked ticket 03/04/05 gate result
      (`.scratch/*/issues/03-*.md`, `04-*.md`, `tool-orchestrator/05-*.md`)
- [x] Chart: grouped bar, 5 modules on x, 3 bars each (success rate / turns /
      input tokens percent change, pattern vs. control) — `docs/phase6_chart.py`,
      written to `docs/phase6-chart.png`, embedded in the README
- [x] Limitations: 1 model, 8 tasks/module, synthetic backend, Code-First
      Hybrid Adapter not built, re-run crash count (0, none recorded across
      any module's gate ticket)
- [x] README status line updated from "Phase 0 of 6 complete" (stale) to
      "complete, all 6 phases done"

**Data source, not re-aggregated:** the 5 modules' numbers come from each
module's own gate ticket, already reviewed and marked done — not re-read from
`results/`, which is gitignored and may not exist in a fresh clone. Hardcoded
into `docs/phase6_chart.py` with a source comment; the chart script carries
its own `demo()` self-check on the percent-change math (ponytail: non-trivial
loop logic gets one runnable check).

**Two results run against ADR 0004's stated expectation** (a pattern module
changes cost, not possibility): Stateful Session Server costs slightly more
turns/tokens than its control, and Proxy Aggregator costs more *and* succeeds
less. Both are already flagged as "negative findings, not averaged in" in
their own gate tickets (Phase 3 ticket 03, Phase 4 ticket 03) — this ticket
carries that framing into the README rather than re-litigating it.

**Phase 6 is complete. All 6 phases done.**
