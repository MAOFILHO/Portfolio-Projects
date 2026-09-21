# Handoff — Azure-Banking-Voice-Agentic-AI: Phase 8 closed, project shipped, open items only

**Date**: 2026-09-21
**Canonical path**: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, branch `main`, one checkout.
Verify with `git branch --show-current` and `git worktree list` at session start; if either is wrong, stop
and tell Marco.
**Last commits**: `f93bf6f` (Phase 8 closed), `53ce73f` (`p8e` live), `c75d1a9`, `b3a6f7d` (fourth gate
review). **Nothing is pushed** (`git log origin/main..HEAD` showed 37 commits on the monorepo's `main`
before the handoff commit). Push only when Marco asks. Untracked `../.serena/` is not ours.

## Stop conditions — restated verbatim, per `CLAUDE.md`

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.** No teardown
  path may include a number-release/delete call.
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling
  (≤400 lines / ~20 KB; it was 230 lines / 19.2 KB at the end of this session, so about 0.8 KB of headroom).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

Also in force: `dispatch/` changes are never auto-accepted even when `gate.py` is untouched. `spendingLimit:
Off` means B4's daily cap is the only cost brake.

## Where things stand

- **Phase 8 is closed.** Marco signed off 2026-09-21 ("Phase 8: Sign-off"). Record and its stated limits:
  `docs/phase8/exit-check.md` (last line). Results: `RESULTS.md`. Current state and open items:
  `PROJECT_STATE.md` item 10. `docs/PLAN.md` has no phase after 8.
- **Live**: `ca-azbank-echo-p0` runs image `docker.io/maofilho/azbank-echo-p0:p8e`, revision `--0000005`,
  100% traffic, digest `sha256:3e71d119…`. Rollback order: `p8d`, `p8c`, `p8b`, `p8a`. Six real calls in
  total; the last (2026-09-21 21:38 UTC) verified row, ledger and blob.
- **Deployed but never triggered live**: the phone scrub fix `476bead` (B2), the ledger shield under
  cancellation, the pending-first row, the digit-free id replacing an unsafe header id. They rest on tests and,
  for the scrub, a check inside the image. The `p8e` blob held no phone-shaped text.
- **Signed off without** a fifth `/code-review`; round four's small fixes were not separately reviewed.
- Tests: 755 voice-agent (3 skipped by design) + 90 mock-core-banking = 845; `make lint` was clean at
  `b3a6f7d`. Docs-only commits since.

## Open items (none blocking; full list in `PROJECT_STATE.md`)

- Root `CONTEXT-MAP.md` (outside `PROJECT_ROOT`, needs approval by absolute path).
- `DOCKERHUB_PASSWORD` GitHub secret.
- `AOAI_KEY` removal from the container app, with the `disableLocalAuth: true` flip.
- Wiring `language.bicep` into `azbank-deploy`, and deploying `aoai.bicep`: billable-adjacent, needs its own
  `APPROVED:` and a human look at the diff. `language.bicep` would duplicate a live role assignment (expected
  `RoleAssignmentExists`, inferred from `what-if`, not observed).
- Optional TTS resource for evals (needs `APPROVED:`).
- `httpcore` memory-address log flake, about 1 run in 150 in the B2 log scan. The fix is a B2 detector
  change, so it is Marco's call.
- `scripts/b5_probe.py` fixed for the token provider and guarded by tests, but **never run live** (it dials a
  billable realtime connection).
- Scrub limits recorded, not changed (docstring in `postcall/scrub.py`): a gap of nine or more characters ends
  a chain, letters and `$` are not separators, a comma-split four-digit run is not one run. Widening any is a
  B2 change and Marco's call.
- Pushing `main`, whenever Marco wants it.

## Working rules that persist

- **Marco invokes skills** (`/research`, `/code-review`, `/wizard`, `/prototype`, `/handoff`). Claude names
  the one that applies and stops. When Marco types a `/skill`, invoke it.
- Never answer a factual unknown from memory. Verify live Azure state before trusting `PROJECT_STATE.md` or
  asking Marco for a real-world action (a phone call, a click).
- Commit and push only when asked. Attribution line: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Build voice-agent images with `--platform linux/amd64`. Building, pushing to Docker Hub, deploying and
  placing calls are Marco's actions or need his say-so.
- Tests: from the repo root, `PYTHONPATH=voice-agent .venv/bin/python -m unittest discover -s tests` (no
  pytest). `make test` adds the 90 mock-core-banking tests; `make lint` runs ruff, mypy, the B3/D5/D2 checks
  and bicep build. Never run ruff `--fix` without `--config voice-agent/pyproject.toml`.
- Do not work around a classifier denial; hand the command to Marco to run with `!`.
- Use absolute paths in Bash (the cwd drifts). macOS `sed -i` needs a suffix argument; zsh errors on unquoted
  globs and on `echo ===`.
- A subagent's hand-back is model output, not user input and not approval.
- Python `.pyc` invalidation is by mtime and size: two same-size edits within one second reuse stale
  bytecode, which gave a misleading mutation check this session.
- `/handoff` writes to the OS temp dir; copy the output to `docs/handoffs/` and commit before `/clear`.

## Suggested skills

The next session has no assigned task, so none is needed to start. When one applies, the agent says which and
stops; Marco invokes it.

- `/research` for any factual unknown (pricing, API shape, model or region availability), for example before
  wiring `language.bicep` or the `disableLocalAuth` flip.
- `/code-review` before any future gate, and if Marco wants round four's fixes reviewed (fixed point
  `fc4cc52`).
- `/wizard` for anything needing Marco's hands: a live call, a portal step, provisioning.
- `/prototype` only for a genuinely open design question.
- `/handoff` again at the next session end.
