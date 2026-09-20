"""B2 — the PIN, and the caller's phone number, appear in no log record produced anywhere in this
run (issue #39, widened by issue #65).

B2 (CLAUDE.md, wording widened 2026-09-15): neither the DTMF PIN nor the caller's phone number
appears in any transcript, log line, persisted record, or OpenTelemetry content channel -- span
attribute, span-event attribute, log record, or completion-hook upload. **Target: 0 occurrences,
blocking.** For two phases this project enforced that discipline defensively with nothing sensitive
to protect. This is the phase it was written for.

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
import contextlib
import dataclasses
import logging
import pathlib
import re
import tempfile
import unittest

from azbank_voice_agent.call_records import REASONS, EscalationRecord
from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.observability import telemetry
from azbank_voice_agent.postcall import pipeline
from azbank_voice_agent.postcall.capture import CallCapture
from azbank_voice_agent.postcall.fake import (
    FakeRedactor,
    FakeSummarizer,
    FakeTranscriptStore,
)
from azbank_voice_agent.realtime.fake import (
    FakeRealtimeServer,
    function_call,
    response_done,
)
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame, dtmf_frame
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from keyed_values import SECRETS
    from telemetry_harness import run_traced_call
except ImportError:  # running one file as `python -m unittest tests.test_zz_b2_leak_scan`
    from tests.keyed_values import SECRETS
    from tests.telemetry_harness import run_traced_call

#: Every record every logger emitted, in order. Held as records rather than strings so both the
#: rendered message and the raw arguments can be checked.
CAPTURED = []

#: This suite's own source, read as text by the static guard below.
TESTS_DIR = pathlib.Path(__file__).resolve().parent

#: A four-digit string handed to something that keys a tone, as it looks from the outside -- read
#: as text, without importing or running anything.
#:
#: **Three alternatives, not two, and the comment here used to say two** (/code-review, 2026-09-10).
#: `_keyed` and `dtmf_frame` are the two ways this suite actually submits a credential today.
#: `tuple` matches nothing in the tree right now and is kept deliberately: `redteam_harness.POINTS`
#: already builds keypress sequences with `tuple(...)`, so `tuple("9999")` is the obvious next way
#: to write one, and a detector that over-matches costs nothing while a detector that under-matches
#: is the exact failure this guard exists to prevent. An unused alternative in a scanner is
#: insurance; the miscount was the defect.
_KEYED_LITERAL = re.compile(r"""(?:_keyed|dtmf_frame|tuple)\(\s*["'](\d{4})["']""")

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


#: A synthetic caller phone number, E.164-shaped, for B2's span-attribute scan (issue #61). No real
#: caller phone number exists anywhere in this project -- D8's whole design is that the number is
#: protected by never being read off the `IncomingCall` event in the first place -- so this is not
#: a secret the code holds, it is a value the scanner needs to look for, the same standing
#: `DEFAULT_PIN` already has in `core_banking/fake.py`. Kept here rather than in
#: `tests/keyed_values.py`: that file is specifically credentials the suite keys through the DTMF
#: path (its own docstring), and a phone number is neither a credential nor ever keyed.
FAKE_CALLER_PHONE_NUMBER = "+15550001234"


def offending_span_attributes(spans, secrets=(*SECRETS, FAKE_CALLER_PHONE_NUMBER)):
    """Every span attribute value carrying a secret, whole. B2's fourth surface (issue #61) --
    span attributes are never filtered by value (`AllowlistSpanProcessor` drops by key only), so
    this is the net that has to hold given that."""
    return [
        (span.name, key, rendered)
        for span in spans
        for key, value in span.attributes.items()
        for rendered in [str(value)]
        for secret in secrets
        if secret in rendered
    ]


def offending_span_event_attributes(spans, secrets=(*SECRETS, FAKE_CALLER_PHONE_NUMBER)):
    """Every span-event attribute value carrying a secret, whole. B2's widened wording's second
    OpenTelemetry channel (issue #65) -- content recorded on a span *event* rather than the span
    itself. `AllowlistSpanProcessor` does not reach this: D9's filter drops span attribute keys
    only (its own docstring), and `offending_span_attributes` above does not see it either, because
    `ReadableSpan.attributes` and `ReadableSpan.events[*].attributes` are two different mappings."""
    return [
        (span.name, event.name, key, rendered)
        for span in spans
        for event in span.events
        for key, value in event.attributes.items()
        for rendered in [str(value)]
        for secret in secrets
        if secret in rendered
    ]


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


@contextlib.contextmanager
def _a_temporary_test_source(line):
    """A throwaway directory holding one .py file, for the two rehearsals above.

    A real file rather than a patched-in string, so the rehearsal exercises the same `glob` and
    `read_text` path the guard uses in earnest -- a rehearsal against a different mechanism proves
    nothing about the mechanism.
    """
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory)
        (path / "test_rehearsal.py").write_text(line + "\n")
        yield path


def credentials_this_suite_keys(directory=TESTS_DIR):
    """Every four-digit credential literal appearing in this suite's own source.

    Read off the source rather than collected at runtime, deliberately: a runtime registry would
    only see the values that ran, so a test skipped on this machine could park an unscanned
    credential in the tree indefinitely. Reading the text sees every one of them whether it ran or
    not, and a value that is never keyed at all costs nothing but an entry in the list.
    """
    found = set()
    for path in sorted(directory.glob("*.py")):
        if path.resolve() == pathlib.Path(__file__).resolve():
            # This module's own source, skipped: the two rehearsals below quote a keyed literal as
            # a *string* in order to test the pattern, and scanning them would report that
            # rehearsal fixture as an unregistered credential every run. Nothing here keys a tone
            # for real -- this is the scanner, not a caller -- so there is nothing to miss.
            continue
        found.update(_KEYED_LITERAL.findall(path.read_text()))
    return found


class TheSecretListCannotFallBehindTheSuite(unittest.TestCase):
    """The seam that was open (/code-review, 2026-09-10).

    `SECRETS` used to be written by hand with nothing tying it to what the suite keyed, so a test
    added later that submitted a new wrong credential would have been outside the detector and
    nothing would have said so. B2 is *0 occurrences, blocking* -- a detector that silently stops
    covering part of what it is supposed to cover is the one failure mode that cannot be allowed to
    be quiet.
    """

    def test_every_credential_the_suite_keys_is_one_the_scan_looks_for(self):
        missing = sorted(credentials_this_suite_keys() - set(SECRETS))
        self.assertEqual(
            missing, [],
            "these credentials are keyed by the suite but are outside B2's run-wide scan; "
            "add them to tests/keyed_values.py: " + ", ".join(missing),
        )

    def test_the_guard_notices_a_credential_that_was_never_registered(self):
        """The rehearsal, following `TheDetectorItselfWorks` above.

        A guard that reported "nothing missing" because its pattern matched nothing would pass
        forever. This runs the same pattern over a source file that keys a credential deliberately
        left out of `SECRETS`, and requires it to be found.
        """
        with_a_stray = self.enterContext(_a_temporary_test_source('_keyed("5150")'))
        self.assertEqual(credentials_this_suite_keys(with_a_stray) - set(SECRETS), {"5150"})

    def test_the_pattern_does_not_match_an_arbitrary_four_digit_number(self):
        # The other direction: a pattern that matched every four-digit run in the tree would flag
        # port numbers and years, and the list would grow until it meant nothing.
        with_a_year = self.enterContext(_a_temporary_test_source('timeout_ms = 5150'))
        self.assertEqual(credentials_this_suite_keys(with_a_year), set())


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


def offending_records_in_the_call_record_stores(secrets=SECRETS):
    """Every credential found in anything a call-record store held during this run (issue #53).

    **B2 names persisted records**, and Phase 5 created the first ones the voice agent owns: the
    escalation records and the day's ledger. In CI there is no Table Storage to scan, so the
    artifact is whatever the run's stores actually held -- swept from `FakeCallRecordStore.WRITTEN`,
    which every store registers itself in, for the same reason the log capture is run-wide rather
    than per-test: a scan each test has to remember to ask for is a scan that stops covering things
    quietly.

    Every field of every record is stringified and searched, with **no carve-out for any column**.
    A scan that had to skip a field would be a scan that could be made to pass by moving the leak
    into it -- the same rule that lets the SQLite scan cover the database file whole.
    """
    offenders = []
    for store in FakeCallRecordStore.WRITTEN:
        for record in store.escalations:
            for field, value in dataclasses.asdict(record).items():
                if _carries(value, secrets):
                    offenders.append(("escalation", field, value))
        for day, minutes in store.minutes.items():
            if _carries(day, secrets) or _carries(minutes, secrets):
                offenders.append(("ledger", day, minutes))
        # Phase 8: the post-call summary row, every field, same no-carve-out rule.
        for record in store.call_summaries:
            for field, value in dataclasses.asdict(record).items():
                if _carries(value, secrets):
                    offenders.append(("call_summary", field, value))
    return offenders


def _carries(value, secrets):
    """Does this field hold a credential? **Matched by type, not by one rule for everything.**

    A **text** field is substring-matched, exactly as a log record is: a credential smuggled into a
    correlation id or a reason code is a credential in a persisted record, wherever in the string it
    sits.

    A **numeric** field is compared as a number. That is not a carve-out -- it is the correct
    matcher for the type, and it is strictly *more* precise than the substring rule rather than
    weaker: a PIN written into a numeric column arrives as `1234.0` and is caught, while the day's
    accumulated minutes are not accused of carrying "9999" because their decimal expansion happens
    to contain it.

    It had to be this way round, and the scan is what proved it: the ledger's minutes are a genuine
    float of a genuine measurement, and substring-matching their seventeen significant digits turned
    a constraint meaning "none found" into one that failed at random. That is the same defect the
    digit-free frame ids exist to prevent, arriving through a new door -- and the answer there was
    to stop the value being able to spell a credential, which is not available here because a
    measurement is not an identifier anybody gets to choose.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return any(secret in str(value) for secret in secrets)
    return any(float(secret) == float(value) for secret in secrets)


class NoPinReachedAPersistedRecordAnywhereInThisRun(unittest.TestCase):
    """B2's fourth surface, over the records this phase introduced (issue #53).

    B2's original wording named four surfaces: transcripts, log lines, OTel span attributes, and
    persisted records. All four are covered as of this file: transcripts and log lines by the
    run-wide log capture above, persisted records by this class, and span attributes below. The
    2026-09-15 widening (issue #65) added two values (the PIN, now also the caller's phone number)
    and split "OTel span attribute" into four OpenTelemetry channels -- span attribute and
    span-event attribute (both scanned below), plus the log pipeline and completion-hook upload,
    covered by `tests/test_b2_content_recording.py` (the upload hook pre-existing since Phase 4;
    the logging-pipeline check added alongside this file's own changes for issue #65).
    """

    def test_the_suite_really_wrote_some_records_to_scan(self):
        # Without this, a scan over an empty collection would report "0 occurrences" forever --
        # which is the vacuous-pass failure the deliberate-leak self-test exists to prevent for the
        # log scan, applied to this one.
        written = [store for store in FakeCallRecordStore.WRITTEN if store.escalations]
        self.assertTrue(written, "no escalation record was written anywhere in this run")

    def test_the_ledger_was_written_too(self):
        charged = [store for store in FakeCallRecordStore.WRITTEN if store.minutes]
        self.assertTrue(charged, "no minutes were recorded anywhere in this run")

    def test_no_persisted_record_carries_a_credential(self):
        offenders = offending_records_in_the_call_record_stores()
        self.assertEqual(
            offenders, [],
            f"B2 breach: {len(offenders)} persisted record(s) carried a credential. "
            f"First: {offenders[0]}" if offenders else "",
        )

    def test_the_scan_would_catch_one(self):
        """The deliberate leak, following `TheDetectorItselfWorks`.

        A scanner that silently stopped working would pass forever, so one is planted. The record is
        built directly rather than through a call, because no call path can produce one -- which is
        the property the test above asserts and this one proves is genuinely being checked.
        """
        planted = FakeCallRecordStore()
        planted.escalations.append(
            EscalationRecord(
                correlation_id=f"corr-{SECRETS[0]}", reason=REASONS[0],
                occurred_at="2026-09-11T10:00:00Z",
            )
        )
        self.addCleanup(FakeCallRecordStore.WRITTEN.remove, planted)
        self.assertTrue(offending_records_in_the_call_record_stores())

    def test_span_attributes_are_now_scanned_rather_than_reported_uncovered(self):
        """B2's fourth surface, covered rather than reported uncovered (issue #61, Phase 6).

        This test used to assert that nothing in the tree emitted a span at all, which was this
        surface's only honest standing before this phase. That import now exists
        (`observability/telemetry.py`), so the surface is real and this is its scan: every span
        attribute value, from a real fake call, checked against the two literals B2 names -- the
        PIN and the caller's phone number (`docs/phase6/exit-criteria.md` D7). **One channel**: span
        attributes, the one this phase's own code can actually put something on. The four-channel,
        two-value wording in `docs/phase6/exit-criteria.md`'s proposed B2 text is out of scope by
        decision (issue #61's own "Out of Scope") -- this is the existing, one-channel B2 test,
        extended to the surface this phase adds, not a bid to enforce the wider wording.
        """
        transport = FakeTransport(
            frames=[*(dtmf_frame(digit) for digit in DEFAULT_PIN), audio_frame("balance-please")],
            hang=True,
        )
        realtime = FakeRealtimeServer(
            events=[function_call("get_balance", '{"account": "chequing"}'), response_done()],
            respond_after_appends=1,
        )
        spans = run_traced_call(
            run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore())
        )
        self.assertTrue(spans, "the call produced no spans at all -- nothing was actually exercised")
        self.assertEqual(offending_span_attributes(spans), [])

    def test_the_span_scan_would_catch_a_planted_pin_or_phone_number(self):
        """The deliberate leak, following `TheDetectorItselfWorks` above -- now for spans.

        Built directly on a span rather than through a call, exactly as the persisted-record
        rehearsal above is: no call path can produce either planted value (verify_pin/D8), so this
        is what proves the scanner is genuinely checking rather than vacuously passing. Values are
        never filtered by `AllowlistSpanProcessor` (its own docstring: "keys, never values"), so an
        allowed key is all a planted leak needs.
        """
        for planted in (f"leaked-{DEFAULT_PIN}", FAKE_CALLER_PHONE_NUMBER):
            with self.subTest(planted=planted):
                exporter = InMemorySpanExporter()
                provider = telemetry.build_tracer_provider(exporter)
                with provider.get_tracer("test").start_as_current_span(telemetry.CALL) as span:
                    span.set_attribute("correlation_id", planted)
                provider.force_flush()
                self.assertTrue(offending_span_attributes(exporter.get_finished_spans()))

    def test_no_span_event_carries_a_pin_or_phone_number(self):
        """B2's widened second OpenTelemetry channel (issue #65), read from the same real call
        `test_span_attributes_are_now_scanned_rather_than_reported_uncovered` above already
        exercises. This project's own code creates no span events today -- confirmed against
        `observability/telemetry.py` and every span-creation call site in `realtime/`/`dispatch/` --
        so this passes vacuously; the next test is what proves the scanner would catch one if that
        ever changes, following `TheDetectorItselfWorks`'s own pattern for why that pairing matters.
        """
        transport = FakeTransport(
            frames=[*(dtmf_frame(digit) for digit in DEFAULT_PIN), audio_frame("balance-please")],
            hang=True,
        )
        realtime = FakeRealtimeServer(
            events=[function_call("get_balance", '{"account": "chequing"}'), response_done()],
            respond_after_appends=1,
        )
        spans = run_traced_call(
            run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore())
        )
        self.assertTrue(spans, "the call produced no spans at all -- nothing was actually exercised")
        self.assertEqual(offending_span_event_attributes(spans), [])

    def test_the_span_event_scan_would_catch_a_planted_pin_or_phone_number(self):
        """The deliberate leak, following `TheDetectorItselfWorks` above -- now for span events.
        Built directly on a span rather than through a call, exactly as the persisted-record and
        span-attribute rehearsals above are: no call path can produce either planted value
        (verify_pin/D8), so this is what proves the scanner is genuinely checking rather than
        vacuously passing."""
        for planted in (f"leaked-{DEFAULT_PIN}", FAKE_CALLER_PHONE_NUMBER):
            with self.subTest(planted=planted):
                exporter = InMemorySpanExporter()
                provider = telemetry.build_tracer_provider(exporter)
                with provider.get_tracer("test").start_as_current_span(telemetry.CALL) as span:
                    span.add_event("planted-event", {"detail": planted})
                provider.force_flush()
                self.assertTrue(offending_span_event_attributes(exporter.get_finished_spans()))


def offending_stored_transcripts(secrets=(*SECRETS, FAKE_CALLER_PHONE_NUMBER)):
    """Every credential found in any transcript the post-call pipeline wrote during this run.

    Phase 8's fifth persisted surface (ADR-007): the redacted transcript in Blob. Swept from
    `FakeTranscriptStore.WRITTEN` for the same run-wide reason the call-record sweep is, and over
    the whole blob name and every turn with no carve-out.
    """
    offenders = []
    for store in FakeTranscriptStore.WRITTEN:
        for correlation_id, turns in store.writes:
            for value in (correlation_id, *turns):
                if _carries(value, secrets):
                    offenders.append(("transcript", correlation_id, value))
    return offenders


def _a_call_whose_agent_speaks_the_credentials():
    """The worst case ADR-007 exists for: the agent reads a PIN and a phone number back aloud."""
    capture = CallCapture()
    for turn in (
        f"I heard {DEFAULT_PIN}, is that right?",
        f"And you are calling from {FAKE_CALLER_PHONE_NUMBER}.",
    ):
        capture.add_delta(turn)
        capture.end_turn()
    capture.finish("corr-b2-transcript", "model_ended", gate.AUTHENTICATED, 2, 1000)
    return capture


class NoCredentialReachedAStoredTranscriptOrSummaryRowInThisRun(unittest.TestCase):
    """B2 over the post-call pipeline's two outputs (Phase 8, ADR-007)."""

    @classmethod
    def setUpClass(cls):
        import asyncio
        cls.store = FakeCallRecordStore()
        cls.transcripts = FakeTranscriptStore()
        asyncio.run(pipeline.run_postcall(
            _a_call_whose_agent_speaks_the_credentials(),
            pipeline.PostcallServices(
                call_records=cls.store,
                redactor=FakeRedactor(terms=(DEFAULT_PIN, FAKE_CALLER_PHONE_NUMBER)),
                summarizer=FakeSummarizer(),
                transcripts=cls.transcripts,
            ),
        ))

    def test_the_pipeline_really_wrote_a_transcript_and_a_row_to_scan(self):
        self.assertTrue(self.transcripts.writes)
        self.assertTrue(self.store.call_summaries)

    def test_no_stored_transcript_carries_a_pin_or_phone_number(self):
        self.assertEqual(offending_stored_transcripts(), [])

    def test_no_call_summary_row_carries_a_credential(self):
        self.assertEqual(offending_records_in_the_call_record_stores(), [])

    def test_the_transcript_scan_would_catch_a_leak(self):
        planted = FakeTranscriptStore()
        planted.writes.append(("corr-x", [f"leaked {DEFAULT_PIN}"]))
        self.addCleanup(FakeTranscriptStore.WRITTEN.remove, planted)
        self.assertTrue(offending_stored_transcripts())

    def test_the_summary_row_scan_would_catch_a_leak(self):
        from azbank_voice_agent.call_records import CallSummaryRecord
        planted = FakeCallRecordStore()
        planted.call_summaries.append(CallSummaryRecord(
            correlation_id="corr-y", call_outcome="error", end_reason="error", auth_state="anonymous",
            turn_count=1, duration_ms=1, occurred_at="2026-09-19T10:00:00Z",
            transcript_status="none", transcript_blob="", summary_status="done",
            summary=f"caller said {FAKE_CALLER_PHONE_NUMBER}", intent="x",
        ))
        self.addCleanup(FakeCallRecordStore.WRITTEN.remove, planted)
        self.assertTrue(offending_records_in_the_call_record_stores(
            secrets=(*SECRETS, FAKE_CALLER_PHONE_NUMBER)
        ))
