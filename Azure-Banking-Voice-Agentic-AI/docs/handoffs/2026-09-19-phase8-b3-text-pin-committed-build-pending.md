# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 8: B3 text pin committed, build still pending

**Date**: 2026-09-19
**Canonical path**: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, branch `main`, one checkout,
no worktree (confirmed at session start with `git branch --show-current` / `git worktree list`).
**Last commit**: `3ce5280` — B3 extended to the text pin via the static check. Nothing pushed.

## Stop conditions — restated verbatim, per `CLAUDE.md`

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling
  (≤400 lines / ~20 KB — currently 233 lines / 18,375 bytes).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## What this session did

1. Answered "what else is missing for Phase 8?" by reading `PROJECT_STATE.md`,
   `docs/phase8/exit-criteria.md`, the prior handoff, and grepping the code. Result: the gap list below.
2. Marco invoked `/code-review` on the 8 uncommitted B3 files (fixed point `HEAD`, working-tree diff, since
   three-dot against `HEAD` is empty for uncommitted work). Two parallel reviewers, Standards and Spec,
   reported separately: Spec 5 findings, Standards 3 hard + 8 judgement calls. Both flagged the same
   line: the `CLAUDE.md` B3 row named `assert_text_model_safety` as enforcement, but nothing called it.
3. Marco chose "option A and then B": fix the wording, then delete the unwired guard. Done, then
   "A, commit now". Result is commit `3ce5280` (7 files). 34 tests in `tests.test_boot` +
   `tests.test_b3_static_check` pass; `scripts/check_b3_allowlist.py` exits 0.
   Removed: `assert_text_model_safety`, `TextModelUnsafe`, `AOAI_TEXT_DEPLOYMENT_VAR` and 5 tests.
   Kept: `ACTIVE_TEXT_MODEL` / `ALLOWED_TEXT_MODELS` (the static check reads them).

The text pin is enforced by the CI static check **only**. `CLAUDE.md`'s B3 row says so. Details of the
pin itself: `docs/adr/ADR-006-second-model-pin-for-post-call-text-work.md` (see its "Build note").

## Not yet decided — needs Marco before the pipeline is built

These two gaps are in **no design doc**. Both were found by reading code, not by the Phase 8 design round.

1. **Transcript scope.** Caller speech is never transcribed. `voice-agent/azbank_voice_agent/realtime/
   session.py` (~line 57) leaves `input_audio_transcription` off on purpose, because Azure needs a named
   transcription deployment for it. Only agent speech arrives (`response.output_audio_transcript.delta`).
   `docs/phase8/exit-criteria.md` criterion 1 promises a "redacted transcript", and Conversation PII
   detection expects speaker turns.
   - **A. Agent-side transcript only.** No new resource, no new pin. The stored record is half a call.
   - **B. Add caller transcription.** Full record, but a new billable deployment (unpriced), a third B3
     pin (ADR-006 says a third pin is a change to that decision), and PII redaction over caller speech,
     where a spoken PIN or phone number could land (B2).
   - The reviewing session **recommended A**. Marco has not answered.
2. **Call outcome mapping (D10).** `exit-criteria.md`'s gap table says "three values in use". The code
   in `session.py` (~lines 750-840) sets **8**: `closed`, `timeout`, `model_ended`, `caller_hangup`,
   `cost_cap`, `attempts_exhausted`, `escalated`, `error`. D10 wants exactly 5:
   `authenticated_served`, `escalated`, `caller_hangup`, `closed_path`, `error`. No mapping exists for
   `timeout`, `cost_cap`, `model_ended`, `attempts_exhausted`, and `authenticated_served` cannot be read
   off `end_reason` alone (it needs `auth_state`). The D1 glossary term is in `CONTEXT.md`.

## What is still not built (Phase 8)

Everything in `docs/phase8/exit-criteria.md` beyond the two provisioned resources and B3's static check:
the post-call pipeline (criteria 1-4), a Blob container plus a Blob role for the voice agent's identity
(the storage Bicep says "no blobs"), `evals/` (directory does not exist), the redteam run (criterion 7),
`RESULTS.md`, the architecture diagram, and the `README.md` badge (still "Phase 6 of 8"). Also open:
`infra/modules/aoai.bicep` has no text deployment; the non-fatal runtime guard from ADR-006 Decision 4
(built with the pipeline, not before).

## Leftover review findings (not fixed — Marco chose to commit and defer)

- The `boot.ALLOWED_REALTIME_MODELS | boot.ALLOWED_TEXT_MODELS` union is written 3 times (`check_b3_
  allowlist.py`, twice in `tests/test_b3_static_check.py`); one `ALL_ALLOWED_MODELS` would replace it.
- Static check is not class-aware: a bare `gpt-5.4-mini` passes anywhere. No test runs the text name with
  a wrong version through the check; `test_an_unapproved_text_model_pair_fails_the_check` overwrites
  `boot.py` itself, sits in the wrong class, and duplicates an existing test.
- No test that `assert_boot_safety` refuses the text pin.
- `scripts/check_b3_allowlist.py` line ~25 still says "realtime"; its docstring carries changelog prose.
- `exit-criteria.md` D11 and ADR-006 Decision 1 still say "`gpt-4o-mini`-class" (the build note explains
  the switch to `gpt-5.4-mini`).
- `PROJECT_STATE.md` lines ~68-80 read past-tense; ~2 KB of headroom under the 20 KB ceiling.
- The pin string `gpt-5.4-mini` is repeated in 5 files (drift risk).

## Verify before acting

- **Live Azure state was not checked this session.** `CLAUDE.md` Resume discipline: verify the API before
  trusting `PROJECT_STATE.md` (both new resources, RBAC, the default-domain suffix). Model versions and
  retirement dates in the docs are unverified this session.
- `../.serena/` is untracked and not this project's; leave it out of commits.

## Suggested skills

`CLAUDE.md` Skill discipline is in force: the next agent **names the skill and why, then stops**; Marco
invokes it. Do not call these proactively.

- **`mattpocock-skills:tdd`** for the pipeline. ADR-007's guarantee (no raw transcript write, ever) is a
  property test worth writing before the code that could break it.
- **`/grilling` + `/domain-modeling`** if Marco wants to settle the two open decisions above. The call-outcome
  mapping is a glossary question (`CONTEXT.md`).
- **`/code-review`** before the Phase 8 gate, no exceptions.
- **`/wizard`** only if the Blob role grant or resource setup needs a manual step Claude cannot perform.
- **`/research`** not expected; use it only for a new factual unknown (e.g. caller-transcription pricing if
  Marco picks B).
