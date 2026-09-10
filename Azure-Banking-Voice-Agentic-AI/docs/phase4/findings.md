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

---

## Recorded up front, unchanged

**No real DTMF tone has ever been consumed by this system.** Phase 0 confirmed live, on calls 2 and
3, that tones *arrive* during active bidirectional streaming. Every line of code that acts on one is
new in this phase and is exercised only against fakes. This is the direct consequence of the phase
deploying nothing, and it closes at Phase 5's real-call exit.
