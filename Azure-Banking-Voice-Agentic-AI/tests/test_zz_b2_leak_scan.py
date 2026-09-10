"""B2 — the PIN appears in no log record produced anywhere in this run (issue #39).

B2 (CLAUDE.md): the DTMF PIN never appears in any transcript, log line, OTel span attribute, or
persisted record. **Target: 0 occurrences, blocking.** For two phases this project enforced that
discipline defensively with nothing sensitive to protect. This is the phase it was written for.

---

**Why this file is named to sort last.** `unittest discover` imports every test module before
running any test, then runs them in sorted module order. The capture below is installed at *import*
time, so it is in place before the first test executes; the assertion has to run after the last one,
and a name that sorts after `test_whole_call` is how a stdlib `unittest` run expresses that. Sorting
is deterministic, not incidental -- `unittest.TestLoader` sorts explicitly.

**Why `unittest` rather than a pytest autouse fixture.** `docs/phase4/exit-criteria.md` criterion 10
asks for an autouse fixture. This project runs stdlib `unittest discover` from its `Makefile` and
says so explicitly. The criterion's intent -- blocking by construction rather than a CI step someone
can drop -- is met by installing the capture from the suite itself: there is no extra command, and
nothing to forget. Adding a test runner in the phase whose diffs are the most security-sensitive is
a larger change than the mechanism is worth. Recorded in `docs/phase4/findings.md` rather than
substituted silently.

**Why `Logger.handle` and not a root handler.** A handler on the root logger looks like the obvious
way to catch everything and quietly is not: `assertLogs` replaces the target logger's handlers and
sets `propagate = False` for the duration of the block, so every record emitted inside one -- and
this suite is full of them, on exactly the modules that touch the PIN -- would never reach it. That
is a detector that passes because it is looking the wrong way. `Logger.handle` runs for every record
any logger actually emits, whatever the handlers are and whether or not it propagates.

**Why both the rendered message and the raw arguments.** A PIN passed as a lazy formatting argument
-- `log.info("checking %s", pin)` -- never appears in a rendered message at all until something
formats it, which in production is the handler and in a test is nothing. Checking only the rendered
form would miss the single most likely way this breaks.

**What this scan deliberately does not catch, and what does.** It looks for the submitted values
whole. Four records reading "1", "2", "3", "4" carry the PIN between them and contain no substring
of it in any one of them, so no substring rule of any width can see that -- and widening the rule to
single digits would flag "attempt 1 of 3" and every port number in the suite. The digit-by-digit
leak is caught precisely instead, at the seam where it could happen: the relay's own logger has no
legitimate reason to emit a decimal digit while a caller is keying, and
`tests/test_whole_call.py::test_the_relay_logs_no_decimal_digit_at_all_while_a_pin_is_being_keyed`
asserts that it emits none. The two rules together are the coverage; neither alone is.
"""
import logging
import unittest

from azbank_voice_agent.core_banking.fake import DEFAULT_PIN

#: Every record every logger emitted, in order. Held as records rather than strings so both the
#: rendered message and the raw arguments can be checked.
CAPTURED = []

#: What must not appear. The demo PIN, and the digit strings the suite keys as wrong ones -- a
#: rejected credential is no less confidential than an accepted one, and a detector that only
#: looked for the right PIN would miss a log line that recorded everything the caller tried.
SECRETS = (DEFAULT_PIN, "9999", "8888", "7777")

_original_handle = logging.Logger.handle


def _capturing_handle(self, record):
    CAPTURED.append(record)
    return _original_handle(self, record)


# Installed at import, which discovery does before it runs anything. Never uninstalled: the run is
# the scope, and a detector that could be switched off partway through is not one.
logging.Logger.handle = _capturing_handle

# So that a record which *would* be emitted in production is emitted here too. A logger left at
# WARNING never creates its INFO records at all, and a leak inside one of those would be invisible
# to any detector -- including this one -- for the entirely wrong reason.
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)


def offending_records(records=None, secrets=SECRETS):
    """Every captured record carrying a secret, with the reason. Empty is the passing state."""
    found = []
    for record in CAPTURED if records is None else records:
        try:
            rendered = record.getMessage()
        except Exception:  # noqa: BLE001 - a record that cannot render is still worth checking
            rendered = str(record.msg)
        arguments = repr(record.args)
        for secret in secrets:
            if secret in rendered:
                found.append((record.name, "rendered message", rendered))
            elif secret in arguments:
                found.append((record.name, "raw arguments", arguments))
    return found


class TheDetectorItselfWorks(unittest.TestCase):
    """A scanner that quietly stopped working would pass forever (issue #39).

    Follows the successor-boot rehearsal's precedent: a test that arranges an otherwise impossible
    condition and says so in its own docstring. Without it, deleting the capture above or breaking
    the comparison would turn every assertion in this file green.
    """

    def test_a_deliberate_leak_is_caught_in_a_rendered_message(self):
        """**This test leaks the PIN on purpose.** It is the only place in this project that does.

        It cleans up after itself, so the run-wide assertion below does not see what it emitted.
        """
        before = len(CAPTURED)
        # Formatted eagerly, on purpose: this is the leak that lands in the rendered message, and
        # the next test is the one that lands only in the arguments.
        logging.getLogger("b2-detector-rehearsal").warning(f"the PIN is {DEFAULT_PIN}")
        try:
            self.assertTrue(offending_records(CAPTURED[before:]))
        finally:
            del CAPTURED[before:]
        self.assertEqual(offending_records(CAPTURED[before:]), [])

    def test_a_deliberate_leak_is_caught_in_a_lazy_formatting_argument(self):
        """The one a rendered-message-only scanner would miss, which is why both are checked."""
        before = len(CAPTURED)
        logging.getLogger("b2-detector-rehearsal").warning("the PIN is %s", DEFAULT_PIN)
        try:
            leaked = offending_records(CAPTURED[before:])
            self.assertTrue(leaked)
        finally:
            del CAPTURED[before:]

    def test_the_capture_is_actually_installed(self):
        # If the patch above were reverted or overwritten, every other assertion here would pass
        # against an empty list. This is what makes "0 occurrences" mean "none found" rather than
        # "none looked for".
        self.assertIs(logging.Logger.handle, _capturing_handle)
        self.assertGreater(len(CAPTURED), 0, "the run produced no log records at all")

    def test_a_record_with_no_secret_in_it_is_not_flagged(self):
        # The other direction: a detector that flagged everything would also pass the test above.
        before = len(CAPTURED)
        logging.getLogger("b2-detector-rehearsal").info("caller authenticated")
        try:
            self.assertEqual(offending_records(CAPTURED[before:]), [])
        finally:
            del CAPTURED[before:]


class NoPinReachedALogRecordAnywhereInThisRun(unittest.TestCase):
    """The constraint itself: 0 occurrences, across every record this whole run produced."""

    def test_no_captured_record_carries_a_pin(self):
        offenders = offending_records()
        self.assertEqual(
            offenders, [],
            f"B2 breach: {len(offenders)} log record(s) carried a PIN. "
            f"First: logger={offenders[0][0]!r} via {offenders[0][1]}" if offenders else "",
        )


if __name__ == "__main__":
    unittest.main()
