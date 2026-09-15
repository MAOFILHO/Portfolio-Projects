# Handoff — Azure-Banking-Voice-Agentic-AI, 2026-09-15

## Where this project lives

Canonical path: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, branch `main`, inside
the `MAOFILHO/Portfolio-Projects` monorepo. **One checkout only** — the worktree split is over
(`CLAUDE.md`'s own top section has the full detail; don't re-derive it). Read `CLAUDE.md` in full at
session start — it names stop conditions this session must not skip past.

## Current state

**No phase currently open.** Phase 6 (Observability) closed 2026-09-15, all 14 exit criteria met —
full record: `docs/phase6/exit-check.md`. `PROJECT_STATE.md` is current as of this commit; read it
next, not this document, for the live Azure inventory and the open-items backlog (19 tracked items,
none blocking). Latest commit on `main`: `0be562a`, confirmed landed on GitHub via
`gh api repos/MAOFILHO/Portfolio-Projects/commits/main`.

## What's actually open

1. **`/research`: D10's IAM role for Application Insights' Entra-identity ingestion path.**
   Undocumented anywhere in this repo. The named fallback (`AZURE_MONITOR_AUTH=connection_string`)
   is what's deployed today and works; this is Phase 7 debt, not a blocker. `PROJECT_STATE.md`
   "Next actions" item 5 is the only open next action currently tracked.
2. **Phase 7 has not been scoped at all.** No design session, no exit criteria, nothing. If the next
   session is meant to start it, that's a fresh `/wizard` or design conversation, not a continuation
   of anything in flight.
3. **The monorepo-root `CONTEXT-MAP.md`** that `docs/agents/domain.md` calls for is still unwritten
   and needs Marco's approval (it sits outside this project's own root). Not this project's item to
   close alone.
4. The 19 backlog items in `PROJECT_STATE.md`'s "Open items" — read that section directly rather
   than here; this file doesn't duplicate it.

## Session-specific gotcha, worth knowing before you push anything

**This sandbox's SSH cannot reach GitHub** (`git@github.com: Permission denied (publickey)`). Every
push this session went: Claude commits locally → Marco runs `git push origin main` in his own
terminal → Claude verifies with `gh api repos/MAOFILHO/Portfolio-Projects/commits/main --jq '.sha'`
and compares against the local commit, because "push completed" from Marco has been wrong before
(a push that only fast-forwarded partway, confirmed by `gh api` disagreeing with what was claimed).
Don't skip the `gh api` check.

**A second gotcha, cosmetic but confusing**: the `Bash` tool's own "Shell cwd was reset to ..."
messages sometimes report `/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-
Agentic-AI` — a path with no `.git` and none of this project's files in it (checked directly this
session: `git rev-parse` there fails with "not a git repository"). It's an inert leftover from
before the worktree consolidation, not a real second checkout. Every file edit and git command this
session used the explicit canonical absolute path and none landed in the wrong place — but always
`cd` explicitly or use absolute paths for git operations rather than trusting the tool's reported cwd.

## Recently closed, for context (don't re-litigate)

- **B2 widened** to 4 OpenTelemetry content channels and 2 protected values (PIN + caller phone
  number) — issue #65, `2458da3`. `/code-review` on the uncommitted diff caught and fixed two real
  issues before it landed (a doc-consistency gap, and an overstated coverage claim for one channel).
- **`ADR-005`** written: the shared core-banking client (issue #35) and the `escalate_to_human`-
  while-anonymous corollary of B1 — both decisions were already live in code, neither had a written
  record before now.
- **The 58-commit backlog review** (`e42c063..HEAD`) done via `/code-review`, monorepo-move-aware
  pathspec scoping (both the project's old root-level directory names and its new subdirectory path,
  combined with `-M` for rename detection — needed because this project's history crosses a
  directory-move boundary that breaks naive `git log -- <path>`).
- A user-reported PIN-timing concern (agent seeming to confirm before the 4th digit) was
  investigated and closed as a **false alarm** — code and live trace evidence agree: exactly 4 digits
  required, no early-confirmation path.

## Suggested skills for the next session

- **`/research`** — for D10's IAM role question, if that's what gets picked up next. Cite primary
  sources (Azure docs, not memory), per this project's own standing rule (`CLAUDE.md`).
- **`/wizard`** — if Phase 7 turns out to need a human-in-the-loop provisioning step (assigning an
  IAM role live is exactly that kind of step).
- **`/code-review`** — before any diff lands, no exceptions, especially anything on the DTMF/PIN path
  (B2) or `dispatch/gate.py` (B1). Two parallel sub-agents (Standards, Spec), per this project's own
  skill definition.
- Per `CLAUDE.md`'s skill discipline: **name the skill, let Marco invoke it** — don't self-invoke.
