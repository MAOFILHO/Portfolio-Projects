"""Phase 8 ticket 3 -- the post-call pipeline, against fakes.

ADR-007 is the spine: the transcript is redacted in memory before it reaches anything persistent,
and a transcript that cannot be redacted is never written unredacted as a fallback. The tests carry
a marker string through the pipeline and look for it in every place something could be persisted or
sent onward -- at every point, not just the final state.
"""
import asyncio
import unittest
from unittest.mock import patch

from azbank_voice_agent.call_records.fake import FakeCallRecordStore, unavailable
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.postcall import pipeline
from azbank_voice_agent.postcall.capture import CallCapture
from azbank_voice_agent.postcall.fake import (
    FakeRedactor,
    FakeSummarizer,
    FakeTranscriptStore,
)

MARKER = "ACCT-SECRET-7788"


def _finished_capture(turns, end_reason="model_ended", auth_state=gate.AUTHENTICATED,
                      correlation_id="corr-1"):
    capture = CallCapture()
    for turn in turns:
        capture.add_delta(turn)
        capture.end_turn()
    capture.finish(correlation_id, end_reason, auth_state, len(turns), 4200)
    return capture


def _run(capture, redactor=None, summarizer=None, transcripts=None, call_records=None):
    call_records = call_records if call_records is not None else FakeCallRecordStore()
    asyncio.run(pipeline.run_postcall(
        capture, call_records=call_records,
        redactor=redactor, summarizer=summarizer, transcripts=transcripts,
    ))
    return call_records


def _wired(**overrides):
    parts = {
        "redactor": FakeRedactor(terms=(MARKER,)),
        "summarizer": FakeSummarizer(),
        "transcripts": FakeTranscriptStore(),
    }
    parts.update(overrides)
    return parts


TURNS = [f"Your account number is {MARKER}.", "Anything else today?"]


class NothingUnredactedReachesAnythingPersistent(unittest.TestCase):
    """ADR-007 Decision 3, proved across the whole run rather than on the final state."""

    def test_no_blob_write_carries_the_marker(self):
        parts = _wired()
        _run(_finished_capture(TURNS), **parts)
        self.assertTrue(parts["transcripts"].writes, "nothing was written -- the test proves nothing")
        for _, written in parts["transcripts"].writes:
            self.assertNotIn(MARKER, " ".join(written))

    def test_the_summarizer_only_ever_sees_redacted_text(self):
        parts = _wired()
        _run(_finished_capture(TURNS), **parts)
        self.assertTrue(parts["summarizer"].inputs)
        for seen in parts["summarizer"].inputs:
            self.assertNotIn(MARKER, " ".join(seen))

    def test_the_table_row_carries_no_marker_in_any_field(self):
        parts = _wired()
        store = _run(_finished_capture(TURNS), **parts)
        self.assertEqual(len(store.call_summaries), 1)
        for value in vars(store.call_summaries[0]).values():
            self.assertNotIn(MARKER, str(value))

    def test_no_log_line_carries_the_marker(self):
        with self.assertLogs(pipeline.log, level="DEBUG") as logged:
            _run(_finished_capture(TURNS), **_wired())
        self.assertNotIn(MARKER, "\n".join(logged.output))

    def test_the_detector_is_alive_a_leaky_redactor_is_caught(self):
        # Test the test: a redactor that changes nothing must put the marker in the blob, or the
        # four checks above would pass against any implementation.
        parts = _wired(redactor=FakeRedactor(terms=(MARKER,), leak=True))
        _run(_finished_capture(TURNS), **parts)
        written = " ".join(" ".join(t) for _, t in parts["transcripts"].writes)
        self.assertIn(MARKER, written)

    def test_the_redactor_is_handed_exactly_what_the_agent_said(self):
        parts = _wired()
        _run(_finished_capture(TURNS), **parts)
        self.assertEqual(parts["redactor"].inputs, [TURNS])


class ATranscriptThatCannotBeRedactedIsNeverWrittenAtAll(unittest.TestCase):
    """ADR-007 Decision 2: a missing transcript, not a delayed or an unredacted one."""

    def _assert_failed_closed(self, parts, store):
        self.assertEqual(parts["transcripts"].writes, [])
        self.assertEqual(parts["summarizer"].inputs, [])
        row = store.call_summaries[0]
        self.assertEqual(row.transcript_status, "redaction_failed")
        self.assertEqual(row.summary_status, "skipped")
        self.assertEqual(row.summary, "")

    def test_a_redaction_error(self):
        parts = _wired(redactor=FakeRedactor(fail_with=RuntimeError("Language is down")))
        store = _run(_finished_capture(TURNS), **parts)
        self._assert_failed_closed(parts, store)

    def test_a_redaction_that_returns_nonsense(self):
        for bad in (None, "a string", [1, 2], ["only one"]):
            parts = _wired(redactor=FakeRedactor(returns=bad))
            store = _run(_finished_capture(TURNS), **parts)
            self._assert_failed_closed(parts, store)

    def test_a_redaction_that_never_answers(self):
        parts = _wired(redactor=FakeRedactor(hang=True))
        with patch.object(pipeline, "STEP_DEADLINE_SECONDS", 0.05):
            store = _run(_finished_capture(TURNS), **parts)
        self._assert_failed_closed(parts, store)

    def test_no_redactor_configured_means_no_transcript_write_and_no_summary(self):
        parts = _wired(redactor=None)
        store = _run(_finished_capture(TURNS), **parts)
        self.assertEqual(parts["transcripts"].writes, [])
        self.assertEqual(parts["summarizer"].inputs, [])
        self.assertEqual(store.call_summaries[0].transcript_status, "not_configured")

    def test_the_failure_reason_is_logged_without_any_content(self):
        parts = _wired(redactor=FakeRedactor(fail_with=RuntimeError(f"echoed {MARKER}")))
        with self.assertLogs(pipeline.log, level="DEBUG") as logged:
            _run(_finished_capture(TURNS), **parts)
        self.assertNotIn(MARKER, "\n".join(logged.output))


class TheHappyPathWritesOneRedactedTranscriptAndOneRow(unittest.TestCase):
    def test_a_completed_call_lands_a_blob_and_a_row(self):
        parts = _wired()
        store = _run(_finished_capture(TURNS), **parts)
        [(correlation_id, written)] = parts["transcripts"].writes
        self.assertEqual(correlation_id, "corr-1")
        self.assertEqual(written, ["Your account number is [REDACTED].", "Anything else today?"])
        row = store.call_summaries[0]
        self.assertEqual(row.correlation_id, "corr-1")
        self.assertEqual(row.transcript_status, "stored")
        self.assertEqual(row.transcript_blob, parts["transcripts"].name_for("corr-1"))
        self.assertEqual(row.summary_status, "done")
        self.assertEqual(row.summary, FakeSummarizer.SUMMARY)
        self.assertEqual(row.intent, FakeSummarizer.INTENT)

    def test_the_row_carries_the_call_outcome_and_the_raw_end_reason(self):
        store = _run(_finished_capture(TURNS, end_reason="model_ended"), **_wired())
        row = store.call_summaries[0]
        self.assertEqual(row.call_outcome, "authenticated_served")
        self.assertEqual(row.end_reason, "model_ended")
        self.assertEqual(row.auth_state, gate.AUTHENTICATED)
        self.assertEqual(row.turn_count, 2)
        self.assertEqual(row.duration_ms, 4200)

    def test_every_end_reason_resolves_to_one_of_the_five_outcomes(self):
        from azbank_voice_agent.postcall import outcome
        for reason in sorted(outcome.KNOWN_END_REASONS):
            store = _run(_finished_capture(TURNS, end_reason=reason), **_wired())
            self.assertIn(store.call_summaries[0].call_outcome, outcome.CALL_OUTCOMES, reason)

    def test_a_call_with_no_correlation_id_still_gets_a_row_and_a_blob(self):
        parts = _wired()
        store = _run(_finished_capture(TURNS, correlation_id=None), **parts)
        row = store.call_summaries[0]
        self.assertTrue(row.correlation_id)
        self.assertEqual(parts["transcripts"].writes[0][0], row.correlation_id)


class ACallWithNothingToRedactStillGetsItsOutcomeRow(unittest.TestCase):
    def test_a_closed_call_touches_none_of_the_slow_dependencies(self):
        parts = _wired()
        store = _run(
            _finished_capture([], end_reason="closed", auth_state=gate.ANONYMOUS), **parts
        )
        self.assertEqual(parts["redactor"].inputs, [])
        self.assertEqual(parts["summarizer"].inputs, [])
        self.assertEqual(parts["transcripts"].writes, [])
        row = store.call_summaries[0]
        self.assertEqual(row.call_outcome, "closed_path")
        self.assertEqual(row.transcript_status, "none")
        self.assertEqual(row.summary_status, "skipped")


class EachStepFailsOnItsOwnWithoutTakingTheOthersDown(unittest.TestCase):
    def test_a_summary_failure_keeps_the_transcript_and_the_row(self):
        parts = _wired(summarizer=FakeSummarizer(fail_with=RuntimeError("model down")))
        store = _run(_finished_capture(TURNS), **parts)
        self.assertEqual(len(parts["transcripts"].writes), 1)
        row = store.call_summaries[0]
        self.assertEqual(row.transcript_status, "stored")
        self.assertEqual(row.summary_status, "failed")
        self.assertEqual(row.call_outcome, "authenticated_served")

    def test_no_summarizer_configured_is_skipped_not_failed(self):
        store = _run(_finished_capture(TURNS), **_wired(summarizer=None))
        self.assertEqual(store.call_summaries[0].summary_status, "not_configured")

    def test_a_blob_write_failure_still_summarises_the_redacted_text(self):
        parts = _wired(transcripts=FakeTranscriptStore(fail_with=RuntimeError("storage down")))
        store = _run(_finished_capture(TURNS), **parts)
        row = store.call_summaries[0]
        self.assertEqual(row.transcript_status, "write_failed")
        self.assertEqual(row.transcript_blob, "")
        self.assertEqual(row.summary_status, "done")

    def test_a_summary_that_never_answers_times_out(self):
        parts = _wired(summarizer=FakeSummarizer(hang=True))
        with patch.object(pipeline, "STEP_DEADLINE_SECONDS", 0.05):
            store = _run(_finished_capture(TURNS), **parts)
        self.assertEqual(store.call_summaries[0].summary_status, "failed")


class ThePipelineNeverRaisesIntoTheProcess(unittest.TestCase):
    def test_a_row_that_cannot_be_written_is_logged_and_swallowed(self):
        store = FakeCallRecordStore(fail_with=unavailable())
        with self.assertLogs(pipeline.log, level="ERROR"):
            _run(_finished_capture(TURNS), call_records=store, **_wired())

    def test_a_capture_that_was_never_finished_is_skipped_quietly(self):
        capture = CallCapture()
        capture.add_delta("hello")
        with self.assertLogs(pipeline.log, level="WARNING"):
            store = _run(capture, **_wired())
        self.assertEqual(store.call_summaries, [])

    def test_cancellation_is_not_swallowed(self):
        async def go():
            task = asyncio.create_task(pipeline.run_postcall(
                _finished_capture(TURNS), call_records=FakeCallRecordStore(),
                **_wired(redactor=FakeRedactor(hang=True)),
            ))
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        asyncio.run(go())


class ThePipelineLogsOutcomesNeverWords(unittest.TestCase):
    def test_a_normal_run_logs_at_least_one_line_and_none_carry_transcript_text(self):
        with self.assertLogs(pipeline.log, level="DEBUG") as logged:
            _run(_finished_capture(TURNS), **_wired())
        text = "\n".join(logged.output)
        for word in ("Anything else today", "account number"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
