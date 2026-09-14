# Handoff — Phase 5 closed, Phase 6 entry conditions not yet met

**Date:** 2026-09-12
**Branch/worktree:** `azure-banking-work` at
`/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI` — this is the
canonical path (`CLAUDE.md`'s own header). Verify with `git branch --show-current` and
`git worktree list` before doing anything; do not trust this line alone.
**HEAD:** `c7bc403` (docs, Phase 5 close-out), preceded by `839a451` (fix, the transfer-word bug).
**Requested focus for the next session:** Marco's args were "Phase 5 and let's start Phase 6" — read
that as intent, not as the two explicit approvals the project's stop conditions require. Neither had
been given as of this handoff. **Get them explicitly before any Phase 6 work begins.**

---

## Restated verbatim: stop conditions in force (`CLAUDE.md`)

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling
  (≤400 lines / ~20KB).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

---

## What just happened (this session)

Full account: `PROJECT_STATE.md` (current state), `docs/phase5/exit-check.md` (criterion-by-criterion
Phase 5 evidence), `docs/PLAN.md`'s Phase 5 section, commits `839a451` and `c7bc403`. Not repeated
here — read those rather than this summary if detail is needed.

In one paragraph: Phase 5's remaining tickets (#57-60) closed today. A phone was dialled roughly a
dozen times; three real live-call defects were found and fixed (premature escalation, routing
narrated aloud with a skipped refusal tool call, and a third bug the second fix introduced — banning
the word "transfer" on the banking agent itself, caught in `/code-review` and fixed same-session).
Image `p5i` / revision `--0000011` is live and confirmed `Healthy`. B5 froze at p95 1025ms, N=13
(real-call pool only — the latency probe couldn't reach `mock-core-banking`'s deliberately
internal-only ingress from outside the Container Apps environment). The acceptance-call criterion is
met by evidence scattered across the day's calls rather than one continuous run — Marco's explicit
choice, recorded as exactly that, not smoothed into a clean pass.

**Two new memory-worthy facts, not yet in a persistent memory file beyond what's here:**
- The transfer-word bug is a good example of one fix's clause being too broad for a second agent. If
  a future phase adds more shared instruction clauses across agents (`agents/specs.py`'s
  `_ESCALATION_INSTRUCTION` / `_ROUTING_IS_INVISIBLE_CLAUSE` pattern), check each clause against
  *every* agent it's appended to, not just the one the bug was found on.
- `mock-core-banking`'s internal-only ingress (a deliberate, reviewed decision — criterion 22) means
  **no tool on this laptop can reach it directly.** Any future ops script, probe, or diagnostic that
  needs to hit it must run from inside the Container Apps environment, or the ingress decision needs
  its own reconsideration — not a workaround.

---

## What is NOT done, and blocks Phase 6

`docs/phase6/exit-criteria.md`'s entry-conditions table (re-checked and updated today) — **4 of 8
still unmet**:

1. **Marco's sign-off on Phase 5** — distinct from the exit criteria being met. Not given yet.
2. **Marco's explicit approval to begin Phase 6** — distinct from `APPROVED: Phase 6` (already typed
   2026-09-12), which covers only the billable-resource gate, not the general go-ahead.
3. **Open item 16** (`/research`) — whether FastAPI/httpx/requests instrumentations capture request
   bodies by default. Hard-blocks Phase 6 ticket D8 criterion 3 (the ACS webhook carries the caller's
   phone number).
4. **Open item 15** (`/research`) — the `RequestResponse` diagnostic-log category's content coverage.
5. **B2 widening sign-off** — `docs/phase6/exit-criteria.md`, "B2, proposed new wording" section. A
   named constraint does not move without it.
6. **`git log e42c063..HEAD` reviewed** — still not done. Today's `/code-review` covered only
   `a7e06d1..HEAD` (17 of the 42 commits since `e42c063`); the other 25 remain unreviewed. Waived once
   already at Phase 5 entry — flag rather than waive again without saying so.

(The other two conditions — Phase 5's exit criteria written, and now met — are satisfied.)

---

## Immediate next action for the next session

1. **Ask Marco directly for the two sign-offs** (items 1-2 above) before anything else. Do not infer
   them from "let's start Phase 6" phrasing alone — that's exactly the failure mode this project's
   `CLAUDE.md` calls out by name ("a human decision point actually being a stop, not a pass-through
   Claude reasons its way around under time pressure").
2. Once both are given, the remaining blockers (items 3-6) need real work, not just sign-off — see
   "Suggested skills" below.
3. **Resume discipline** (`CLAUDE.md`): before trusting `PROJECT_STATE.md`'s "Live Azure state"
   section, re-verify against live `az` state. It was accurate as of this session's end but is a
   snapshot.

---

## Suggested skills for the next session

Per this project's own skill-discipline rule (`CLAUDE.md`): name these to Marco and let him invoke
them — do not call them proactively.

- **`/research`** — for open items 15 and 16 above. Both are factual unknowns (a diagnostic-log
  category's coverage; an instrumentation library's default body-capture behaviour), exactly what
  this project reserves `/research` for rather than answering from memory.
- **`/code-review`** — for `git log e42c063..HEAD` (or whatever range remains unreviewed by the time
  the next session starts), to actually close entry condition 6 rather than waive it a second time.
- **`/wizard`** — likely needed once Phase 6 actually begins provisioning (Application Insights, the
  OTel Distro wiring) given the human-in-the-loop provisioning pattern every prior phase has used.
- **Model policy** (`CLAUDE.md`): Phase 6's *design* is already done (`docs/phase6/exit-criteria.md`,
  19 decisions settled 2026-09-11, presumably in an Opus session). If Phase 6 needs any *new* design
  or exit-criteria rework — not just implementing what's already settled — that work belongs in an
  Opus session, not this one's Sonnet default.

---

## Files worth reading first, in order

1. `PROJECT_STATE.md` — current state, rewritten this session for Phase 6 entry.
2. `docs/phase6/exit-criteria.md` — entry-conditions table (top), 19 settled decisions.
3. `docs/phase5/exit-check.md` — if any Phase 5 evidence needs re-checking or citing.
4. `docs/PLAN.md`'s Phase 5 and Phase 6 sections.

No secrets, keys, or PII are referenced in this document or were handled unsafely this session (the
Docker Hub credential and AOAI key were both fetched directly into shell variables and `unset` after
use, never printed).
