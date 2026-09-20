"""Phase 8 ticket 2 -- what the relay hands the post-call pipeline when a call ends.

`run_call` fills an optional `CallCapture` as the call runs: the agent's words, one entry per
response (D14: agent speech only, caller speech is never transcribed), and how the call ended.
Exit criterion 4 is the point of most of this file: attaching a capture must not change a single
thing the call does -- same frames, same events consumed, same cap behaviour.
"""
import asyncio
import time
import unittest
from unittest.mock import patch

from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.cost import caps
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.postcall.capture import CallCapture
from azbank_voice_agent.realtime.fake import (
    FakeRealtimeServer,
    audio_delta,
    function_call,
    response_done,
    transcript_delta,
)
from azbank_voice_agent.realtime.session import run_call, run_closed_call
from azbank_voice_agent.transport.fake import FakeTransport


def _run(events, capture=None, transport=None, correlation_id=None):
    realtime = FakeRealtimeServer(events=events)
    transport = transport or FakeTransport()
    asyncio.run(run_call(
        transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore(),
        correlation_id=correlation_id, capture=capture,
    ))
    return transport, realtime


class TheCaptureHoldsWhatTheAgentSaid(unittest.TestCase):
    def test_deltas_within_one_response_join_into_one_turn(self):
        capture = CallCapture()
        _run([transcript_delta("Hi, "), transcript_delta("how can I help?"), response_done()], capture)
        self.assertEqual(capture.agent_turns, ["Hi, how can I help?"])

    def test_each_response_is_its_own_turn_in_order(self):
        capture = CallCapture()
        _run([
            transcript_delta("First."), response_done(),
            transcript_delta("Second."), response_done(),
        ], capture)
        self.assertEqual(capture.agent_turns, ["First.", "Second."])

    def test_a_tool_call_only_response_adds_no_empty_turn(self):
        capture = CallCapture()
        _run([function_call("get_balance", "{}"), response_done(),
              transcript_delta("Done."), response_done()], capture)
        self.assertEqual(capture.agent_turns, ["Done."])

    def test_words_still_in_flight_when_the_call_ends_are_kept(self):
        # The caller hangs up mid-sentence: no response.done ever arrives for that turn.
        capture = CallCapture()
        _run([transcript_delta("Your balance is")], capture)
        self.assertEqual(capture.agent_turns, ["Your balance is"])

    def test_the_capture_never_holds_audio(self):
        capture = CallCapture()
        _run([audio_delta("AUDIOBYTES"), transcript_delta("Hello."), response_done()], capture)
        self.assertNotIn("AUDIOBYTES", repr(capture.__dict__))


class TheCaptureKnowsHowTheCallEnded(unittest.TestCase):
    def test_a_call_that_ends_with_the_caller_hanging_up(self):
        capture = CallCapture()
        _run([response_done()], capture, correlation_id="abc-123")
        self.assertEqual(capture.correlation_id, "abc-123")
        self.assertEqual(capture.auth_state, gate.ANONYMOUS)
        self.assertEqual(capture.turn_count, 1)
        self.assertIsNotNone(capture.end_reason)
        self.assertGreaterEqual(capture.duration_ms, 0)

    def test_a_call_that_hits_the_turn_cap_says_so(self):
        capture = CallCapture()
        # The transport stays open, so the cap is the only thing that can end this call -- a
        # transport that disconnects at once would race the cap, and the relay reports whichever
        # finished task it visits last.
        with patch.object(caps, "MAX_CALL_TURNS", 1):
            _run([response_done(), response_done()], capture, transport=FakeTransport(hang=True))
        self.assertEqual(capture.end_reason, "cost_cap")

    def test_the_capture_is_finished_even_when_the_relay_fails(self):
        capture = CallCapture()
        realtime = FakeRealtimeServer(events=[])
        with patch.object(realtime, "send", side_effect=RuntimeError("boom")), \
             self.assertRaises(RuntimeError):
            asyncio.run(run_call(
                FakeTransport(), realtime, FakeCoreBankingClient(), FakeCallRecordStore(),
                capture=capture,
            ))
        self.assertEqual(capture.end_reason, "error")

    def test_the_capture_is_finished_even_when_the_ledger_write_is_cancelled(self):
        # The capture is finished in the inner `finally` around the ledger write; a task cancelled
        # during that write must not leave it unfinished, or the pipeline skips the call and no
        # outcome row is ever written.
        class CancelledDuringTheWrite(FakeCallRecordStore):
            async def record_minutes(self, day, minutes):
                raise asyncio.CancelledError

        capture = CallCapture()
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_call(
                FakeTransport(), FakeRealtimeServer(events=[response_done()]),
                FakeCoreBankingClient(), CancelledDuringTheWrite(), capture=capture,
            ))
        self.assertIsNotNone(capture.end_reason)

    def test_the_recorded_duration_is_the_calls_not_the_ledger_writes(self):
        class SlowLedger(FakeCallRecordStore):
            entered = None

            async def record_minutes(self, day, minutes):
                self.entered = time.monotonic()
                await asyncio.sleep(0.05)

        ledger = SlowLedger()
        capture = CallCapture()
        began = time.monotonic()
        asyncio.run(run_call(
            FakeTransport(), FakeRealtimeServer(events=[response_done()]),
            FakeCoreBankingClient(), ledger, capture=capture,
        ))
        # The duration was taken before the ledger write began, so it cannot exceed the time from
        # the start of the run to that moment (+1 ms for rounding) -- whatever the machine's speed.
        self.assertLessEqual(capture.duration_ms, (ledger.entered - began) * 1000 + 1)

    def test_a_capture_that_raises_cannot_skip_the_ledger_charge(self):
        # B4: a cap that undercounts fails open. The day is charged before the capture is finished,
        # so a broken capture costs a row and never a minute.
        class BrokenCapture(CallCapture):
            def finish(self, *args):
                raise RuntimeError("boom")

        ledger = FakeCallRecordStore()
        with self.assertRaises(RuntimeError):
            asyncio.run(run_call(
                FakeTransport(), FakeRealtimeServer(events=[response_done()]),
                FakeCoreBankingClient(), ledger, capture=BrokenCapture(),
            ))
        self.assertTrue(ledger.minutes)


class AttachingACaptureChangesNothingAboutTheCall(unittest.TestCase):
    """Exit criterion 4: the same scripted call, with and without a capture."""

    EVENTS = staticmethod(lambda: [
        audio_delta("a1"), transcript_delta("Hello."), response_done(),
        audio_delta("a2"), transcript_delta("Anything else?"), response_done(),
    ])

    def test_the_same_frames_go_to_the_caller_and_the_model(self):
        bare_transport, bare_rt = _run(self.EVENTS())
        cap_transport, cap_rt = _run(self.EVENTS(), capture=CallCapture())
        self.assertEqual(bare_transport.sent, cap_transport.sent)
        self.assertEqual(bare_rt.sent_types, cap_rt.sent_types)
        self.assertEqual(bare_rt.consumed, cap_rt.consumed)

    def test_the_turn_cap_stops_the_call_at_the_same_place(self):
        with patch.object(caps, "MAX_CALL_TURNS", 2):
            _, bare_rt = _run([response_done() for _ in range(5)])
            _, cap_rt = _run([response_done() for _ in range(5)], capture=CallCapture())
        self.assertEqual(bare_rt.consumed, cap_rt.consumed)
        self.assertEqual(cap_rt.consumed, 2)

    def test_the_relay_never_waits_on_anything_the_capture_does(self):
        # The capture is plain in-memory bookkeeping: none of its methods is a coroutine, so the
        # relay cannot be made to await it.
        for name in ("add_delta", "end_turn", "finish"):
            self.assertFalse(asyncio.iscoroutinefunction(getattr(CallCapture, name)), name)


class TheClosedPathFillsACaptureToo(unittest.TestCase):
    def test_a_closed_call_records_that_it_was_closed_and_holds_no_words(self):
        capture = CallCapture()
        realtime = FakeRealtimeServer(
            events=[audio_delta("were-closed"), response_done()], respond_after_appends=0,
        )
        asyncio.run(run_closed_call(
            FakeTransport(), realtime, FakeCallRecordStore(),
            correlation_id="closed-1", capture=capture,
        ))
        self.assertEqual(capture.end_reason, "closed")
        self.assertEqual(capture.auth_state, gate.ANONYMOUS)
        self.assertEqual(capture.agent_turns, [])
        self.assertEqual(capture.correlation_id, "closed-1")

    def test_a_closed_call_is_finished_even_when_the_ledger_write_is_cancelled(self):
        class CancelledDuringTheWrite(FakeCallRecordStore):
            async def record_minutes(self, day, minutes):
                raise asyncio.CancelledError

        capture = CallCapture()
        realtime = FakeRealtimeServer(
            events=[audio_delta("were-closed"), response_done()], respond_after_appends=0,
        )
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(run_closed_call(
                FakeTransport(), realtime, CancelledDuringTheWrite(),
                correlation_id="closed-2", capture=capture,
            ))
        self.assertEqual(capture.end_reason, "closed")

    def test_a_capture_that_raises_cannot_skip_the_ledger_charge_on_the_closed_path_either(self):
        class BrokenCapture(CallCapture):
            def finish(self, *args):
                raise RuntimeError("boom")

        ledger = FakeCallRecordStore()
        realtime = FakeRealtimeServer(
            events=[audio_delta("were-closed"), response_done()], respond_after_appends=0,
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(run_closed_call(
                FakeTransport(), realtime, ledger, correlation_id="closed-3", capture=BrokenCapture(),
            ))
        self.assertTrue(ledger.minutes)


if __name__ == "__main__":
    unittest.main()
