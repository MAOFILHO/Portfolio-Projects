# Handoff — Azure-Banking-Voice-Agentic-AI, 2026-09-18

## Where this project lives

Canonical path: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, branch `main`, inside
the `MAOFILHO/Portfolio-Projects` monorepo. **One checkout only** — `CLAUDE.md`'s own top section has
the full detail on the old worktree split; don't re-derive it. Read `CLAUDE.md` in full at session
start — it names stop conditions this session must not skip past, most importantly: the phone number
`+17059100383` is never released by any script, and `PROJECT_STATE.md` has a hard size ceiling
(≤400 lines/~20KB) that must be checked before every edit.

## Current state

**No phase currently open.** Phase 7 (IaC completion & CI/CD) closed 2026-09-18, all 9 exit criteria
met (2 with a stated, accepted limit) — full record: `docs/phase7/exit-check.md`. `PROJECT_STATE.md`
is current as of this commit; read it next, not this document, for the live Azure inventory and the
19-item open backlog (none blocking). Latest commit on `main`: `eb405fc`, confirmed landed on GitHub
(`gh api repos/MAOFILHO/Portfolio-Projects/commits/main` matches local `HEAD` exactly — verified this
session, SSH push worked cleanly, no sandbox networking issue this time).

## What Phase 7 actually built, and what's real debt from it

Full account: `docs/phase7/deploy-teardown-cli.md` (design) and `docs/phase7/exit-check.md`
(criterion-by-criterion evidence). Don't re-read this section as duplicate — the short version, for
orientation only:

- `src/azbank_deploy/` — a Typer CLI (`make deploy`/`make teardown`) that auto-computes the legal
  dependency order for all 7 Azure resources this project owns, live-verified end to end today
  (teardown to zero, then a real from-empty redeploy, then a live phone call with a successful PIN +
  balance check).
- **Two pieces of accepted debt, both $0 ongoing cost, both left unfixed on purpose:**
  1. The CLI models resource state as boolean ("deployed: yes/no"), not "still matches what it
     depends on." Tearing down and recreating the Container Apps environment gives Azure a new random
     domain suffix; ACS (never torn down, by design) kept the stale webhook URL and calls rang
     unanswered until fixed live (`az eventgrid event-subscription update`). Not fixed in the CLI
     itself — the next resource with a similar live-computed dependency value would hit the same gap.
  2. `make teardown` doesn't clean up 3 auto-created Log Analytics workspaces or 2 Application
     Insights alert artifacts (outside the CLI's 8-node graph). Confirmed $0 cost.
- `DOCKERHUB_PASSWORD` still needs adding as a GitHub repository secret before the `deploy`/`teardown`
  *workflows* can run (the local CLI already works — Marco supplied it as a local env var today).

## What's actually open

1. **Phase 8 has not been scoped at all.** No design doc, no exit criteria, no `APPROVED: Phase 8`.
   If the next session is meant to start it, that's a fresh design conversation, not a continuation of
   anything in flight — `docs/PLAN.md` is the source of truth for the overall phase plan if Phase 8's
   shape isn't obvious from there.
2. `/research`: D10's IAM role for Application Insights' Entra-identity ingestion path — still
   undocumented, still Phase 7 debt carried forward (the fallback `AZURE_MONITOR_AUTH=connection_string`
   is what's deployed and works).
3. The monorepo-root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls for is still unwritten and
   needs Marco's approval (it sits outside this project's own root, same as the two GitHub Actions
   workflow files approved this session).
4. The 19-item backlog in `PROJECT_STATE.md`'s "Open items" — read that section directly, not
   duplicated here.

## Session-specific gotcha, worth knowing before you trust a recorded FQDN or principal ID

**The Container Apps environment's default domain suffix changed today** (`yellowmoss-81870d2d` as of
this session — was something else before). It's random per environment and changes on any teardown +
recreate. Same for the voice agent's system-assigned identity principal ID
(`bb712203-9e00-42a5-a0b5-0f38b376c79e` as of today). Any doc — including `PROJECT_STATE.md` itself —
can be stale on both the instant a teardown/redeploy happens again. Always re-check live
(`az containerapp show`) before trusting either value, per `CLAUDE.md`'s own Resume discipline.

## Recently closed, for context (don't re-litigate)

- **A real RBAC gap found live**: a prior session's "already granted" claim for AOAI's managed-identity
  role assignment was wrong — Bicep had it written, not applied. Fixed, then live-verified by a call.
- **Two `agents/specs.py` conversational bugs**, both found on real calls, both fixed: an over-dramatic
  escalation-refusal wording, and a regression that wording fix caused (post-PIN handoff silently
  stopped working). Full account: `docs/phase7/d2-live-call-result.md`.
- **`/code-review` on `53f868b`** (the CLI + workflows commit) — 0 hard violations, 1 real bug fixed
  (`d7c6b14`, a dead `location` parameter that could never do anything, confirmed against the `az` CLI's
  own help text rather than assumed).
- SSH push authentication issue this session (`Permission denied (publickey)` on first attempt) was
  local machine setup, not the deploy key — the key just wasn't loaded into `ssh-agent`/Keychain yet.
  Fixed with `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`. Not expected to recur.

## Suggested skills for the next session

- **Design/kickoff conversation for Phase 8** — not a named skill here, but the first real step;
  `docs/PLAN.md` and the closed-phase pattern in `docs/phase5/exit-criteria.md` through
  `docs/phase7/exit-criteria.md` are the templates to follow.
- **`/research`** — for D10's IAM role question, if that's what gets picked up. Cite primary sources
  (Azure docs, not memory), per this project's own standing rule.
- **`/code-review`** — before any diff lands, no exceptions, especially anything on the DTMF/PIN path
  (B2) or `dispatch/gate.py` (B1). Two parallel sub-agents (Standards, Spec), per this project's own
  skill definition.
- Per `CLAUDE.md`'s skill discipline: **name the skill, let Marco invoke it** — don't self-invoke.
