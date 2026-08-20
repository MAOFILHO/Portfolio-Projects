# Azure-Banking-Voice-Agentic-AI — scoping handoff — 2026-08-19

Project: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI` (monorepo root:
`/Users/marco/K21/Real-world`, working branch `azure-banking-voice-agentic-ai`).

This file is a map, not a source of truth. Everything it points at can drift; this file itself will
not be updated again — re-read the pointed-to files, don't trust this doc's prose over them.

## Read first, in this order

1. `CLAUDE.md` — stop conditions (top of file), the B1–B5 constraint table, hard exclusions, the
   `PROJECT_STATE.md` size ceiling, model/context policy, skill discipline. Restate the stop
   conditions verbatim at the top of the first response in a new session.
2. `docs/PLAN.md` — the actual scope: reuse-reality findings against the two seed repos, all 18
   settled decisions, the B1–B5 constraints in full (fail-closed test cases, B3's startup guard,
   B5's two-stage measurement plan), architecture, region/residency (ADR-001/002, to be written as
   real files in `docs/adr/` during Phase 0), the budget (including the eval-budget ceiling), project
   layout, testing strategy, the full Phase 0–8 plan, and the R-01…R-08 tracked risks.

## Where things stand

**Nothing is built yet.** This handoff exists at the boundary between scoping and Phase 0, not
between two phases of implementation. Specifically:

- No code, no `infra/`, no `tests/`, no `Makefile`, no `pyproject.toml` exist yet — `docs/PLAN.md`
  section "Project layout" is the target shape, not the current one.
- `PROJECT_STATE.md` does not exist yet. It gets created when Phase 0 actually starts, sized per
  decision 18 (`CLAUDE.md`) from day one — do not let it grow past ≤400 lines/~20 KB even at
  creation.
- `docs/adr/` does not exist yet. ADR-001 (data residency) and ADR-002 (geography knobs) are written
  **during Phase 0** (step 9), not deferred — their content is already drafted in `docs/PLAN.md`
  under "Region & data residency" and just needs to become real files.
- The Azure subscription (`960936b9-ecde-465b-be8d-776ca077dcd0`, PayAsYouGo, `spendingLimit: Off`)
  is bare — zero resource groups, zero Cognitive Services accounts. `Microsoft.Communication` is
  **not registered**; that's Phase 0 step 1.
- No phone number is leased yet.

## What Phase 0 actually is

Provisioning + a real meter/latency spike, run via `/wizard` because it needs a human on a phone —
Marco dialing from Ontario. Full 11-step list and exit gate: `docs/PLAN.md`, Phase 0.

**The one thing to watch closely:** R-08 (demonstrability). Phase 0 step 10 computes, from
*measured* meters (not the plan's estimate), how many full demo runs/month the budget actually
supports. If that number comes in under 5, **stop — do not proceed into Phase 1** — and go back to
Marco about reducing fixed cost or raising the ceiling.

## Known open risks going into Phase 0

All eight are in `docs/PLAN.md` under "Tracked risks" with their fallback. The ones Phase 0 is
directly built to resolve: R-01 (conflicting retirement dates on `gpt-realtime-mini` — verify via
Models API), R-02 (whether `Pcm24KMono` really delivers clean 24kHz both ways — the resampler was
deleted on a documentation claim, not a measurement), R-03 (`DtmfData` during active streaming),
R-04 (Container Apps idle-vs-active billing over 72h), R-05 (narrowed to: which Toronto-area area
codes are actually in live inventory), R-06 (whether DataZone is even offered for realtime models),
R-08 (demonstrability, above).

## Note on `/handoff`

No `/handoff` skill is registered in this environment (checked `~/.claude/commands` and this
project's `.claude/`, both empty of it) — this file was written by hand, following the format
`AWS-Insurance-FNOL-Voice-Agentic-AI/docs/handoffs/` already uses. If a `/handoff` skill exists
elsewhere, point it at this convention.
