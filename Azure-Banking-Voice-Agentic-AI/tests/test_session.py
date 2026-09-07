"""Relay tests -- cost caps and the events the relay must survive.

Issue #18 replaced this file's hand-rolled doubles with the real fakes from
azbank_voice_agent.transport.fake / .realtime.fake, and retargeted every case at `run_call`'s
injected-collaborator signature. Intent unchanged from Phase 1: same caps, same assertions.

The whole-call path lives in test_whole_call.py; what stays here is the narrower behaviour that
is easiest to see on its own.
"""
import asyncio
import unittest
from unittest.mock import patch

from azbank_voice_agent.cost import caps
from azbank_voice_agent.realtime import session
from azbank_voice_agent.realtime.fake import FakeRealtimeServer, error_event, response_done
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport


class RunCallEnforcesB4Caps(unittest.TestCase):
    """B4 (CLAUDE.md): no call exceeds 20 turns / 5 minutes, fails closed. This is a Phase-1-sized
    guard only -- a bare per-call counter and wall-clock timeout, not the full cost-store/daily-cap
    system (docs/PLAN.md Phase 5, `T-B4-FAILCLOSED`)."""

    def test_turn_cap_ends_the_call_without_draining_every_queued_event(self):
        realtime = FakeRealtimeServer(events=[response_done() for _ in range(5)])
        with patch.object(caps, "MAX_CALL_TURNS", 2), \
             self.assertLogs(session.log, level="WARNING") as cm:
            asyncio.run(run_call(FakeTransport(), realtime))
        # Stopped at the cap (2), not after draining all 5 queued turns.
        self.assertEqual(realtime.consumed, 2)
        self.assertTrue(any("MAX_CALL_TURNS" in line for line in cm.output))

    def test_duration_cap_ends_a_call_that_never_hits_the_turn_cap(self):
        # Neither side ever ends this call: the caller says nothing and the model never speaks.
        # Only the wall-clock cap can end it.
        with patch.object(caps, "MAX_CALL_SECONDS", 0.05), \
             self.assertLogs(session.log, level="WARNING") as cm:
            asyncio.run(run_call(FakeTransport(hang=True), FakeRealtimeServer(hang=True)))
        self.assertTrue(any("MAX_CALL_SECONDS" in line for line in cm.output))

    def test_a_call_under_both_caps_ends_cleanly(self):
        realtime = FakeRealtimeServer(events=[response_done()])
        with self.assertLogs(session.log, level="INFO") as cm:
            asyncio.run(run_call(FakeTransport(), realtime))
        self.assertTrue(any("call ended" in line for line in cm.output))
        self.assertFalse(any("MAX_CALL" in line for line in cm.output))


class RunCallSurvivesModelErrors(unittest.TestCase):
    def test_an_error_event_is_logged_and_does_not_end_the_call(self):
        realtime = FakeRealtimeServer(events=[error_event("rate limited"), response_done()])
        with self.assertLogs(session.log, level="ERROR") as cm:
            asyncio.run(run_call(FakeTransport(), realtime))
        self.assertTrue(any("AOAI error event" in line for line in cm.output))
        self.assertEqual(realtime.consumed, 2)  # kept going past the error


class CallerHangupEndsTheCall(unittest.TestCase):
    def test_transport_disconnect_ends_the_call_without_raising(self):
        # FakeTransport with no frames and hang=False disconnects immediately, exactly as a real
        # ACS media socket does once the caller hangs up. That must end the call cleanly, not
        # surface as an error.
        realtime = FakeRealtimeServer(hang=True)
        with self.assertLogs(session.log, level="INFO") as cm:
            asyncio.run(run_call(FakeTransport(), realtime))
        self.assertTrue(any("call ended" in line for line in cm.output))


if __name__ == "__main__":
    unittest.main()
