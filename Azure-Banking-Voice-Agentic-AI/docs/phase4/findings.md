# Phase 4 — findings and recorded deviations

Written as the phase was built, ticket by ticket, rather than reconstructed at the end. Everything
here is something a later session would otherwise discover rather than read.

---

## Deviations from the written tickets

Each of these is flagged rather than folded in silently, which is the rule the exit criteria set
for the one deviation they anticipated (the `unittest`-for-pytest substitution, criterion 10).

### 1. The authenticator has seven outcomes, not the six #36 lists

`docs/phase4/exit-criteria.md` and issue #36 both name six: accumulating, cleared, authenticated,
rejected credential, attempts exhausted, unavailable. The implementation has a seventh,
**`IGNORED`**.

It is required by the protocol the same tickets specify. Pound is ignored, and a key arriving after
the call's authentication question is already settled — passed, or exhausted — is ignored too.
Neither is *accumulating* (nothing was accumulated) and neither is *cleared* (nothing was cleared),
so reporting either would be untrue. The relay acts on the same four outcomes it always did; the
addition is entirely on the silent side.

### 2. The injected conversation item's shape is not verified against the live deployment

Criterion 7 and issue #37 call for the outcome to be injected "as a conversation item plus a
response request — the same mechanism the handoff already uses". The handoff's mechanism is a
`conversation.item.create` carrying a **`function_call_output`**, and that shape *is* verified live
(`docs/phase1/research-aoai-realtime-wire-format.md`, confirmed on a real Phase 1 call).

A PIN outcome answers no tool call, so it has no `call_id` and cannot use that item type. What
`realtime/session.py:_spoken_note` sends instead is a `message` item with a `system` role and
`input_text` content. **That shape is the documented one and nothing more — this project has never
seen the deployment accept it.**

This sits in the same known-partial as the keyed tone itself and closes at the same point: Phase 5's
real-call exit. It is recorded here because Phase 4 deploys nothing, so nothing in this phase can
close it, and `CLAUDE.md`'s rule against answering a factual API question from memory means it must
not be left reading as verified.

**Wanted before Phase 5's real call:** `/research` on the Azure OpenAI realtime API's
`conversation.item.create` item types, specifically whether a `system`-role `input_text` message is
accepted mid-session on a `gpt-realtime-mini` deployment, and what a rejection looks like.

### 3. B2's leak detector is `unittest`, not a pytest autouse fixture

Anticipated by the exit criteria's own criterion 10 and by issue #39, and repeated here so the
record is in one place. This project runs stdlib `unittest discover` from its `Makefile`; the
criterion's intent — blocking by construction rather than a CI step someone can drop — is met by
installing the capture from the suite itself.

Two implementation details are worth reading before touching it (`tests/test_zz_b2_leak_scan.py`):

- **It patches `logging.Logger.handle`, not the root logger's handlers.** A root handler looks like
  the obvious way to catch everything and quietly is not: `assertLogs` replaces the target logger's
  handlers and sets `propagate = False` for the duration of the block, and this suite is full of
  those on exactly the modules that touch the PIN. Those records would never have reached a root
  handler.
- **Its filename sorts last on purpose.** `unittest discover` imports every module before running
  any test, so the capture is installed before the first test runs; the run-wide assertion has to
  come after the last one, and sorted module order is how a stdlib `unittest` run says that.

### 4. B2's coverage is two rules, not one

The run-wide scan looks for submitted values **whole**. It cannot see a relay that logged each tone
as it arrived: four records reading `1`, `2`, `3`, `4` carry the PIN between them and contain no
substring of it in any one of them. Widening the scan to single digits is not the fix — it would
flag `attempt 1 of 3` and every port number in the suite.

The digit-by-digit leak is caught precisely instead, at the seam where it could happen. The relay's
own logger has no legitimate reason to emit a decimal digit while a caller is keying, so
`test_the_relay_logs_no_decimal_digit_at_all_while_a_pin_is_being_keyed` asserts that it emits none.

**Both rules were verified against a real injected leak, not only against the rehearsal**: logging
the submission in `auth/authenticator.py` fails the run-wide scan, and logging the arriving tone in
`realtime/session.py` fails the digit rule. Recorded because the first attempt at that verification
credited the run-wide scan with a catch that was actually the older whole-call assertion's — the
substring rule had not fired at all, which is how gap 4 was found.

**Which of B2's four surfaces these rules actually cover** (added 2026-09-10; `/code-review` read
the "two rules" framing above as a claim about all four). Log lines and persisted records: covered.
Transcripts and injected items: covered, run-wide, since 2026-09-10 — previously one call.
**OTel span attributes: not covered, because this project emits no spans at all.** There is nothing
to scan and nothing is claimed; that surface becomes real work in Phase 6, which owns observability.
A constraint reported as met against a surface that does not yet exist would be the same empty claim
as a percentile with no N. The table in `docs/phase4/exit-check.md` criterion 10 is the canonical
version of this breakdown.

---

## Fixed after `/code-review`, 2026-09-10

The two-axis review ran over the whole phase, `56178e5...HEAD`. Fifteen findings across both axes,
deduplicating to thirteen. Twelve were implemented; one was declined. Nothing here changed a
constraint's target, and `make test` and `make lint` are green.

**The one that mattered most, and why it was not a live hole.** `redteam_harness.py` derived each
case's `authenticated` flag from the *scripted keypresses* rather than from the call. No point in the
matrix ever spells the accepted credential, so the flag was `False` for all 193 cases and
`Outcome.is_breach` silently collapsed from a conjunction to its remaining half. That over-reports:
it could have invented a breach, never passed one, so B1's verdict of 0 breaches stands unchanged.
It is still a real defect — a detector never shown to distinguish its two cases has not been shown to
detect anything — and `TheDetectorItself` now exercises both legs, including a call that really does
authenticate.

**The rest, briefly.**
- The `injected` arguments strategy emitted unterminated JSON, so it died at the dispatcher's parse
  in exactly the place a `malformed` payload dies and the smuggled field never existed. Now valid
  JSON carrying a real `auth_state` key. Worth stating plainly: the gate is consulted *before*
  arguments are parsed, so on a refused tool no argument shape is reached at all — the strategy can
  only discriminate on verification, the one operation permitted while anonymous, and a case is
  aimed there.
- `verification-flooding.yaml` named two failures nothing scored. `Outcome.verifications` records one
  entry per answered credential check, so a cleared entry costing an attempt, or a rejection not
  costing one, is now a red test rather than a rationale.
- B2's secret list was hand-written with nothing tying it to what the suite keys. `tests/keyed_values.py`
  is now the one list, and a static guard reads the suite's own source and fails if any keyed
  four-digit credential is outside it. Fragments such as a cleared `123` are deliberately *not* in
  the run-wide scan: a two-digit needle matches any timestamp or port number the suite logs. They
  stay asserted precisely, in the one call that keys them.
- The relay's DTMF comment claimed the record never reveals how many tones arrived. One arrival line
  per frame means it does. The comment now says so and explains why that is acceptable: B2 protects
  the credential, and a keypress count is not one.
- `log.info("PIN entry outcome")` used a term `CONTEXT.md` proscribes; so did the success sentence
  read to the caller, `"you're verified"`. Both fixed, and a test now asserts no caller sentence uses
  a proscribed auth-state term.
- `_press` returned `(None, submission)` — a pair whose first element was empty exactly when the
  second was not. It returns one value now, and the completed-entry wrapper **refuses to render its
  own digits**, which keeps four keyed digits out of any traceback or debugger frame.
- `test_gate.py`'s both-directions permission assertion is split, so a Phase 5 failure says which
  direction broke. It was **kept, not relaxed**: a declared tool absent from the granting row is
  refused for everyone, which is the gate failing closed and therefore silent. The red build is the
  tripwire that makes that silence audible, and Phase 5 will trip it three times on purpose.

**Declined, deliberately.** The sha256 digest helper appears in the voice agent's fake, in
`mock-core-banking/db.py`, and in its seed constant. That is `docs/PLAN.md` decision 9's
shared-nothing rule working as intended — the two deployables do not share code — so consolidating it
would undo an architectural decision to satisfy a duplication smell. Recorded here rather than fixed.

**Not restructured, and why.** The credential check is awaited inside the inbound relay loop, so
audio forwarding stalls until the system of record answers. It is bounded by the client's own timeout
and circuit breaker. The stall lands on the fourth tone, when the caller has just finished keying and
is waiting for a verdict rather than speaking, so putting a second concurrent task on the PIN path
would reclaim audio nobody is using at the cost of the ordering guarantee B1 rests on. Revisit only
if B5 measurement shows it.

---

## Closed 2026-09-10: the idea count, and a detector that would have under-reported

`redteam/README.md` recorded two attack ideas as **real, tested, and deliberately not counted**,
because the loader did not generate them: inheriting a previous caller's authentication, and
completing an entry with characters that are digits to Unicode and to no keypad. The count read 11.

**They are counted now because they are generated now — not because the rule changed.** Counting
them where they sat would have been the padding the README forbids. The matrix grew two things
instead: a `prior_call` field, which runs an earlier unrelated call against the same core-banking
client, and an `after_homoglyph_digits` point, which keys six characters `str.isdigit()` accepts.
Both are ordinary idea files now and widen with every tool Phase 5 adds. **13 ideas → 211 concrete
cases, 194 reaching an attempt, 0 breaches.**

**The gap to the 20–30 target is not closed and is still reported as a gap.** The surface is three
operations, two agents and two auth states; that is what caps the honest number, and two more ideas
did not change it.

**What the narrow tests became.** `tests/test_redteam.py`'s `IdeasThatDoNotFitTheMatrix` was renamed
and re-framed rather than deleted. A corpus case watches a call from outside and can only see a
refusal, and a refusal looks the same however it was arrived at. The two tests now assert the
mechanism the corpus cases cannot reach: the exact payload the second call is refused with, and the
authenticator's `IGNORED` verdict on each character one at a time. They are assertions *about* two
counted ideas, not a thirteenth and fourteenth.

**The correctness fix this dragged in, and which way it pointed.** `Outcome.authenticated` and
`Outcome.reached` were read off the core-banking spy's whole history. That is correct only while no
case runs more than one call. With `prior_call`, the earlier caller's accepted verdict would have
been read as *this* call's — and `is_breach`, a conjunction, would have come back False for
precisely the cases written to catch a breach. The harness now marks the spy's record before the
case's own call and reads only past that mark.

**Verified against a real injected breach, not against the rehearsal.** With one permissive gate
row, the twelve cross-call cases put two banking operations into the spy's record. Read from the
mark, the detector catches both. Read across the whole process, it catches **none** of them. This
resembles the `authenticated`-from-the-script defect `/code-review` found, and differs in the one
way that matters: that one over-reported and could only ever invent a breach, and this one would
have swallowed real ones.

---

## Open: one unreproduced test failure

**Seen once, in a full `make test`-equivalent run on 2026-09-10, and not reproduced in 98
consecutive runs since.** Reported as `FAILED (failures=1, skipped=3)` out of 263 tests. The run's
own output did not name the test, and the next run of the identical tree passed.

**Best available reading, stated as a reading rather than a diagnosis.** It was a *failure*, not an
error. The only test in this project that can fail rather than error for environmental reasons is
`tests/test_core_banking_live.py`: its `_wait_until_healthy` raises `AssertionError` when the spawned
service does not answer `/health` within 20 seconds, and unittest counts a raised `AssertionError` as
a failure. That test also asks the OS for a free port, closes the socket, and then hands the number
to `uvicorn` — a window in which another process can take it. Both shapes are the ordinary flakiness
of spawning a real service on a real socket, and the machine was running other work at the time.

**It is not evidence about B1 or B2.** Every deterministic tier is in-process with no sockets and no
sleeps, and the red-team corpus was re-run 98 times with identical verdicts.

**What would settle it:** the failure name. The run was piped through `grep`, which is why the name
was lost.

**Acted on 2026-09-10 — the name can no longer be lost this way, and both suspected shapes are
narrowed.** Still unexplained; what changed is that a recurrence will be readable.

- **`make test` keeps each suite's whole output**, in `.test-output-voice-agent.log` and
  `.test-output-mock-core-banking.log`, whatever the caller does to the target's stdout. Both are
  gitignored and rewritten every run. Redirect-then-`cat` rather than `tee`, because `tee` returns
  its own exit status and would turn a red suite green, and `set -o pipefail` does not exist in the
  `/bin/sh` the ubuntu CI runners use. **Verified in both directions:** a deliberately failing test
  run as `make test | grep -E '^(Ran|OK|FAILED)'` — the exact shape that lost the name — exits
  non-zero and leaves the failing test's name in the log.
- **The live test retries a start on a fresh port**, three attempts, and the final failure carries
  every attempt's reason rather than only the last. This is aimed straight at the reading above:
  the free port is closed before `uvicorn` binds it, and a busy machine can miss a fixed deadline.
  A service that genuinely cannot start still fails all three, for the same reason each time, which
  is what distinguishes the two.
- **The spawned service's own output is kept instead of going to `DEVNULL`**, and its tail is
  reported on a failed start. A port collision and a broken import both used to arrive as
  "exited during startup with code 1"; forcing a real collision now prints
  `ERROR: [Errno 48] error while attempting to bind on address ... address already in use`.

The retry loop is driven against a stub in `TheStartupRetry`, which spawns nothing — issue #30's
"exactly one test" counts services started, not `TestCase` classes.

---

## Recorded up front, unchanged

**No real DTMF tone has ever been consumed by this system.** Phase 0 confirmed live, on calls 2 and
3, that tones *arrive* during active bidirectional streaming. Every line of code that acts on one is
new in this phase and is exercised only against fakes. This is the direct consequence of the phase
deploying nothing, and it closes at Phase 5's real-call exit.
