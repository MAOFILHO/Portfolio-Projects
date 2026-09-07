"""One complete call, end to end, between two fakes -- no Azure, no credentials, no spend.

This is the test docs/PLAN.md's Phase 2 exit criterion is written against: "full app runs
end-to-end between two fakes in CI with zero Azure dependency". Nothing here patches a module
attribute; `run_call` is handed both collaborators, which is the whole point of issue #18.

Determinism note: the fake model holds its scripted events until the caller's audio has actually
been forwarded (`respond_after_appends`), so the two relay tasks can't race. That also mirrors the
real deployment, which answers after server-side turn detection fires -- not before.
"""
import asyncio
import json
import socket
import unittest
from unittest.mock import patch

from azbank_voice_agent import accounts
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.realtime.fake import (
    FakeRealtimeServer,
    audio_delta,
    error_event,
    function_call,
    response_done,
    transcript_delta,
)
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame, dtmf_frame, unknown_frame


def _balance_call():
    """Caller speaks, agent greets, attempts a balance check -- without ever handing off to
    banking (see WholeCallWithMidCallHandoff for that path). The gate is deny-all until Phase 4
    (2026-09-07 review of dispatch/gate.py), so the tool call is refused rather than answered --
    this scenario now exercises that refusal at the whole-call seam, not a successful lookup. The
    fake model can still script get_balance while nominally on triage, same as any other model
    attempt (dispatch/gate.py's own docstring: tool scoping is defence in depth, not the control,
    so an attempt outside an agent's declared tools reaches the gate exactly like any other)."""
    transport = FakeTransport(
        frames=[audio_frame("caller-said-1"), audio_frame("caller-said-2")],
        hang=True,  # the model's scripted events end this call, not the caller hanging up
    )
    realtime = FakeRealtimeServer(
        events=[
            audio_delta("agent-greeting"),
            transcript_delta("Hi, how can I help?"),
            function_call("get_balance", '{"account": "chequing"}'),
            audio_delta("agent-says-balance"),
            response_done(),
        ],
        respond_after_appends=2,
    )
    return transport, realtime


class WholeCallAgainstBothFakes(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def test_a_complete_call_runs_with_no_azure_and_no_patching(self):
        transport, realtime = _balance_call()

        asyncio.run(run_call(transport, realtime))

        # The model heard the caller.
        self.assertEqual(realtime.appended_audio, ["caller-said-1", "caller-said-2"])
        # The caller heard the agent -- both spoken chunks, in order.
        self.assertEqual(transport.sent_audio_payloads, ["agent-greeting", "agent-says-balance"])
        # The tool call reached the dispatcher and was refused by the real (deny-all) table --
        # no patching, this is what an anonymous caller actually gets in Phase 2.
        self.assertEqual(len(realtime.tool_outputs), 1)
        call_id, output = realtime.tool_outputs[0]
        self.assertEqual(call_id, "call-1")
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})
        # The whole exchange, in order: configure, hear, answer the tool, ask for a new response.
        self.assertEqual(realtime.sent_types, [
            "session.update",
            "input_audio_buffer.append",
            "input_audio_buffer.append",
            "conversation.item.create",
            "response.create",
        ])

    def test_the_session_opens_on_triage_with_only_the_handoff_tool(self):
        # Issue #20: tool scope is per-agent now, not one static list every call opens with. A
        # call starts on TRIAGE, which has no banking tools of its own -- only a way to hand off.
        transport, realtime = _balance_call()
        asyncio.run(run_call(transport, realtime))
        declared = [tool["name"] for tool in realtime.session_config["tools"]]
        self.assertEqual(declared, ["handoff_to_banking"])

    def test_tool_arguments_and_agent_speech_never_reach_a_log_line(self):
        # B2 (CLAUDE.md): dispatch/tools.py already promises never to log tool arguments --
        # Phase 4 puts PIN-adjacent data on this exact path. This proves the relay doesn't
        # undercut that a frame earlier, and that the agent's spoken transcript gets the same
        # treatment, before either code path exists for real (see also the DTMF test above).
        transport, realtime = _balance_call()

        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime))

        self.assertTrue(any("tool call: get_balance" in line for line in cm.output))
        self.assertFalse(any("chequing" in line for line in cm.output))
        self.assertFalse(any("Hi, how can I help" in line for line in cm.output))

    def test_an_error_event_is_logged_without_its_content(self):
        # B2 (CLAUDE.md): an AOAI error event can echo the offending request back in its message
        # (e.g. a validation error on bad tool arguments) -- exactly the content B2 forbids in any
        # log line. An earlier fix (b9140fb) closed the tool-call and transcript lines but missed
        # this one, since it logged the whole event object rather than a field (caught by
        # /code-review, 2026-09-07).
        transport = FakeTransport(frames=[audio_frame("real-audio")], hang=True)
        realtime = FakeRealtimeServer(
            events=[error_event("account 1234-5678-90 overdrawn"), response_done()],
            respond_after_appends=1,
        )

        with self.assertLogs("bridge", level="ERROR") as cm:
            asyncio.run(run_call(transport, realtime))

        self.assertTrue(any("error event" in line for line in cm.output))
        self.assertFalse(any("1234-5678-90" in line for line in cm.output))
        self.assertFalse(any("overdrawn" in line for line in cm.output))

    def test_a_whole_call_never_opens_a_network_connection(self):
        # The fakes are documented as never touching the network. This asserts it rather than
        # trusting the docstring: any outbound connect attempt during a full call fails the test.
        transport, realtime = _balance_call()
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network call")), \
             patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network call")):
            asyncio.run(run_call(transport, realtime))
        self.assertEqual(transport.sent_audio_payloads, ["agent-greeting", "agent-says-balance"])


class WholeCallHandlesNonAudioFrames(unittest.TestCase):
    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def test_dtmf_tone_never_reaches_the_model_and_never_reaches_a_log_line(self):
        # B2 (CLAUDE.md): the PIN never appears in any transcript, log line, or span attribute.
        # Asserted at the whole-call seam, not just at the frame parser.
        transport = FakeTransport(frames=[dtmf_frame("7"), audio_frame("real-audio")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)

        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime))

        self.assertEqual(realtime.appended_audio, ["real-audio"])  # the tone was not forwarded
        self.assertTrue(any("DTMF" in line for line in cm.output))  # arrival still logged
        self.assertFalse(any("7" in line for line in cm.output))  # but never the tone itself

    def test_an_unrecognised_frame_kind_is_ignored_not_crashed_on(self):
        transport = FakeTransport(frames=[unknown_frame(), audio_frame("real-audio")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)
        asyncio.run(run_call(transport, realtime))
        self.assertEqual(realtime.appended_audio, ["real-audio"])


class WholeCallWithTheGateClosed(unittest.TestCase):
    """B1 at the whole-call seam: a refused tool must not run, and the caller must be told rather
    than left in silence."""

    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def _transfer_call(self):
        transport = FakeTransport(frames=[audio_frame("move-my-money")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call(
                    "transfer",
                    '{"from_account": "chequing", "to_account": "savings", "amount": 100.0}',
                ),
                response_done(),
            ],
            respond_after_appends=1,
        )
        return transport, realtime

    def test_a_refused_transfer_moves_no_money_and_the_caller_is_told(self):
        transport, realtime = self._transfer_call()

        with patch.object(gate, "is_allowed", return_value=False):
            asyncio.run(run_call(transport, realtime))

        _, output = realtime.tool_outputs[0]
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})
        # The money did not move.
        self.assertEqual(accounts.ACCOUNTS["chequing"], 2400.0)
        self.assertEqual(accounts.ACCOUNTS["savings"], 500.0)
        # And the model was asked for a new response, so the refusal is spoken, not silent.
        self.assertIn("response.create", realtime.sent_types)

    def test_a_tool_the_real_table_does_not_permit_is_refused_without_patching_anything(self):
        # The gate as actually configured, not a forced-closed one: a tool nobody granted is
        # refused on a real call path.
        transport = FakeTransport(frames=[audio_frame("do-something-else")], hang=True)
        realtime = FakeRealtimeServer(
            events=[function_call("drain_account", "{}"), response_done()],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime))
        _, output = realtime.tool_outputs[0]
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})


class WholeCallWithMidCallHandoff(unittest.TestCase):
    """Issue #20's own acceptance criteria, at the whole-call seam: a caller who starts on triage
    and needs a specialist is handed over mid-call without repeating themselves, and without a
    second session ever being opened."""

    def setUp(self):
        accounts.ACCOUNTS.clear()
        accounts.ACCOUNTS.update({"chequing": 2400.0, "savings": 500.0})

    def _handoff_then_balance_call(self):
        transport = FakeTransport(frames=[audio_frame("i-need-my-balance")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_banking", "{}", call_id="call-handoff"),
                function_call("get_balance", '{"account": "chequing"}', call_id="call-balance"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        return transport, realtime

    def test_the_call_opens_on_triage_and_hands_off_to_banking_on_one_session(self):
        transport, realtime = self._handoff_then_balance_call()
        asyncio.run(run_call(transport, realtime))

        # Exactly one connection was ever used -- the same fake `realtime` received every
        # message, including both configurations. A second session would mean a second
        # RealtimeConnection, which nothing here ever constructs.
        configs = realtime.session_configs
        self.assertEqual(len(configs), 2)
        self.assertEqual([t["name"] for t in configs[0]["tools"]], ["handoff_to_banking"])
        self.assertEqual(
            sorted(t["name"] for t in configs[1]["tools"]),
            ["get_balance", "list_accounts", "transfer"],
        )
        self.assertNotEqual(configs[0]["instructions"], configs[1]["instructions"])

        # The handoff itself came back as a function_call_output, so the model can keep talking
        # rather than the call going silent while it's reconfigured.
        call_id, output = realtime.tool_outputs[0]
        self.assertEqual(call_id, "call-handoff")
        self.assertEqual(json.loads(output), {"result": "transferred to banking"})

    def test_the_tool_call_after_handoff_runs_as_the_banking_agent_not_triage(self):
        # Gate closed (the real Phase 2 config, not patched): both attempts are refused, but the
        # *log* records which agent each refusal was against -- proving the handoff actually
        # changed which identity dispatch_tool_call was given, not just which tools were declared
        # (dispatch/gate.py: tool scoping is defence in depth, not the control -- this is the
        # control's own record of which agent asked).
        transport, realtime = self._handoff_then_balance_call()
        with self.assertLogs("dispatch", level="WARNING") as cm:
            asyncio.run(run_call(transport, realtime))
        self.assertTrue(any("agent=banking" in line for line in cm.output))
        self.assertFalse(any("agent=triage" in line for line in cm.output))

    def test_a_handoff_never_reaches_the_dispatcher(self):
        # A handoff is routing, not a banking tool call, so it must never produce a "tool call:
        # ..." line -- that log line is dispatch_tool_call's own path, and a handoff has to
        # bypass it entirely (dispatch/gate.py's own docstring: tool scoping is defence in depth,
        # not the control -- a handoff isn't even attempting a controlled action).
        transport, realtime = self._handoff_then_balance_call()
        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime))
        self.assertTrue(any("handoff: triage -> banking" in line for line in cm.output))
        self.assertFalse(any("tool call: handoff_to_banking" in line for line in cm.output))

    def test_a_handoff_the_calling_agent_has_no_declared_edge_to_is_refused_not_routed(self):
        # BANKING.handoff_to is empty -- a handoff_to_triage call from BANKING must not silently
        # reconfigure the session (fixed 2026-09-07, /code-review of #20: both axes independently
        # found handoff_target() checked only "does the target agent exist", not "did the calling
        # agent declare this edge"). It falls through to the ordinary dispatch path instead, where
        # the gate refuses it exactly like any other unrecognised tool name -- there is no separate
        # path that lets an undeclared edge succeed.
        transport = FakeTransport(frames=[audio_frame("i-need-my-balance")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_banking", "{}", call_id="call-handoff-1"),
                function_call("handoff_to_triage", "{}", call_id="call-handoff-2"),
                response_done(),
            ],
            respond_after_appends=1,
        )

        with self.assertLogs("dispatch", level="WARNING") as cm:
            asyncio.run(run_call(transport, realtime))

        # Exactly one reconfiguration happened -- the rejected second attempt never sent a second
        # session.update (triage's opening config, then the one real handoff to banking).
        self.assertEqual(len(realtime.session_configs), 2)
        self.assertTrue(any("handoff_to_triage" in line for line in cm.output))

        # The refused attempt still gets a spoken answer, same as any other refusal -- B1's
        # "never silent" property applies here too, not just to real banking tools.
        call_id, output = realtime.tool_outputs[1]
        self.assertEqual(call_id, "call-handoff-2")
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})


if __name__ == "__main__":
    unittest.main()
