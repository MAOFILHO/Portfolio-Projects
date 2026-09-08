# Handoff — Phase 2 signed off, Phase 3 (mock-core-banking) next

**2026-09-08**, Azure-Banking-Voice-Agentic-AI, branch `azure-banking-work`.

## STOP CONDITIONS — absolute, no exceptions (restated verbatim, CLAUDE.md)

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling
  (≤400 lines/~20KB — currently 211 lines/~15.5KB).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## Where things actually are — verify before trusting this doc

**Canonical path**: `/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`,
branch `azure-banking-work`. If a fresh session lands anywhere else, stop and say so — don't
silently continue or relocate (CLAUDE.md's own opening section, and this project's history has
already had one session start from the wrong place).

Per CLAUDE.md's resume discipline: **verify live Azure state before acting on `PROJECT_STATE.md`**,
don't trust either source blindly. As of this session's end:
- `ca-azbank-echo-p0` running image `docker.io/maofilho/azbank-echo-p0:p3`, revision `--0000002`,
  `Healthy`, 100% traffic. Managed identity (`5e09fe34-8913-4aa2-80ac-618af308a88f`) + `Reader` RBAC
  on `aoai-azure-banking-voice-cc` only.
- Local `HEAD` (`62a7143`) confirmed matching `origin/azure-banking-work` via
  `gh api repos/MAOFILHO/Portfolio-Projects/branches/azure-banking-work` (this sandbox's SSH key is
  missing — pushes go via `git push https://github.com/...` directly, `git fetch origin` will still
  fail over SSH, that's expected, not a new problem).
- **The live log-stream endpoint (`az containerapp logs show --follow`/`--tail`) is unreachable from
  Marco's network entirely** — confirmed from both a Claude Code session and his own terminal
  independently (TCP connect to `canadacentral.azurecontainerapps.dev:443` times out). Cause
  unknown, not yet resolved. Use `az monitor log-analytics query --workspace
  bf520f2c-e2bc-4488-8965-9317a7922c74` instead (the actual live workspace — see below).
- **There are three Log Analytics workspaces, not two** as `PROJECT_STATE.md` said before this
  session: `...aiCS` (documented "real", actually stale since 2026-08-25) and `...aixC` (orphan)
  were the only two on record; the diagnostic setting actually targets a third, previously
  undocumented one, `workspace-rgazurebankingvoiceagenticai1D`
  (`bf520f2c-e2bc-4488-8965-9317a7922c74`). Query that one for anything current.

## What happened this session

Resumed mid-Phase-2. In order:

1. `#20` (declarative agent table + mid-call handoff) reviewed via `/code-review`, one real gap
   found and fixed via TDD (`e33edea`) — `handoff_target()` now checks the *calling* agent's own
   declared edges, not just that the target exists. All 7 of Phase 2's built tickets reviewed and
   fixed as of `57b2761`.
2. Branch pushed (HTTPS workaround, no SSH key here). Managed identity + `Reader` RBAC added to
   `ca-azbank-echo-p0`, confirmed via `az role assignment list --scope`.
3. Phase 2 image built (Marco's laptop, `docker buildx`) and deployed twice — `:p2` (2026-09-07,
   B3 verified live for the first time from real container logs), then `:p3` (2026-09-08, adds B5
   latency logging).
4. **8 real phone calls placed** (`+17059100383`). Findings, all timestamps, and per-call detail:
   `docs/phase2/evidence/b5-call-log.md`. Headline results: handoff and gate-refusal both proven
   live for the first time; a review-fix scenario (hallucinated re-handoff) fired for real on
   Call 1 and was correctly refused; a real B5 instrumentation gap was found (no turn-latency
   timestamp pair existed at all) and fixed (`42e02c5`, redeployed as `:p3`); a ~2.5-11s dead-air
   gap before the agent speaks first was found and confirmed real (still open, not fixed — see
   below).
5. **`scripts/b5_probe.py` built** — an AOAI-direct automated latency harness (real
   `connect_realtime()`, no ACS/phone), built after Marco asked whether ~20 more real calls was
   really the only way to reach B5's N≥100 bar. Found and fixed a real bug before any sample
   existed (synthetic transport gave the server's VAD nothing to detect silence from). A 75-call
   batch produced 74 valid samples; every outlier traced to the same transfer-intent utterance —
   independent confirmation of `docs/PLAN.md`'s own prediction that tool calls are the slowest leg.
6. **B5's provisional figure landed: p95=932ms, N=106** (31 real calls + 75 probe, both pools
   stated together per CLAUDE.md's "any p95 states its N" rule, not silently merged).
7. `/code-review` run (fixed point `57b2761..HEAD`, spec = GitHub issue #24). Two real Spec-axis
   gaps found and fixed same session: operating mode was never re-measured after the calls (fixed
   — IDLE reconfirmed via R-04's own method, `docs/phase2/evidence/b5-call-log.md`'s "R-04
   reconfirmation" section); `#20`/`#21` were functionally done but never formally closed on
   GitHub (fixed — both closed with evidence citations).
8. **Marco signed off: "Phase 2 approved."** All three of Phase 2's stated exit criteria
   (`docs/PLAN.md`'s Phase 2 Exit line) are met.

Full narrative detail for any of the above: `PROJECT_STATE.md`'s "#24 — B5 call log" section (compact)
and `docs/phase2/evidence/b5-call-log.md` (full). Don't re-derive what's already written there.

## Open items carried forward (none block Phase 2's close)

- **Dead air before the agent speaks first**, every real call (2.5-11s) — `session.py` sends no
  initial `response.create`; the greeting only happens once the caller talks first. Not fixed,
  Marco's call on whether/when.
- **R-08's demo-runs/month figure is stale** (79.2, from Phase 0) against the reconfirmed IDLE
  verdict — needs recomputing, not exit-blocking.
- **Minor Standards-axis smell, not fixed** (explicitly out of scope this session — Marco asked
  only for the two acceptance-criteria gaps): `scripts/b5_probe.py`'s `_chunk_to_frames` and
  `_silence_frames` both compute the same frame-byte-size expression and build the identical frame
  dict — extract a shared helper if anyone's back in that file.
- **`b5_probe.py`'s fixed 6-second tail wait is sometimes too short** for transfer-heavy exchanges
  (1 of 75 batch calls got no response within it) — known limitation, not investigated further,
  there was already enough data without fixing it.

## Next: Phase 3 — mock-core-banking

Scope is already written, `docs/PLAN.md`'s "Phase 3 — mock-core-banking" section — don't
re-scope from scratch, read it first. One-line summary: FastAPI + SQLite, own Container App, own
Dockerfile, timeouts/retries/circuit-breaking in the client, `T-UNKNOWN-ACCT`. The real network
path this phase introduces sits behind Phase 2's gate from the moment it exists.

Per CLAUDE.md's model policy: **Opus for this phase's kickoff** (design, exit-criteria authoring)
before implementation starts — don't jump straight into Sonnet build work.

## Suggested skills for the next session

- **`/research`** if any factual unknown comes up during Phase 3 design (pricing, a new Azure
  resource's region/SKU availability, anything not already verified in `docs/PLAN.md`). This
  project has been burned once already by an unverified assumption — don't answer from memory.
- **`/wizard`** only if Phase 3's kickoff turns up a human-in-the-loop provisioning step (a new
  Container App, a new resource group decision) — not needed for the mock-service code itself.
- **`/code-review`** before Phase 3's own exit gate, same two-axis process used this session
  (Standards + Spec, spec = the Phase 3 GitHub issue once filed).
- **`/prototype`** only if a genuine design question comes up (e.g., exact circuit-breaker
  behavior) — not a substitute for reading `docs/PLAN.md`'s existing scope first.
- **`/handoff`** at the next phase boundary — remember to copy its temp-dir output into
  `docs/handoffs/` and commit before `/clear` (CLAUDE.md: `/handoff` itself never writes into the
  repo, that's a deliberate skill behavior, not a bug — the copy-and-commit step is what makes
  "unwritten handoff outstanding" actually mean something on macOS's periodically-cleaned `/tmp`).

## Before `/clear`

This doc must be copied into `docs/handoffs/` and committed before the session ends — not done
yet as of writing this file. Do that now, in the current session, before clearing.
