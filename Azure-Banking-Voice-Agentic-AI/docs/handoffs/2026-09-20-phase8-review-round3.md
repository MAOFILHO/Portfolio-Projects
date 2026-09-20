# Handoff — Azure-Banking-Voice-Agentic-AI, Phase 8: review round 3 done, decisions pending

**Date**: 2026-09-20
**Canonical path**: `/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI`, branch `main`, one checkout.
Verify with `git branch --show-current` and `git worktree list` at session start.
**Last commits**: `e5b7fe5`, `34e91d4` (round-2 fixes), `4b857a2` (round-1 fixes). **Nothing pushed.**
**Uncommitted (held on purpose, see below)**: `CLAUDE.md`, `tests/test_postcall_capture.py`,
`voice-agent/azbank_voice_agent/realtime/session.py`. Untracked `../.serena/` is not ours.

## Stop conditions — restated verbatim, per `CLAUDE.md`

- No phase begins without written exit criteria from the prior phase and Marco's explicit approval.
- No billable Azure resource is created without Marco typing `APPROVED: <phase name>`.
- **Never auto-accept a diff that provisions a billable resource, or that touches `dispatch/gate.py`
  (B1) or anything on the DTMF/PIN path (B2).** These always get a human look before they land, no
  matter how mechanical the change appears.
- **The phone number is never released, by any script, at any phase, for any reason.**
- `PROJECT_STATE.md` is updated before any session ends, and never exceeds its size ceiling
  (≤400 lines / ~20 KB — currently ~243 lines / ~19.4 KB, about 0.6 KB of headroom).
- Restate these conditions verbatim at the top of every session summary and after every `/compact`.

## Where Phase 8 stands

Built, on `main`, live (image `p8a`); criteria 1-2 proven on one real call. Two `/code-review` rounds
plus a third (below). History and evidence: `docs/phase8/build-notes.md`. Criteria and decisions:
`docs/phase8/exit-criteria.md` (D1-D18), `docs/adr/ADR-006-*.md`, `docs/adr/ADR-007-*.md`. State and
open items: `PROJECT_STATE.md` item 10. This session's commits are self-describing in `git log`.

## The held, uncommitted diff — needs Marco's look before it lands

It is in the `finally` of `run_call` / `run_closed_call`, directly under `authenticator.end_call()`
(PIN-buffer zeroing; that line is unchanged and still first). Not committed because `CLAUDE.md`
requires a human look at anything near the DTMF/PIN path.

- `session.py`: ledger write (`_record_minutes`, B4) is first again, wrapped in try/finally so
  `capture.finish(...)` runs after it even if the write is cancelled. Round 1 had put `finish` ahead
  of the ledger, which would have skipped the day's charge if `finish` ever raised.
- `tests/test_postcall_capture.py`: `BrokenCapture` tests (both paths; these are the ones that fail
  against the old ordering), a deterministic duration test, renamed cancellation tests.
- `CLAUDE.md` B3 row: "Text: CI static check only" -> "the runtime guard above plus the CI static
  check, and no Bicep enforcement". Wording only, but it is a named-constraint row.
- Show it with `git diff -- voice-agent/azbank_voice_agent/realtime/session.py CLAUDE.md tests/`.
  On Marco's word, also fix two comments the round-3 review found overstating: "First, ahead of
  anything else in this block that could raise" (`end_call()` and a `duration_ms` line precede it) and
  "on every path out" (a cancelled write aborts, see decision 3), plus the test comment "awaited in the
  same `finally`" (it is the inner try/finally).

## Round-3 `/code-review` (fixed point `4b857a2`, diff against the working tree) — findings, no fixes yet

Both axes independently found the same worst issue.
1. **Escalation row keyed on an unchecked id (worst, both axes).** `dispatch/tools.py:360` builds
   `EscalationRecord.now(scope.correlation_id, ...)` from the raw `x-ms-call-correlation-id` header;
   `store.py` `record_escalation` uses `f"{occurred_at}_{correlation_id}"` as the RowKey. `#`/`?`/`/`/`\`
   makes `create_entity` raise; the call still escalates but the durable record is lost. `None` becomes
   `..._None`. The comment in `store.py` claiming ids "cannot contain a character the key forbids"
   contradicts `is_storable_id`'s docstring. `is_storable_id` also has no length cap (Table RowKey limit
   is 1 KiB). Note `dispatch/tools.py` is on the "never auto-accept" list: show the diff first.
2. **B4 gap, pre-existing.** A task cancelled during `_record_minutes` aborts the write, so those
   minutes are never recorded (undercount, i.e. fail-open). Only the capture is protected, not the
   charge. Nothing shields the write.
3. Judgement calls (low): `problem` in `pipeline.py` would read better as `failure_status`; `_run`'s
   8-line id block could be `_storage_key()`; `BrokenCapture` / `CancelledDuringTheWrite` defined twice
   in the tests; `is_storable_id` lives in the Table-specific `store.py`; `test_app.py`'s
   `assertIsInstance` is near-vacuous; `phase6/exit-criteria.md` header still says "NOT given" while its
   line 34 says typed 2026-09-12; `PROJECT_STATE.md` still has past-tense narrative outside item 10.
4. Verified fine: ADR-007 Decisions 2 and 3 hold through the `_step` redesign; `end_call()` untouched;
   an ACS GUID id is kept as-is; the pipeline's warning never logs the raw id.

## Decisions waiting on Marco (none taken)

1. Extend the id check to the escalation record (plus a length cap)? Touches `dispatch/tools.py`.
2. Accept the held `session.py` / `CLAUDE.md` diff so it can be committed with the comment fixes?
3. Shield the ledger write from cancellation (`asyncio.shield`)? Changes B4 behaviour.
4. Still-open Spec gaps from earlier rounds: (a) a call whose `connect_realtime()` raises writes no
   row; (b) the row is written last, after up to 3 x 60 s steps, so a container kill loses it;
   (c) one agent turn over 1,000 characters loses the whole transcript; (d) criterion 4's test
   measures no latency and does not attach the real pipeline; `$` amounts unredacted; a formatted
   number's area code survives `scrub_numbers` (`scrub.py` is B2, declined pending Marco).

## Remaining for the Phase 8 gate

`RESULTS.md` (D6 line ceiling), architecture diagram, README badge (still "6 of 8"), `COSTS.md`
(gpt-5.4-mini $0.75 / $4.50 per 1M tokens Global, Blob and Language notes), the D15 write-up for
criteria 6-7 (evals need TTS caller audio and no TTS resource is provisioned; a TTS resource is
billable and needs `APPROVED:`), `evals/`, then the exit check, Marco's closure sign-off, a final
`/code-review`, `/handoff` (copy to `docs/handoffs/`, commit), `/clear`.
Also open from earlier phases: root `CONTEXT-MAP.md`, the `DOCKERHUB_PASSWORD` GitHub secret, the
`AOAI_KEY` removal and `disableLocalAuth` flip, and the Language Bicep module (billable).
Observation, not a criterion: the agent talks over the caller (turn detection / barge-in). Nothing changed.

## Working rules and gotchas that persist

- Marco invokes skills (`/research`, `/code-review`, `/wizard`, `/prototype`); Claude does not. Say
  which applies and stop.
- Never answer factual unknowns from memory. Verify live state before asking Marco for a real-world action.
- Commit and push only when asked (the `/implement` skill's "commit" counts). Attribution line:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Tests: `.venv/bin/python -m unittest discover -s tests` (no pytest); `make lint` covers ruff, mypy,
  the B3/D5/D2 checks and bicep build. Never run `ruff --fix` without `--config voice-agent/pyproject.toml`.
- Docker images: `--platform linux/amd64`. macOS `sed -i` needs an explicit suffix argument; prefer the Edit tool.
- `echo ===` fails in zsh; quote it.
- The auto-mode classifier has denied prod-deploy and role-grant commands; do not work around it, hand
  the command to Marco to run with `!`.
- Live: container app `ca-azbank-echo-p0` runs `docker.io/maofilho/azbank-echo-p0:p8a`. The storage
  account `stazbankcallrecords` has shared-key access off, so data-plane reads need Entra data roles
  (Marco's user holds Table and Blob Data Reader, granted 2026-09-20).
- Use they/them for anyone whose pronouns are not stated.

## Suggested skills for the next agent

- `/code-review` — Marco invokes it; run it again after decisions 1-3 are implemented and before the gate.
- `/tdd` (via `/implement`) — for decisions 1 and 3: write the failing test first (an escalation with
  a `#` id; a cancelled ledger write that must still be charged).
- `/research` — Marco invokes it; only if a factual unknown arises (e.g. Table RowKey length limit
  wording, TTS options for the evals). Do not answer those from memory.
- `/wizard` — only if criterion 6-7 evals need Marco's hands or voice on a real call.
- `/handoff` — at the end, then copy the output into `docs/handoffs/` and commit.
