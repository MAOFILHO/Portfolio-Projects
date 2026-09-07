# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 1, 2026-09-07

**Canonical path**: `/Users/marco/K21/Real-world-worktrees/azure-banking/Azure-Banking-Voice-Agentic-AI`,
branch `azure-banking-work`. Verify with `git branch --show-current` / `git worktree list` before
doing anything — do not trust this line if it's gone stale.

## STOP CONDITIONS — absolute, no exceptions (restated per CLAUDE.md)

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).
- **The phone number (`+17059100383`) is never released, by any script, at any phase, for any
  reason.** No teardown path may include a number-release/delete call (R-09).
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds ≤400 lines/~20KB.
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## What this session did

1. **Status check** (no code change): read `PROJECT_STATE.md` and `docs/PLAN.md`'s phase headers to
   answer "how many phases, what's done" — 9 phases total (0–8), Phase 0 closed, Phase 1 in progress,
   Phases 2–8 not started. Full detail already in `PROJECT_STATE.md` — not duplicated here.

2. **`/code-review` of Phase 1** (`mattpocock-skills:code-review`), fixed point `46a1b11` (last
   Phase 0 commit) vs `HEAD`, two parallel sub-agents (Standards / Spec axes). Full findings were
   reported in-conversation, not written to a file — re-run if a written record is wanted. Headline
   results:
   - **Spec axis**: all 5 in-scope Phase 1 items implemented and tested, 0 scope creep. One doc/code
     mismatch found: `PROJECT_STATE.md` open item 11 still says the `app.py:86` try/except fix is
     "not fixed" — it is, with 4 passing tests in `tests/test_echo_app.py`. **Not yet corrected in
     `PROJECT_STATE.md` — do that.**
   - **Standards axis**: flagged B4 (Cost Ceiling) as unenforced in `voice-agent/bridge.py` — no
     turn counter, no call-duration timeout. On follow-up (reading `docs/PLAN.md`'s full phase
     architecture, not just Phase 1's own section) this review's first framing was corrected: full
     B4 (`cost/caps.py`, per-session **and** daily caps, fail-closed on an unreachable cost store,
     `T-B4-FAILCLOSED`) is explicitly **Phase 5** scope (`docs/PLAN.md:621-624`), not a Phase-1 gap.
     Marco chose (via `AskUserQuestion`) a middle path: add a bare per-call guard now, not the full
     Phase 5 system.

3. **Implemented the minimal B4 guard** (`diagnosing-bugs` skill's test-first discipline, adapted —
   this was a missing-feature task, not a mystery bug, so Phase 3 "Hypothesise" was skipped as
   explicitly not applicable):
   - `voice-agent/bridge.py`: `MAX_CALL_TURNS = 20`, `MAX_CALL_SECONDS = 300`. A turn = one
     `response.done` event. The call ends (not an error, just ends) if either cap is hit.
   - `tests/test_bridge.py`: extended the existing fakes (`_FakeAoaiConnection`, `_FakeAcsWs`,
     `_fake_async_openai_factory`) with optional `events`/`hang` params, backward-compatible with
     every existing test. Two new tests in `RunBridgeEnforcesB4Caps` force each cap independently.
   - Confirmed red against the old `bridge.py` (AttributeError — constants didn't exist), then green
     after the fix. Full suite: **24/24 pass, ~57ms.**
   - **This is explicitly NOT full B4** — no daily cap, no cost store, no fail-closed-on-unreachable-
     store. That's still Phase 5's job. Said plainly in both the code comments and the tests' class
     docstring so nobody mistakes this for the real thing later.

## Current repo state — uncommitted work outstanding

```
 M tests/test_bridge.py
 M voice-agent/bridge.py
```

**Not committed.** The project's own main flow (`CLAUDE.md`: "design → build → test → /code-review →
exit-criteria check → commit → /handoff → /clear") puts commit *before* `/handoff`, but it didn't
happen here — this session never received an explicit instruction to commit, and the harness rule
("commit or push only when the user asks") means it wasn't done unilaterally. **First thing the next
session should do: either get Marco to say "commit this" (then commit with a message naming the B4
guard and noting it's partial, Phase-5-completes-the-rest), or explicitly decide it's staying
uncommitted for a reason.** Don't `/clear` past this point either way — that's the stop condition
above, not a suggestion.

## Phase 1 gate status

**Not closed yet.** Exit-test table in `docs/PLAN.md` (search "Phase 1 (REVISED") shows all 6 rows
PASS from the 2026-09-01 real call. Two things stand between here and calling the gate closed:

1. The uncommitted B4-guard work above.
2. `PROJECT_STATE.md`'s open items 1–12 (read that file directly — not duplicated here), notably:
   open item 1 (no durable logging path — flagged as a real blocker for a production voice agent,
   not a Phase-1-specific gap but worth resolving before calling anything "done"), open item 11's
   stale status line (see above), and open item 12 (intermittent interrupt-the-caller defect,
   unresolved, last seen once out of two real calls).

`PROJECT_STATE.md` itself was **not edited this session** — it still reflects the state before this
session's code-review findings and B4 guard. It needs updating (item 11's correction, a line recording
the B4 guard, the uncommitted-work note) before the Phase 1 gate can honestly be called closed.

## Suggested skills for the next session

Per this project's skill discipline (`CLAUDE.md`: "Marco invokes skills — Claude does not invoke them
on its own initiative") — **name these, don't call them unprompted**:

- **`/code-review`** again, if the B4-guard diff or any further Phase 1 change lands before the gate
  closes — it's cheap and this project requires it before every phase gate, no exceptions, "including
  phases that feel too small to need it."
- **`/research`** if Phase 2 kickoff raises a factual unknown — e.g., what `cost/caps.py`'s actual
  fail-closed storage should be (a file? Azure Table? something else), or a fresh B3 pin-retirement
  check against the live Models API (the project's own rule: check this at every phase gate).
- **`/wizard`** for Phase 2 kickoff specifically if it turns out to need a human-in-the-loop step
  (re-provisioning Container Apps compute again counts, same as Phase 1's did).
- **Not needed right now**: `/prototype` — nothing here is an unresolved design-feel question; this
  was either a factual correction (B4 scope) or a small, well-specified implementation.

## References (not duplicated here)

- `docs/PLAN.md` — Phase 1 REVISED section ("search `Phase 1 (REVISED 2026-08-28`"), Phase 5 section
  (B4's real home), named-constraints table.
- `PROJECT_STATE.md` — current phase, open items 1–12, active risks.
- `tests/test_bridge.py`, `voice-agent/bridge.py` — this session's diff, uncommitted.
- Fixed point used for this session's code review: commit `46a1b11`.
