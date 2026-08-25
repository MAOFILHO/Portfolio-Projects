# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 0 in progress

**Written**: 2026-08-20, mid-session (not a phase boundary — this is a `/handoff` mid-Phase-0, not the
`/clear`-at-phase-boundary handoff `CLAUDE.md`'s model/context policy describes).

**Project root**: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI` — inside the
`Portfolio-Projects` monorepo (`/Users/marco/K21/Real-world`, remote `origin` =
`git@github.com:MAOFILHO/Portfolio-Projects.git`). Branch: `azure-banking-voice-agentic-ai`.

---

## STOP CONDITIONS — restated verbatim, `CLAUDE.md`'s own requirement

> - No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
> - No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
> - Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
>   (B1) or anything on the DTMF/PIN path (B2). These always get a human look before they land, no
>   matter how mechanical the change appears.
> - `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling (≤400
>   lines / ~20 KB).
> - Restate these conditions verbatim at the top of every session summary and after every `/compact`.

**Marco has typed `APPROVED: Phase 0`** (twice, this session) — the gate is passed for Phase 0 as a
whole. That does **not** mean proceed unsupervised: Marco explicitly asked for a stage-by-stage
walkthrough, stopping at each step, with cost confirmed in `COSTS.md` before anything billable. Keep
that cadence — don't batch remaining stages just because the gate is open.

## ⚠️ Open compliance gap — read first

`PROJECT_STATE.md` **does not exist yet**. Per decision 18 (`CLAUDE.md`, `docs/PLAN.md`) it should be
created "when Phase 0 actually starts" — Phase 0 has now actually started (gate passed, `01-provision.sh`
Stage 1–3 walked). `CLAUDE.md`'s own stop condition requires it updated before any session ends. This
session is ending via `/handoff` without it. **Create `PROJECT_STATE.md` before this session's work is
considered properly closed out** — current phase (0), open items (this doc's list), size ceiling ≤400
lines/~20KB, historical narrative goes to `docs/phase0/`, not into it.

## ⚠️ Git state — read before pushing or opening a PR

- Local branch `azure-banking-voice-agentic-ai` is **2 commits ahead of `origin`'s same branch**:
  `37fc54b`, `6794192` (both docs-only, already verified safe — see "This session's commits" below).
  Push with `git push origin azure-banking-voice-agentic-ai` **from the monorepo root**
  (`/Users/marco/K21/Real-world`), not from inside the project folder — Marco was explicit about this
  more than once.
- `origin/main` is at `c06d985` (merge of PR #5, which Marco opened and merged himself mid-session) and
  is **4 commits behind** the feature branch (`7b92f95`, `6b359fc`, `37fc54b`, `6794192`). No new PR is
  open for these. Don't open one unless Marco asks — he merged #5 on his own initiative last time;
  follow his lead rather than assuming another merge is wanted.
- The Bash tool's own `git push` is denied by this session's permission settings (happened twice). Give
  Marco the exact command to run himself via `!` rather than retrying — he's confirmed that pattern
  works.

## Where things actually stand in Azure

**Nothing billable has been created yet.** Confirmed via live checks this session:
- Subscription `960936b9-ecde-465b-be8d-776ca077dcd0`, correct one, `spendingLimit: Off` confirmed via
  the authoritative ARM API (not the flattened `az account show` field, which showed a misleading `null`).
- `Microsoft.Communication` provider: `Registering` (Marco triggered this himself, outside this
  session — confirmed with him directly, not assumed).
- Resource group `rg-azure-banking-voice-agentic-ai`: does not exist yet.
- No AOAI resource, no ACS resource, no phone number, no Container App exist yet.

**Next action if resuming provisioning**: Stage 4 of `docs/phase0/wizard/01-provision.sh` — register
`Microsoft.Communication` (free) — was about to run when this session ended. Stages 1–3 were walked by
running the equivalent live commands directly (not by executing the `.sh` file as a subprocess), per
Marco's request for a stage-by-stage, stop-and-confirm cadence — continue that pattern, or switch to
literally invoking the script if that's easier; both are valid, the script is the authoritative
procedure either way.

## This session's commits (chronological, all on `azure-banking-voice-agentic-ai`)

1. `74537bd`, `36808fa` — shared multi-project pre-commit dispatcher (`scripts/git-hooks/pre-commit` at
   the monorepo root) so this project and `AWS-Insurance-FNOL-Voice-Agentic-AI` can both have scope-check
   hooks without one silently overwriting the other's installed hook. Tested (same-project pass,
   cross-project correctly blocked on both sides) before committing.
2. `0ab0632` — this project's own `scripts/check_project_root_scope.py` + `Makefile`; `CLAUDE.md`
   skill-discipline clarified (Marco invokes skills, Claude names one and stops); the four-script Phase 0
   wizard (`docs/phase0/wizard/{01-provision,02-test-calls,03-cost-check-24h,04-teardown-and-r08}.sh` +
   `README.md`); `.gitignore`.
3. `ef962fa` — `02-test-calls.sh` was missing a billing reminder on failure (found by direct question,
   not caught proactively — worth remembering to check *every* script for a pattern once one script gets
   fixed for it).
4. (Marco's own commit, `0832156`, unrelated FNOL work, rode along in the same push — not mine, don't
   attribute it to this session's work.)
5. `7b92f95` — two real bugs found under review and fixed: (a) free-tier subscription promotion
   (`{"category":"freetier","endDateTime":"2027-02-28"}`) could silently suppress Phase 0's measured
   meters — Cost Management *omits* unbilled usage rather than discounting it (sourced from Microsoft's
   own docs, quoted in `COSTS.md`); added a portal-only human-check stage plus a quantity×list-rate
   fallback. (b) `Microsoft.Communication` was `Registering`, not `NotRegistered`, contradicting the
   scoping handoff — added a hard precondition check immediately before the number-purchase stage.
6. `6b359fc` — widened the R-01 Models API query from `gpt-realtime-mini` only to every realtime-capable
   model in canadacentral. Re-pinned `docs/PLAN.md` decision 14 to `gpt-realtime-mini` version
   `2025-10-06` (not the `isDefaultVersion` `2025-12-15`) — same cost, ~3.7 more months of runway, better
   rate limits. Named `gpt-realtime-1.5` as B3's documented successor (not adopted — ~3.2x cost).
   Restructured B3's startup guard from a single frozen constant to active-pin + named-successor with a
   non-silent warning if the successor ever boots.
7. `37fc54b` — recorded `T-B3-SUCCESSOR-BOOT` (skip-by-default L1 test, boots the successor against
   `FakeRealtimeServer`) as an explicit Phase 2 deliverable — not written as code yet, since
   `FakeRealtimeServer` doesn't exist until Phase 2 builds it.
8. `6794192` — pre-spend hourly cost estimate added to `COSTS.md` ahead of the gate (Container App
   ~$0.006–0.02/hr depending on R-04's eventual idle/active verdict; number ~$0.0014/hr; AOAI/ACS
   resources themselves are $0/hr, consumption-only).

**Earlier pre-existing commits this session built on** (not mine): `2b577e1` (scoping plan, `CLAUDE.md`,
handoff — the original scoping work), `dd2e6c6`/`dc923e4` (unrelated FNOL work already on this shared
branch — the branch is shared with FNOL work, which is itself worth noting as slightly unusual).

## Key artifacts (read these, don't ask me to re-derive them)

- `docs/PLAN.md` — source of truth for scope/architecture/budget/phase plan. Decision 14 (model pin) and
  R-01 (tracked risk) both updated this session with full reasoning.
- `CLAUDE.md` — stop conditions, B1–B5 table (B3 wording updated), skill-discipline (updated), new "Model
  pin review" paragraph (pin checked at every phase gate, not treated as settled after one pass).
- `COSTS.md` (project root, new this session) — free-tier promotion investigation, model-pin revision
  summary, pre-spend hourly cost table. Will keep growing as the wizard scripts run.
- `docs/phase0/findings.md` (new this session) — every raw finding (R-01's full model catalog + pricing
  comparison, the free-tier mechanism research, the rate-limit interpretation with its honest gap).
- `docs/phase0/wizard/` — the four-script wizard + `README.md`. `01-provision.sh` and
  `04-teardown-and-r08.sh` both got real bug fixes this session (ERR trap + health check in `01`;
  verified-not-assumed teardown deletion in `04`) — read those scripts' own header comments before
  running them, don't assume the version described in earlier chat turns is still current (it is, but
  verify).
- `scripts/git-hooks/pre-commit` (monorepo root) — the shared dispatcher. Both this project's and FNOL's
  `make install-hooks` install this same file now.

## Open items for the next session

1. **Create `PROJECT_STATE.md`** (see compliance gap above) — do this before/alongside resuming
   provisioning, not after.
2. **Push the 2 unpushed commits** (`37fc54b`, `6794192`) when Marco's ready — give him the `!` command,
   don't retry the Bash tool's own `git push` (denied twice already this session).
3. **Resume the wizard at Stage 4** of `01-provision.sh` (register `Microsoft.Communication` — free) if
   Marco wants to continue provisioning. Keep the stage-by-stage, stop-and-confirm cadence he asked for.
4. **R-06** (DataZone probe, Stage 6) and **R-05** (live area-code inventory, Stage 8) are still
   unmeasured — Stage 1–3 only covered pre-flight, R-01, and the gate itself.
5. Rate-limit interpretation (item 5, `docs/phase0/findings.md`) has an honest unresolved gap: whether
   the Models API's "3 requests/60s" figure means session-establishment or something else. Recommended
   next step (not yet done): check the Foundry portal's Quota page once the AOAI deployment exists in
   Stage 5–7.
6. Once Phase 0 completes (scripts 2–4, spanning the 24h/72h real-world waits), its exit gate needs
   checking against `docs/PLAN.md`'s stated criteria before Phase 1 starts — don't let that get skipped
   under the assumption Phase 0 "basically happened."

## Suggested skills for the next session

- **`/wizard`** is not something to re-invoke — the wizard already exists at `docs/phase0/wizard/`. Just
  resume driving it (Stage 4 onward), or hand it to Marco to run himself with `!`.
- **`/research`** if any further factual Azure unknown comes up (another rate-limit question, another
  pricing gap) — this project has a real pattern this session of not trusting recalled/assumed facts;
  keep that discipline. Per `CLAUDE.md`'s skill-discipline (updated this session): Marco invokes it,
  the next agent's job is to name it and stop, not call the `Skill` tool itself.
- **`/code-review`** once Phase 0's scripts have actually executed against real Azure and the phase is
  ready to close out — before the Phase 0 → Phase 1 gate, per `CLAUDE.md`'s main flow.
- Do **not** reach for `/prototype` — nothing in Phase 0's remaining work is an unresolved design
  question; it's execution of an already-designed procedure.
