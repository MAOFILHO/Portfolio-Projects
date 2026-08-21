# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 0, Stage 10 done, Stage 11 generated (uncommitted)

Date: 2026-08-20. Canonical path: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, inside
the `Portfolio-Projects` monorepo, branch `azure-banking-voice-agentic-ai`.

## Read first, in order

1. `CLAUDE.md` (project root) — operating rules, stop conditions, restate them verbatim before acting.
2. `PROJECT_STATE.md` (project root) — current-state snapshot, ≤400 lines/20KB by design. Trust the
   git log over its prose for exact detail; it's deliberately terse (decision 18).
3. `docs/PLAN.md` — source of truth for scope/architecture/budget/risks. Don't re-litigate its
   decisions or tracked risks (R-01…R-09) without new evidence.
4. `docs/phase0/findings.md` — the evidence backing every risk resolution this phase. Long; read the
   section headers, not necessarily every line.
5. `git log --oneline -20` — this session's actual commits are the precise record of what changed;
   PROJECT_STATE.md is a summary, not the primary source.

## STOP CONDITIONS — restate verbatim, per CLAUDE.md, at the top of every session summary/after /compact

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).
- **The phone number (`+17059100383`) is never released, by any script, at any phase, for any
  reason.** No teardown path may include a number-release/delete call.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling.

## Where things stand

**Phase 0, Stage 10 of 12 complete and committed.** Stage 11 (echo app) has been generated to disk but
is **deliberately uncommitted** — Marco asked to review the code before it's built/deployed (Stage 12),
and the session ended (handoff requested) before he gave that go-ahead.

Resources that exist and bill: resource group, AOAI resource + `gpt-realtime-mini` 2025-10-06
deployment (consumption-only, $0 idle), ACS resource (consumption-only, $0 idle), phone number
`+17059100383` ($1.00/mo, purchased, R-09 protected — never release it). Nothing hourly-billed exists
yet — that starts at Stage 12.

**Uncommitted on disk right now:** `docs/echo-app/{app.py,requirements.txt,Dockerfile}` — generated
verbatim from `01-provision.sh`'s Stage 11 heredoc, matches what Stage 12 would actually build. Marco
was mid-review of this when the session ended. **Do not commit these without his sign-off on the code
itself** — that review was the explicit reason the session stopped short of Stage 12.

One live finding surfaced this session, not yet actioned: `app.py`'s WS handler logs the raw DTMF tone
value on every digit (`log.info("DTMF tone=%s arrived...", ...)`). Harmless in Phase 0 (no PIN/auth
exists yet), but this exact line cannot survive into Phase 2 unmodified once DTMF-PIN entry exists —
B2 forbids the PIN in any log line. Flagged to Marco, not yet fixed (nothing to protect yet). Worth
remembering when Phase 2's design starts.

## Immediate next step

**Do not act — wait for Marco's word on the echo app.** Likely next messages are either "looks good,
go" (→ run/replicate Stage 12: build, push to Docker Hub as **Private**, deploy to Container Apps,
`min-replicas=1, 0.25 vCPU/0.5GiB`) or requested changes to `docs/echo-app/`.

**Stage 12 is the next billable-per-hour resource and starts R-04's 72h idle-observation window and
the clock `03-cost-check-24h.sh`/`04-teardown-and-r08.sh` depend on.** State the rate before it fires:
~$0.00588/hr idle – ~$0.0196/hr active (Container Apps Consumption plan, sourced from the pricing
calculator API, `docs/PLAN.md` Budget section + a live Retail Prices API spot-check this session
confirming no rate drift).

**Timing note already resolved this session, don't re-derive it:** `02-test-calls.sh` (3 real test
calls) should run in the **same sitting as Stage 12**, immediately after — its own header says so
("run this today, right after 01-provision.sh succeeds"), and `PROVISION_TIME` (written at Stage 12,
anchoring R-04's 72h window) means calls held for later would land mid-window and invalidate the idle
read. `03-cost-check-24h.sh`'s own 24h check is non-blocking/informational regardless of call timing —
don't let that fact cause the calls to be deferred; R-04/script 4 is the actual constraint.

## What NOT to re-litigate (already decided, with evidence)

- **Decision 13**: number is 705 (North Bay/Sault Ste Marie, ON), not Toronto — Toronto is genuinely
  absent from ACS's entire Canadian geographic inventory (`docs/phase0/findings.md`, "R-05").
- **R-06**: DataZoneStandard confirmed NOT offered for `gpt-realtime-mini` 2025-10-06 (exact error in
  `docs/adr/ADR-001-data-residency.md`).
- **R-09** (number irreplaceability): ACS's Canadian number inventory is volatile on a ~20min
  timescale (10→8 localities observed in one session) — this is *why* the number is never released,
  not a cost consideration.
- **B3 promoted**: the startup guard must key on (deployment name, model version) together and read
  the live deployment's version at boot, not trust config alone (`docs/PLAN.md`'s B3 code block,
  `CLAUDE.md`'s constraints table).
- **ADR-001/ADR-002** (`docs/adr/`): already written, already reflect the real findings (R-05/R-06),
  not the original assumptions they set out to test. Don't rewrite them without new evidence.
- **Concurrent-session git risk**: this monorepo's working tree is shared with at least one other
  active session (`AWS-Insurance-FNOL-Voice-Agentic-AI`). Its files have shown up staged/modified in
  `git status` multiple times this session without being touched. **Always run `git status --short`
  before `git add`, and stage explicit paths — never `git add -A`/`git add .`.** Worktree separation
  per project was agreed but deliberately deferred to after Phase 0 completes.

## Open items carried forward (full detail in PROJECT_STATE.md's "Open items")

1. Docker Hub vs ACR — deliberate decision due at Phase 1 kickoff, not before.
2. Rate-limit interpretation (Models API's `10 req/60s`) — still not confirmed via the Foundry portal's
   Quota page; cheap, ~30s, just not done yet.
3. `gpt-realtime-1.5` successor path untested — Phase 2 deliverable (`T-B3-SUCCESSOR-BOOT`), needs
   `FakeRealtimeServer` which doesn't exist yet either.
4. Free-tier suppression check — Stage 1 of `03-cost-check-24h.sh`, portal-only, not yet run (no
   resources billing long enough to check).
5. Git worktree separation — agreed, deferred to after Phase 0.

## Suggested skills for the next session

- **`/wizard`** — Phase 0 is explicitly a wizard-driven phase (human-in-the-loop: dialing a real
  phone, Docker Hub credentials, portal-only checks). Resume via the existing
  `docs/phase0/wizard/01-provision.sh` (Stage 12 onward) and `02-test-calls.sh`, not a new design.
- **`/code-review`** — due before Stage 12 fires if Marco requests it on `docs/echo-app/`, and again
  at Phase 0's exit gate before `/handoff` + `/clear` into Phase 1. Per `CLAUDE.md`'s skill-discipline
  section, only invoke on Marco's explicit request, not proactively.
- **`/research`** — if any further factual Azure/ACS question comes up (pricing, API shape, SDK
  signature) — this project has a standing "never answer from memory" rule after being burned by
  exactly that once (R-01) and finding several more stale assumptions live this session (stale
  api-versions, a nonexistent CLI subcommand). The `MediaStreamingOptions` SDK field/enum names in
  `docs/echo-app/app.py` are explicitly flagged in the script's own header as unverified against the
  installed package version — worth a `/research` pass before Stage 12 builds the image, not after.

## Do not do

- Don't run Stage 12 (or anything past Stage 11) without Marco's explicit go-ahead on the echo app.
- Don't commit `docs/echo-app/` without that same sign-off.
- Don't `git add -A`/`git add .` in this monorepo — stage explicit paths only (see concurrent-session
  note above).
- Don't release the phone number, ever, under any script or phase (R-09).
- Don't skip restating the stop conditions verbatim at the start of the next session or after any
  `/compact`.
