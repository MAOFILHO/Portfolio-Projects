"""One complete call, end to end, between two fakes -- no Azure, no credentials, no spend.

This is the test docs/PLAN.md's Phase 2 exit criterion is written against: "full app runs
end-to-end between two fakes in CI with zero Azure dependency". Nothing here patches a module
attribute; `run_call` is handed all three collaborators, which is the whole point of issue #18 (and of
issue #28, which added the third).

Determinism note: the fake model holds its scripted events until the caller's audio has actually
been forwarded (`respond_after_appends`), so the two relay tasks can't race. That also mirrors the
real deployment, which answers after server-side turn detection fires -- not before.
"""
import asyncio
import datetime
import inspect
import json
import socket
import time
import unittest
from unittest.mock import patch

from azbank_voice_agent import auth as auth_module
from azbank_voice_agent.agents import specs
from azbank_voice_agent.auth import AttemptsExhausted, outcomes, sentence_for
from azbank_voice_agent.call_records import REASONS
from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.call_records.fake import unavailable as store_unavailable
from azbank_voice_agent.call_records.store import day_key
from azbank_voice_agent.core_banking import CoreBankingUnavailable
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient
from azbank_voice_agent.cost import caps
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.dispatch import tools as tools_module
from azbank_voice_agent.realtime import session as session_module
from azbank_voice_agent.realtime.fake import (
    FakeRealtimeServer,
    audio_delta,
    error_event,
    function_call,
    response_done,
    speech_stopped,
    transcript_delta,
)
from azbank_voice_agent.realtime.session import budget_or_closed, run_call, run_closed_call
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
        # The third injected collaborator (issue #28). Same shape as the other two fakes: a real
        # module, never a network call, handed to run_call rather than patched in.
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def test_a_complete_call_runs_with_no_azure_and_no_patching(self):
        transport, realtime = _balance_call()

        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

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
        # The whole exchange, in order. The second frame is the greeting request added by issue
        # #51 -- the agent is asked to speak before the caller does, rather than waiting for
        # server-side turn detection to fire.
        self.assertEqual(realtime.sent_types, [
            "session.update",
            "response.create",
            "input_audio_buffer.append",
            "input_audio_buffer.append",
            "conversation.item.create",
            "response.create",
        ])

    def test_the_session_opens_on_triage_with_only_the_handoff_tool(self):
        # Issue #20: tool scope is per-agent now, not one static list every call opens with. A
        # call starts on TRIAGE, which has no banking tools of its own -- only a way to hand off.
        transport, realtime = _balance_call()
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        declared = sorted(tool["name"] for tool in realtime.session_config["tools"])
        self.assertEqual(
            declared, ["escalate_to_human", "handoff_to_banking", "handoff_to_cards"]
        )

    def test_tool_arguments_and_agent_speech_never_reach_a_log_line(self):
        # B2 (CLAUDE.md): dispatch/tools.py already promises never to log tool arguments --
        # Phase 4 puts PIN-adjacent data on this exact path. This proves the relay doesn't
        # undercut that a frame earlier, and that the agent's spoken transcript gets the same
        # treatment, before either code path exists for real (see also the DTMF test above).
        transport, realtime = _balance_call()

        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

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
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        self.assertTrue(any("error event" in line for line in cm.output))
        self.assertFalse(any("1234-5678-90" in line for line in cm.output))
        self.assertFalse(any("overdrawn" in line for line in cm.output))

    def test_a_whole_call_never_opens_a_network_connection(self):
        # The fakes are documented as never touching the network. This asserts it rather than
        # trusting the docstring: any outbound connect attempt during a full call fails the test.
        transport, realtime = _balance_call()
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network call")), \
             patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network call")):
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(transport.sent_audio_payloads, ["agent-greeting", "agent-says-balance"])


class WholeCallHandlesNonAudioFrames(unittest.TestCase):
    def setUp(self):
        # The third injected collaborator (issue #28). Same shape as the other two fakes: a real
        # module, never a network call, handed to run_call rather than patched in.
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def test_dtmf_tone_never_reaches_the_model_and_never_reaches_a_log_line(self):
        # B2 (CLAUDE.md): the PIN never appears in any transcript, log line, or span attribute.
        # Asserted at the whole-call seam, not just at the frame parser. Since issue #37 the
        # classifier does return the digit -- so this test now proves the thing that actually
        # matters, which is that the relay hands it on without ever writing it down.
        transport = FakeTransport(frames=[dtmf_frame("7"), audio_frame("real-audio")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)

        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        self.assertEqual(realtime.appended_audio, ["real-audio"])  # the tone was not forwarded
        self.assertTrue(any("DTMF" in line for line in cm.output))  # arrival still logged
        self.assertFalse(any("7" in line for line in cm.output))  # but never the tone itself

    def test_a_malformed_dtmf_frame_does_not_end_the_call(self):
        # A DTMF frame with no tone in it is ignored like any other unrecognised key. Anything
        # that raised on the inbound task would take the call down with it.
        transport = FakeTransport(
            frames=[json.dumps({"kind": "DtmfData"}), audio_frame("real-audio")], hang=True
        )
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(realtime.appended_audio, ["real-audio"])

    def test_an_unrecognised_frame_kind_is_ignored_not_crashed_on(self):
        transport = FakeTransport(frames=[unknown_frame(), audio_frame("real-audio")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(realtime.appended_audio, ["real-audio"])


def _keyed(pin):
    """One DTMF frame per digit, the way a caller keying a PIN actually arrives."""
    return [dtmf_frame(digit) for digit in pin]


class WholeCallWithAKeyedPin(unittest.TestCase):
    """The keyed tone reaching the authenticator, at the only seam where it is a real call.

    The authenticator's own rules are proved directly in tests/test_authenticator.py. What is
    proved here is the second claim of the same pair the gate's tests already use: that the machine
    is genuinely in the path. A control that decides perfectly and is never consulted protects
    nothing, and that failure would pass every test of the first kind.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _call(self, frames, events=(), hang=True):
        transport = FakeTransport(frames=list(frames), hang=hang)
        realtime = FakeRealtimeServer(events=list(events), respond_after_appends=0)
        return transport, realtime

    def _injected_notes(self, realtime):
        """The text of every conversation item the relay injected that is not a tool result."""
        return [
            part["text"]
            for message in realtime.sent
            if message["type"] == "conversation.item.create"
            and message["item"].get("type") == "message"
            for part in message["item"]["content"]
        ]

    def test_a_keyed_pin_authenticates_the_call_and_tells_the_caller(self):
        transport, realtime = self._call(_keyed(DEFAULT_PIN))
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        self.assertEqual(self.core_banking.calls, ["verify_pin"])
        self.assertEqual(self._injected_notes(realtime), [sentence_for(outcomes.AUTHENTICATED)])
        # Told rather than left in silence: the item is followed by a response request, the same
        # two messages a handoff already sends.
        self.assertEqual(realtime.sent_types[-2:], ["conversation.item.create", "response.create"])

    def test_nothing_is_submitted_or_said_before_the_fourth_digit(self):
        transport, realtime = self._call(_keyed(DEFAULT_PIN[:3]))
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(self.core_banking.calls, [])
        self.assertEqual(self._injected_notes(realtime), [])

    def test_a_mis_key_cleared_then_a_correct_entry_authenticates_and_costs_nothing(self):
        frames = [*_keyed("999"), dtmf_frame("*"), *_keyed(DEFAULT_PIN)]
        transport, realtime = self._call(frames)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        # One check, not two: the cleared entry never completed, so it never reached the service.
        self.assertEqual(self.core_banking.calls, ["verify_pin"])
        self.assertEqual(self._injected_notes(realtime), [sentence_for(outcomes.AUTHENTICATED)])

    def test_three_rejections_end_the_call_after_the_caller_is_told(self):
        frames = _keyed("9999") + _keyed("8888") + _keyed("7777") + [audio_frame("still-here")]
        transport, realtime = self._call(frames)

        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        self.assertEqual(self.core_banking.calls, ["verify_pin"] * 3)
        self.assertEqual(self._injected_notes(realtime), [
            sentence_for(outcomes.REJECTED),
            sentence_for(outcomes.REJECTED),
            sentence_for(outcomes.EXHAUSTED),
        ])
        # The call ended: the audio frame queued behind the third rejection was never forwarded.
        self.assertEqual(realtime.appended_audio, [])
        self.assertTrue(any("attempts exhausted" in line.lower() for line in cm.output))
        self.assertTrue(any("call ended" in line for line in cm.output))

    def test_ending_on_exhausted_attempts_is_not_reported_as_a_relay_failure(self):
        # It travels the relay's "expected, not a relay failure" branch, the same one a cost cap
        # uses -- so run_call returns rather than raising.
        transport, realtime = self._call(_keyed("9999") + _keyed("8888") + _keyed("7777"))
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

    def test_exhaustion_uses_its_own_exception_type_and_not_the_cost_caps(self):
        """A security event and a cost event must stay distinguishable (issue #37).

        Asserted at the type rather than at the behaviour, because the behaviour is identical by
        design: both end the call quietly. Reusing CallLimitExceeded would mean B4, and every log
        and dashboard that ever reads these would conflate the two.
        """
        self.assertFalse(issubclass(AttemptsExhausted, caps.CallLimitExceeded))
        self.assertFalse(issubclass(caps.CallLimitExceeded, AttemptsExhausted))

    def test_an_unavailable_service_fails_closed_and_spends_no_attempt(self):
        self.core_banking.fail_with = CoreBankingUnavailable("down")
        frames = _keyed(DEFAULT_PIN) * 4
        transport, realtime = self._call(frames)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        notes = self._injected_notes(realtime)
        self.assertEqual(notes, [sentence_for(outcomes.UNAVAILABLE)] * 4)
        # Four submissions, none of them an attempt -- the call is still going, which it would not
        # be if an outage had spent the caller's three tries.
        self.assertEqual(self.core_banking.calls, ["verify_pin"] * 4)

    def test_the_caller_can_key_the_pin_after_a_handoff(self):
        """The moment a caller may authenticate is not dictated by routing they cannot see.

        The machine is agent-independent by construction; this is the proof that the relay does
        not reintroduce the dependency by only feeding it while on triage.
        """
        transport = FakeTransport(
            frames=[audio_frame("i-need-my-balance"), *_keyed(DEFAULT_PIN)], hang=True
        )
        realtime = FakeRealtimeServer(
            events=[function_call(specs.handoff_tool_name(gate.BANKING_AGENT), "{}")],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        self.assertEqual(len(realtime.session_configs), 2)  # the handoff happened
        self.assertEqual(self.core_banking.calls, ["verify_pin"])

    def test_no_digit_reaches_the_model_a_log_line_or_an_injected_item(self):
        """B2 across every surface one keyed call touches.

        The injected item is the new one and the one that matters: it is the first thing this
        project has ever put into the model's context on the caller's behalf, and it states the
        outcome only -- never a digit, never an attempt count.
        """
        frames = _keyed("9999") + _keyed("*123") + _keyed(DEFAULT_PIN)
        transport, realtime = self._call(frames)

        with self.assertLogs(level="DEBUG") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        everything = "\n".join(cm.output) + json.dumps(realtime.sent) + json.dumps(transport.sent)
        for secret in (DEFAULT_PIN, "9999", "123"):
            with self.subTest(secret_length=len(secret)):
                self.assertNotIn(secret, everything)

    def test_the_relay_logs_no_decimal_digit_at_all_while_a_pin_is_being_keyed(self):
        """The digit-by-digit leak, which a whole-PIN substring scan cannot see.

        `tests/test_zz_b2_leak_scan.py` scans every record in the run for the submitted values, and
        that is the right shape for a value logged whole. It cannot catch a relay that logged each
        tone as it arrived: four records reading "1", "2", "3", "4" contain the PIN between them
        and contain no substring of it in any one of them.

        The bridge logger's whole vocabulary on this path is fixed prose and outcome tokens -- it
        has no legitimate reason to emit a digit while a caller is keying -- so the precise
        assertion is available here and is stronger than any substring rule could be.
        """
        frames = [*_keyed("9999"), dtmf_frame("*"), *_keyed("8888"), *_keyed(DEFAULT_PIN)]
        transport, realtime = self._call(frames)

        with self.assertLogs("bridge", level="DEBUG") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        for record in cm.records:
            with self.subTest(message=record.msg):
                rendered = record.getMessage()
                self.assertFalse(
                    any(character.isdigit() for character in rendered),
                    f"the relay emitted a digit while a PIN was being keyed: {rendered!r}",
                )

    def test_no_new_tool_is_declared_anywhere(self):
        """There is no authentication tool, which is why nothing is reachable while anonymous.

        Dropping the spoken factor removed the one tool that would have had to be callable before
        authentication (docs/phase4/exit-criteria.md).
        """
        declared = {tool["name"] for identity in specs.AGENTS for tool in specs.tools_for(identity)}
        for name in declared:
            with self.subTest(tool=name):
                self.assertNotIn("auth", name)
                self.assertNotIn("pin", name)
                self.assertNotIn("verify", name)

    def test_one_realtime_session_per_call_is_unchanged_by_a_pin_entry(self):
        transport, realtime = self._call(_keyed(DEFAULT_PIN))
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(len(realtime.session_configs), 1)


class _FixedUuid:
    """A `uuid4()` whose `.hex` is known, so an error can be scripted to name the id it produces."""

    def __init__(self, hex_value):
        self.hex = hex_value


def _repeatable_uuids():
    """A `uuid4` stand-in giving known, **distinct** values, restarting on each call to this.

    Distinct matters: the injection is two frames and each gets its own id, so a stand-in returning
    one value for every call would collapse them and hide whichever half a test meant to name.
    Restarting matters too: a correlation test runs the same call twice, once to learn the ids and
    once to have them rejected, and the two runs have to stamp the same ids.
    """
    values = iter([_FixedUuid(letter * 32) for letter in "abcdefghijkl"])
    return lambda: next(values)


class TheInjectedItemIsAddressable(unittest.TestCase):
    """The injected PIN-outcome item carries a client `event_id`, and a rejection is correlated.

    **Why** (`docs/phase4/research-carried-findings.md` §1d, researched 2026-09-10 against the
    generated OpenAI realtime types). `conversation.item.create` is answered with either a
    `conversation.item.created` or an `error`, and the error carries `error.event_id`: "The event_id
    of the client event that caused the error, if applicable." That field is the **only** documented
    way to attribute a rejection to a particular frame this relay sent. Without a client-generated
    id on the way out, the relay can observe that an error arrived and nothing more.

    This is what makes Phase 5's first real call diagnostic rather than pass-or-fail. The item's
    shape is confirmed correct against the specification, but no source documents whether Azure's
    endpoint and this model version accept it, so the call is a probe -- and a probe that cannot
    tell "my injection was rejected" from "something else went wrong" is not much of one.

    **What is deliberately still not logged**: the error's message, type and code. That decision
    stands unchanged from Phase 2 -- a validation error can echo the offending request back, which
    is exactly the content B2 forbids. Correlating on an opaque id this relay generated itself
    reveals nothing about the caller.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _injected_items(self, realtime):
        return [
            message for message in realtime.sent
            if message["type"] == "conversation.item.create"
            and message["item"].get("type") == "message"
        ]

    def _run(self, frames, events=()):
        transport = FakeTransport(frames=list(frames), hang=True)
        realtime = FakeRealtimeServer(events=list(events), respond_after_appends=0)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        return realtime

    def test_the_injected_item_carries_a_client_event_id(self):
        realtime = self._run(_keyed(DEFAULT_PIN))
        items = self._injected_items(realtime)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].get("event_id"), "the injected item is unaddressable")

    def test_two_injections_on_one_call_do_not_share_an_id(self):
        # An id reused across injections would correlate a rejection to the wrong one, which is
        # worse than not correlating at all.
        realtime = self._run(_keyed("9999") + _keyed("8888"))
        identifiers = [item["event_id"] for item in self._injected_items(realtime)]
        self.assertEqual(len(identifiers), 2)
        self.assertEqual(len(set(identifiers)), 2)

    def test_the_id_does_not_carry_what_was_keyed(self):
        """B2. The id is generated, never derived from anything the caller did."""
        realtime = self._run(_keyed(DEFAULT_PIN))
        identifier = self._injected_items(realtime)[0]["event_id"]
        self.assertNotIn(DEFAULT_PIN, identifier)

    def test_the_id_contains_no_decimal_digit_at_all(self):
        """The property that keeps B2's run-wide scan deterministic.

        A raw uuid hex is drawn from an alphabet that is more than half digits, so over a run it
        eventually spells some four-digit run by chance -- and the scan looks for exactly that,
        across everything every call sent. The first version of this id did precisely that and
        turned the red-team corpus's B2 assertion red on a coincidence. A constraint that fails at
        random is worse than a weaker one stated honestly, so the id is built to be *unable* to
        spell a credential rather than merely unlikely to.

        **Asserted structurally, not by sampling.** Two earlier versions of this both sampled: two
        hundred whole calls, then two thousand generated ids. Sampling cannot establish this. The
        property holds because the map covers every digit the uuid alphabet can produce, so that is
        what gets asserted -- one line, complete, and it would still catch a map that forgot `9`
        while a random sample might not (/code-review, 2026-09-10).
        """
        # Every character a hex uuid can contain, put through the map at once.
        self.assertFalse(
            any(c.isdigit() for c in "0123456789abcdef".translate(session_module._DIGIT_FREE)),
            "the map lets a digit through",
        )
        # And the assembled id, prefix included, for the same reason at the other end.
        self.assertFalse(any(c.isdigit() for c in session_module._new_event_id()))

    def test_the_id_map_is_injective_so_ids_stay_as_unique_as_the_uuid(self):
        """The other half of the claim, and the half the digit rule does not reach.

        Digits are rewritten to letters. If that map ever collided -- two digits to one letter, or a
        digit onto a letter the hex alphabet already uses -- two different uuids could produce one
        id, and a rejection would be correlated to the wrong frame.

        **Injective and disjoint from hex is what is asserted, which is what the uniqueness argument
        needs.** An earlier name for this test said "bijective", which is a different and stronger
        claim about a map this one never makes (/code-review, 2026-09-10).
        """
        replacements = [chr(value) for value in session_module._DIGIT_FREE.values()]
        self.assertEqual(len(replacements), len(set(replacements)), "two digits share a letter")
        self.assertFalse(
            set(replacements) & set("0123456789abcdef"),
            "a digit maps onto a character the hex alphabet already uses",
        )

    def test_a_rejection_naming_the_injection_is_reported_as_that_injection_failing(self):
        """The whole point: Phase 5 learns that *this* shape was refused, not that *an* error came.

        The relay's id is random per call, so the error cannot be scripted to name it without
        pinning it first. That is what the patch below is for, and it is the only thing it does.
        """
        # One run to learn the id the relay stamps, one to reject it. Each gets its own fresh
        # sequence, so both stamp the same ids, and neither assumes how an id is built.
        with patch.object(session_module.uuid, "uuid4", side_effect=_repeatable_uuids()):
            stamped = self._injected_items(self._run(_keyed(DEFAULT_PIN)))[0]["event_id"]

        self.core_banking = FakeCoreBankingClient()
        with patch.object(session_module.uuid, "uuid4", side_effect=_repeatable_uuids()):
            with self.assertLogs("bridge", level="ERROR") as cm:
                self._run(
                    [*_keyed(DEFAULT_PIN), audio_frame("still-here")],
                    events=[error_event("bad item", caused_by=stamped), response_done()],
                )

        self.assertTrue(
            any("injected" in line.lower() for line in cm.output),
            f"a rejection of the relay's own item was not identified as one: {cm.output}",
        )

    def test_the_response_request_is_stamped_too_not_only_the_item(self):
        """The mechanism is two frames, so attribution has to cover both.

        A rejection of the response request is as much a failure of this injection as a rejection
        of the item, and correlating only the item would report it as an unrelated error
        (/code-review, 2026-09-10).
        """
        realtime = self._run(_keyed(DEFAULT_PIN))
        # **Stamped** response requests only. Since issue #51 the relay also sends an unstamped
        # `response.create` to open the call with a greeting, and that frame is not part of this
        # mechanism -- it is an ordinary request like the one a handoff sends. Filtering on the
        # stamp is what keeps this test about attribution rather than about frame counting.
        requests = [
            m for m in realtime.sent if m["type"] == "response.create" and m.get("event_id")
        ]
        self.assertEqual(len(requests), 1)
        self.assertTrue(requests[0].get("event_id"), "the response request is unaddressable")
        # And it is a different frame from the item, so a rejection says which half failed.
        self.assertNotEqual(
            requests[0]["event_id"], self._injected_items(realtime)[0]["event_id"]
        )

    def test_a_rejection_of_the_response_request_is_attributed_to_the_injection(self):
        with patch.object(session_module.uuid, "uuid4", side_effect=_repeatable_uuids()):
            realtime = self._run(_keyed(DEFAULT_PIN))
            stamped = next(
                m for m in realtime.sent
                if m["type"] == "response.create" and m.get("event_id")
            )["event_id"]

        self.core_banking = FakeCoreBankingClient()
        with patch.object(session_module.uuid, "uuid4", side_effect=_repeatable_uuids()):
            with self.assertLogs("bridge", level="ERROR") as cm:
                self._run(
                    [*_keyed(DEFAULT_PIN), audio_frame("still-here")],
                    events=[error_event("malformed item", caused_by=stamped), response_done()],
                )

        self.assertTrue(
            any("injected" in line.lower() for line in cm.output),
            f"a rejected response request was not tied to the injection: {cm.output}",
        )

    def test_an_unrelated_error_is_not_attributed_to_the_injection(self):
        # A relay that called every error a rejected injection would be as uninformative as one
        # that called none of them that, and would send Phase 5 chasing the wrong thing.
        with self.assertLogs("bridge", level="ERROR") as cm:
            self._run(
                [*_keyed(DEFAULT_PIN), audio_frame("still-here")],
                events=[error_event("rate limited"), response_done()],
            )
        self.assertFalse(
            any("injected" in line.lower() for line in cm.output),
            f"an unrelated error was blamed on the injected item: {cm.output}",
        )

    def test_an_error_arriving_with_no_causing_id_does_not_raise(self):
        # `error.event_id` is optional in the spec, so its absence is ordinary, not exceptional.
        with self.assertLogs("bridge", level="ERROR"):
            self._run(
                [audio_frame("hello")],
                events=[error_event("server error", caused_by=None), response_done()],
            )


class WholeCallTheGateOpens(unittest.TestCase):
    """The payoff, at the whole-call seam: key the PIN, then hear a balance (issue #38).

    Nothing is patched. The gate as actually configured, the authenticator as actually wired, and
    the real permission table -- which is the only arrangement in which "the caller authenticates
    and then hears a balance" says anything true.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _authenticate_then_ask_for_a_balance(self, pin):
        transport = FakeTransport(
            frames=[audio_frame("balance-please"), *_keyed(pin)], hang=True
        )
        realtime = FakeRealtimeServer(
            events=[
                function_call(specs.handoff_tool_name(gate.BANKING_AGENT), "{}"),
                function_call("get_balance", '{"account": "chequing"}', call_id="call-2"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        return transport, realtime

    def test_the_caller_authenticates_and_then_hears_a_balance(self):
        transport, realtime = self._authenticate_then_ask_for_a_balance(DEFAULT_PIN)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        call_id, output = realtime.tool_outputs[-1]
        self.assertEqual(call_id, "call-2")
        # The figure came from the system of record, not from anywhere in the voice agent.
        self.assertEqual(
            json.loads(output), {"result": self.core_banking.accounts["chequing"]}
        )
        self.assertEqual(self.core_banking.calls, ["verify_pin", "get_balance"])

    def test_the_same_call_without_the_pin_is_refused_the_same_balance(self):
        # The control, held against the same script with the wrong PIN. Everything else about the
        # call is identical, so the refusal can only be the auth state.
        transport, realtime = self._authenticate_then_ask_for_a_balance("9999")
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        _, output = realtime.tool_outputs[-1]
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})
        self.assertEqual(self.core_banking.calls, ["verify_pin"])

    def test_an_anonymous_caller_routed_to_banking_is_refused_everything_there(self):
        # Handoff stays ungated, so this routing succeeds -- and buys the caller nothing. Routing
        # is never authorization.
        transport = FakeTransport(frames=[audio_frame("balance-please")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call(specs.handoff_tool_name(gate.BANKING_AGENT), "{}"),
                function_call("get_balance", '{"account": "chequing"}', call_id="call-2"),
                function_call("list_accounts", "{}", call_id="call-3"),
                function_call(
                    "transfer",
                    '{"from_account": "chequing", "to_account": "savings", "amount": 1.0}',
                    call_id="call-4",
                ),
                response_done(),
            ],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        self.assertEqual(len(realtime.session_configs), 2)  # the handoff really happened
        for call_id, output in realtime.tool_outputs[1:]:
            with self.subTest(call_id=call_id):
                self.assertEqual(json.loads(output), {"error": gate.REFUSAL})
        # And the sharpened B1, at the seam that matters: nothing banking reached the client.
        self.assertEqual(self.core_banking.calls, [])

    def test_the_refusal_still_explains_nothing(self):
        transport = FakeTransport(frames=[audio_frame("balance-please")], hang=True)
        realtime = FakeRealtimeServer(
            events=[function_call("get_balance", '{"account": "chequing"}'), response_done()],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        _, output = realtime.tool_outputs[0]
        spoken = json.loads(output)["error"].lower()
        for leak in ("authenticated", "anonymous", "pin", "permission", "banking agent"):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, spoken)


class TriageAsksForTheKeyedPin(unittest.TestCase):
    """Issue #37's trap 1: prose the model acts on must not describe a system that no longer exists.

    Asserted rather than eyeballed, because this is the instruction set that decides whether a
    caller is ever asked to authenticate at all -- and it changed in the same diff as the
    transition, deliberately.
    """

    def test_triage_asks_the_caller_to_key_the_pin(self):
        instructions = specs.TRIAGE.instructions.lower()
        self.assertIn("pin", instructions)
        self.assertIn("keypad", instructions)

    def test_triage_is_told_never_to_ask_for_it_aloud_or_repeat_a_digit_back(self):
        instructions = specs.TRIAGE.instructions.lower()
        self.assertIn("never ask them to say the pin out loud", instructions)
        self.assertIn("never read any digit back", instructions)

    def test_triage_is_told_not_to_count_attempts_out_loud(self):
        # The same probing-oracle reasoning the gate's refusal and the auth sentences already use.
        self.assertIn("how many tries are left", specs.TRIAGE.instructions.lower())

    def test_banking_instructions_are_untouched_by_this_phase(self):
        # It already refuses to state a figure without calling a tool, which is what it now
        # actually gets to do (issue #38).
        self.assertNotIn("pin", specs.BANKING.instructions.lower())


class RoutingIsInvisibleButMoneyTransfersAreNot(unittest.TestCase):
    """/code-review, 2026-09-12: the routing-narration fix banned the word 'transfer' on all three
    agents, including banking -- whose own `transfer` tool moves money and whose result text says
    "transferred $X" (dispatch/tools.py). That would have banking refuse to ever confirm a
    transfer it had just completed. Pinned here so it can't regress silently a second time."""

    def test_banking_is_not_told_to_avoid_the_word_transfer(self):
        instructions = specs.BANKING.instructions.lower()
        self.assertNotIn("never say the words 'transfer'", instructions)

    def test_triage_and_cards_are_still_told_to_avoid_the_word_transfer(self):
        # Unlike banking, these two never move money -- "transfer" on their lines only ever means
        # routing the call, which the caller must never hear about.
        for spec in (specs.TRIAGE, specs.CARDS):
            with self.subTest(agent=spec.identity):
                self.assertIn("'transfer' or 'transferring'", spec.instructions.lower())


class WholeCallWithTheGateClosed(unittest.TestCase):
    """B1 at the whole-call seam: a refused tool must not run, and the caller must be told rather
    than left in silence."""

    def setUp(self):
        # The third injected collaborator (issue #28). Same shape as the other two fakes: a real
        # module, never a network call, handed to run_call rather than patched in.
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

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
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        _, output = realtime.tool_outputs[0]
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})
        # The money did not move.
        self.assertEqual(self.core_banking.accounts["chequing"], 2400.0)
        self.assertEqual(self.core_banking.accounts["savings"], 500.0)
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
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        _, output = realtime.tool_outputs[0]
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})


class WholeCallWithMidCallHandoff(unittest.TestCase):
    """Issue #20's own acceptance criteria, at the whole-call seam: a caller who starts on triage
    and needs a specialist is handed over mid-call without repeating themselves, and without a
    second session ever being opened."""

    def setUp(self):
        # The third injected collaborator (issue #28). Same shape as the other two fakes: a real
        # module, never a network call, handed to run_call rather than patched in.
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

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
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        # Exactly one connection was ever used -- the same fake `realtime` received every
        # message, including both configurations. A second session would mean a second
        # RealtimeConnection, which nothing here ever constructs.
        configs = realtime.session_configs
        self.assertEqual(len(configs), 2)
        self.assertEqual(
            sorted(t["name"] for t in configs[0]["tools"]),
            ["escalate_to_human", "handoff_to_banking", "handoff_to_cards"],
        )
        self.assertEqual(
            sorted(t["name"] for t in configs[1]["tools"]),
            ["escalate_to_human", "get_balance", "list_accounts", "list_transactions", "transfer"],
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
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertTrue(any("agent=banking" in line for line in cm.output))
        self.assertFalse(any("agent=triage" in line for line in cm.output))

    def test_a_handoff_never_reaches_the_dispatcher(self):
        # A handoff is routing, not a banking tool call, so it must never produce a "tool call:
        # ..." line -- that log line is dispatch_tool_call's own path, and a handoff has to
        # bypass it entirely (dispatch/gate.py's own docstring: tool scoping is defence in depth,
        # not the control -- a handoff isn't even attempting a controlled action).
        transport, realtime = self._handoff_then_balance_call()
        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
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
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        # Exactly one reconfiguration happened -- the rejected second attempt never sent a second
        # session.update (triage's opening config, then the one real handoff to banking).
        self.assertEqual(len(realtime.session_configs), 2)
        self.assertTrue(any("handoff_to_triage" in line for line in cm.output))

        # The refused attempt still gets a spoken answer, same as any other refusal -- B1's
        # "never silent" property applies here too, not just to real banking tools.
        call_id, output = realtime.tool_outputs[1]
        self.assertEqual(call_id, "call-handoff-2")
        self.assertEqual(json.loads(output), {"error": gate.REFUSAL})


class WholeCallLogsB5LatencyAnchors(unittest.TestCase):
    """B5 (CLAUDE.md's constraints table) needs a real round-trip to measure -- Call 1's real
    logs (2026-09-08) had tool-call and handoff events but no timestamp pair to compute turn
    latency from at all. Arrival only (B2): these lines carry no audio, no transcript, nothing
    but that the event happened."""

    def setUp(self):
        # The third injected collaborator (issue #28). Same shape as the other two fakes: a real
        # module, never a network call, handed to run_call rather than patched in.
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def test_a_plain_turn_logs_caller_ended_then_agent_started(self):
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[speech_stopped(), audio_delta("hi there"), response_done()],
            respond_after_appends=1,
        )
        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        ended_idx = next(i for i, line in enumerate(cm.output) if "caller turn ended" in line)
        started_idx = next(i for i, line in enumerate(cm.output) if "agent audio started" in line)
        self.assertLess(ended_idx, started_idx)

    def test_only_the_first_audio_delta_of_a_response_is_logged(self):
        # Real audio deltas arrive many per response (Call 1's real logs: 8-30+ per turn) -- one
        # log line per response, not per chunk, or B5 latency data would be swamped by noise.
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                speech_stopped(),
                audio_delta("a"), audio_delta("b"), audio_delta("c"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(sum(1 for line in cm.output if "agent audio started" in line), 1)

    def test_a_tool_round_trip_still_pairs_with_the_original_caller_turn(self):
        # The function-call-only response has no audio -- response.done still resets the flag,
        # but no new "caller turn ended" happens in between, so the eventual audio after the
        # tool round-trip still measures against the real turn boundary, not a false-short one
        # starting from the tool response's own (nonexistent) speech_stopped.
        transport = FakeTransport(frames=[audio_frame("balance-please")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                speech_stopped(),
                function_call("get_balance", '{"account": "chequing"}'),
                response_done(),
                audio_delta("refusal"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        with self.assertLogs("bridge", level="INFO") as cm:
            asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(sum(1 for line in cm.output if "caller turn ended" in line), 1)
        self.assertEqual(sum(1 for line in cm.output if "agent audio started" in line), 1)


if __name__ == "__main__":
    unittest.main()


class WholeCallListingTransactions(unittest.TestCase):
    """A caller who authenticates and asks what happened on an account (issue #46).

    The point of testing this here rather than only at the dispatcher is the second claim of the
    pair the gate's tests use: the tool is genuinely reachable on a real call path, and the history
    the caller hears came from the system of record rather than from anything the model remembered.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _call(self, arguments='{"account": "chequing"}'):
        transport = FakeTransport(
            frames=[*_keyed(DEFAULT_PIN), audio_frame("what-happened-on-chequing")], hang=True
        )
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_banking", "{}", call_id="call-handoff"),
                function_call("list_transactions", arguments, call_id="call-history"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        return transport, realtime

    def _result(self, realtime, call_id="call-history"):
        return json.loads(dict(realtime.tool_outputs)[call_id])

    def test_an_authenticated_caller_hears_their_history(self):
        transport, realtime = self._call()
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

        result = self._result(realtime)["result"]
        self.assertTrue(result)
        # Newest first, and the figures are the ones the system of record holds.
        self.assertEqual(result[0]["occurred_at"], "2026-09-05")
        self.assertEqual(result[0]["amount"], -40.00)
        self.assertEqual(result[0]["counterparty"], "savings")
        self.assertIn("list_transactions", self.core_banking.calls)

    def test_the_history_came_from_the_system_of_record(self):
        # The claim that matters: what the caller is read is what the client returned, not a
        # payload assembled anywhere in the relay. Proved by changing what the system of record
        # holds and watching the answer change with it.
        transport, realtime = self._call()
        self.core_banking.transactions["chequing"] = []
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(self._result(realtime)["result"], [])

    def test_an_empty_history_is_a_result_not_an_error(self):
        # A caller who has never used an account must not be told something went wrong.
        transport, realtime = self._call()
        self.core_banking.transactions["chequing"] = []
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertNotIn("error", self._result(realtime))

    def test_an_unknown_account_is_the_sentence_get_balance_already_produces(self):
        transport, realtime = self._call(arguments='{"account": "bitcoin"}')
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(
            self._result(realtime), {"error": "There's no bitcoin account on this profile."}
        )

    def test_an_anonymous_caller_is_refused_and_the_service_is_never_asked(self):
        # No PIN keyed at all: the call stays anonymous, and the refusal must happen before the
        # client is reached rather than after it answers.
        transport = FakeTransport(frames=[audio_frame("what-happened")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_banking", "{}", call_id="call-handoff"),
                function_call(
                    "list_transactions", '{"account": "chequing"}', call_id="call-history"
                ),
                response_done(),
            ],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(self._result(realtime), {"error": gate.REFUSAL})
        self.assertNotIn("list_transactions", self.core_banking.calls)

    def test_a_malformed_account_argument_never_reaches_the_service(self):
        transport, realtime = self._call(arguments='{"account": {"$ne": null}}')
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(self._result(realtime), {"error": tools_module.MALFORMED})
        self.assertNotIn("list_transactions", self.core_banking.calls)


class WholeCallBlockingACard(unittest.TestCase):
    """The Cards agent, reached by handoff, blocking a card once (issue #47).

    Two claims, the pair the gate's tests already use. The tool is genuinely reachable on a real
    call path through the third agent. And the idempotency key is genuinely the relay's, generated
    once per call, so a model that calls the tool twice blocks once.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _call(self, blocks=1, keyed=True, agent=gate.CARDS_AGENT):
        frames = [*_keyed(DEFAULT_PIN)] if keyed else []
        frames.append(audio_frame("ive-lost-my-card"))
        events = [function_call(specs.handoff_tool_name(agent), "{}", call_id="call-handoff")]
        events += [
            function_call("block_card", "{}", call_id=f"call-block-{i}") for i in range(blocks)
        ]
        events.append(response_done())
        transport = FakeTransport(frames=frames, hang=True)
        realtime = FakeRealtimeServer(events=events, respond_after_appends=1)
        return transport, realtime

    def _result(self, realtime, call_id="call-block-0"):
        return json.loads(dict(realtime.tool_outputs)[call_id])

    def test_an_authenticated_caller_can_block_their_card(self):
        transport, realtime = self._call()
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertIn("blocked", self._result(realtime)["result"])
        self.assertTrue(self.core_banking.card_blocked)

    def test_the_caller_is_told_it_cannot_be_undone(self):
        # Said in the sentence at the end of the operation as well as before it. The caller will
        # remember the operation by what they were told when it finished.
        transport, realtime = self._call()
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertIn("can't be unblocked", self._result(realtime)["result"])

    def test_a_second_block_on_the_same_call_blocks_nothing_twice(self):
        transport, realtime = self._call(blocks=2)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        # One key, sent twice, so the service answers the second from its record of the first --
        # and the caller hears the same thing rather than a second confirmation of a second block.
        self.assertEqual(len(self.core_banking.idempotency), 1)
        self.assertEqual(
            self._result(realtime, "call-block-0")["result"],
            self._result(realtime, "call-block-1")["result"],
        )

    def test_the_key_is_the_relays_and_is_scoped_to_the_call(self):
        # Two calls, two keys. A key scoped to the process would let one caller's block answer
        # another caller's request, which is the failure a per-call key exists to prevent.
        keys = []
        for _ in range(2):
            client = FakeCoreBankingClient()
            transport, realtime = self._call()
            asyncio.run(run_call(transport, realtime, client, FakeCallRecordStore()))
            keys.extend(client.idempotency)
        self.assertEqual(len(set(keys)), 2)

    def test_the_key_carries_no_decimal_digit(self):
        """B2 (issue #53's constraint, enforced where the key is made).

        A random hex identifier is drawn from an alphabet more than half digits, so across enough
        calls it will eventually spell a four-digit run by chance and turn the run-wide scan red on
        a coincidence. Driven off the generator rather than off one sample, so the property is the
        thing asserted rather than one lucky draw.
        """
        for _ in range(200):
            key = session_module._new_idempotency_key()
            self.assertFalse(any(character.isdigit() for character in key), key)

    def test_a_key_and_a_frame_id_are_not_mistaken_for_each_other(self):
        self.assertTrue(session_module._new_idempotency_key().startswith("idem_"))
        self.assertTrue(session_module._new_event_id().startswith("evt_"))

    def test_an_anonymous_caller_is_refused_and_the_card_is_untouched(self):
        transport, realtime = self._call(keyed=False)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(self._result(realtime), {"error": gate.REFUSAL})
        self.assertFalse(self.core_banking.card_blocked)
        self.assertNotIn("block_card", self.core_banking.calls)

    def test_the_banking_agent_cannot_block_a_card(self):
        # block_card is Cards's and nobody else's. A caller routed to banking who asks for it is
        # refused, which is what keeps the agent table and the permission table agreeing.
        transport, realtime = self._call(agent=gate.BANKING_AGENT)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(self._result(realtime), {"error": gate.REFUSAL})
        self.assertFalse(self.core_banking.card_blocked)


class TheThirdAgentNeededNothingElse(unittest.TestCase):
    """Issue #20's scaling claim, tested rather than asserted (issue #47).

    `agents/specs.py` has said since Phase 2 that adding an agent is a table row rather than a
    change to enforcement, dispatch, or handoff handling. Three phases later there was finally a
    third agent to try it with. These are the specific things that would have had to change if the
    claim were false.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def test_routing_to_cards_reconfigures_the_one_session(self):
        transport = FakeTransport(frames=[audio_frame("lost-my-card")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_cards", "{}", call_id="call-handoff"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        configs = realtime.session_configs
        self.assertEqual(len(configs), 2)
        self.assertEqual(
            sorted(t["name"] for t in configs[1]["tools"]), ["block_card", "escalate_to_human"]
        )
        self.assertNotEqual(configs[0]["instructions"], configs[1]["instructions"])

    def test_the_banking_agent_cannot_forge_an_edge_to_cards(self):
        # Banking declares no handoff at all, so `handoff_to_cards` from banking is not a handoff --
        # it falls through to the gate as an unrecognised tool name and is refused. This is the
        # Phase 2 fix for hallucinated handoffs, still holding with three agents in the table.
        self.assertIsNone(specs.handoff_target("handoff_to_cards", gate.BANKING_AGENT))

    def test_cards_cannot_route_the_call_onward(self):
        for target in (gate.TRIAGE_AGENT, gate.BANKING_AGENT):
            with self.subTest(target=target):
                self.assertIsNone(
                    specs.handoff_target(specs.handoff_tool_name(target), gate.CARDS_AGENT)
                )

    def test_a_forged_handoff_from_cards_is_refused_on_a_real_call(self):
        transport = FakeTransport(frames=[audio_frame("now-my-balance")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_cards", "{}", call_id="call-handoff"),
                function_call("handoff_to_banking", "{}", call_id="call-forged"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        # Two configurations, not three: the forged handoff reconfigured nothing.
        self.assertEqual(len(realtime.session_configs), 2)
        self.assertEqual(
            json.loads(dict(realtime.tool_outputs)["call-forged"]), {"error": gate.REFUSAL}
        )


class WholeCallEscalation(unittest.TestCase):
    """**T-ESCALATION-LOGGED** (docs/PLAN.md decision 17), and the store proved to be in the path.

    Two claims, again. The record is written with what it was given -- that is the named test case.
    And the store is genuinely consulted on a real call rather than merely correct in isolation,
    which is what tests/test_call_records.py cannot show.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _call(self, reason=REASONS[0], keyed=False, correlation_id="corr-abc"):
        frames = [*_keyed(DEFAULT_PIN)] if keyed else []
        frames.append(audio_frame("get-me-a-person"))
        transport = FakeTransport(frames=frames, hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call(
                    "escalate_to_human", json.dumps({"reason": reason}), call_id="call-escalate"
                ),
                # The response that CALLED escalate_to_human gets its own response.done first, no
                # audio -- same as any tool-call-only response (confirmed live 2026-09-14: every
                # tool-call turn's `agent_spoke` is False). Scripted explicitly rather than left out:
                # an earlier version of this fix consumed `pending_escalation` here, one response
                # too early, and this is the event that fixture must produce to catch that again.
                response_done(),
                # The response the code asks for alongside the tool's output (issue #48) -- the
                # model's own closing remark, which must actually be relayed before the call ends.
                # Scripted here rather than left out, so a regression that stops relaying it (the
                # 2026-09-14 bug: raising right after response.create, before this delta and its
                # response.done could ever arrive) fails a test instead of only a live call.
                audio_delta("connecting you now"),
                response_done(),
                # Never reached: the relay raises once the response.done above fires. Scripted
                # anyway, so "the call ended there" is a fact about the relay rather than about the
                # fake running out of events.
                function_call("get_balance", '{"account": "chequing"}', call_id="call-after"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        return transport, realtime, correlation_id

    def _run(self, **kwargs):
        transport, realtime, correlation_id = self._call(**kwargs)
        asyncio.run(
            run_call(transport, realtime, self.core_banking, self.call_records, correlation_id)
        )
        return transport, realtime

    def test_one_record_is_written_carrying_what_it_was_given(self):
        self._run(reason=REASONS[1])
        self.assertEqual(len(self.call_records.escalations), 1)
        record = self.call_records.escalations[0]
        self.assertEqual(record.correlation_id, "corr-abc")
        self.assertEqual(record.reason, REASONS[1])
        self.assertTrue(record.occurred_at)

    def test_the_store_is_genuinely_in_the_path(self):
        # The second claim: a store nobody consults records nothing, and that failure passes every
        # test of what it would have recorded.
        self._run()
        # `record_minutes` follows on every path out (issue #50) -- what this asserts is that the
        # escalation itself reached the store, in order, before the call's own bookkeeping.
        self.assertEqual(self.call_records.calls[0], "record_escalation")

    def test_the_caller_is_told_before_the_call_ends(self):
        # The ordering the whole design turns on: output, then a response request, and -- the part
        # a live call found missing on 2026-09-14 -- the raise only after that response's audio has
        # actually reached the caller, not merely after the request for it was sent.
        transport, realtime = self._run()
        self.assertEqual(
            json.loads(dict(realtime.tool_outputs)["call-escalate"]),
            {"result": tools_module.ESCALATED},
        )
        self.assertEqual(realtime.sent_types[-2:], ["conversation.item.create", "response.create"])
        # The actual regression: sending the request proves nothing by itself (a relay that raised
        # immediately after would still pass the assertion above) -- what must be true is that the
        # closing remark's own audio was relayed to the caller before the call ended.
        self.assertEqual(transport.sent_audio_payloads, ["connecting you now"])

    def test_a_tool_call_before_the_closing_remark_does_not_end_the_call_early(self):
        # The gap a 2026-09-14 code review found in the first version of this fix: watching only
        # "the next response.done" ends the call in silence anyway if the model's closing turn
        # opens with another tool call before it actually speaks -- the response that call belongs
        # to gets its own response.done first, with no audio, exactly like the escalation's own
        # response did. `response_had_a_tool_call` is what this test pins.
        transport = FakeTransport(frames=[audio_frame("get-me-a-person")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call(
                    "escalate_to_human", json.dumps({"reason": REASONS[0]}), call_id="call-escalate"
                ),
                response_done(),  # the escalation's own response -- no audio
                function_call("get_balance", '{"account": "chequing"}', call_id="call-nested"),
                response_done(),  # the nested tool call's response -- also no audio
                audio_delta("connecting you now"),
                response_done(),  # only now does the model actually speak
            ],
            respond_after_appends=1,
        )
        asyncio.run(
            run_call(transport, realtime, self.core_banking, self.call_records, "corr-nested")
        )
        self.assertEqual(transport.sent_audio_payloads, ["connecting you now"])
        self.assertEqual(len(self.call_records.escalations), 1)

    def test_the_call_ends_and_nothing_after_it_runs(self):
        _, realtime = self._run()
        self.assertNotIn("call-after", dict(realtime.tool_outputs))

    def test_the_call_ends_through_the_expected_branch_not_as_a_failure(self):
        # `run_call` returning rather than raising is the assertion: an unexpected exception would
        # propagate out of it and be a relay failure rather than a call that ended.
        self._run()
        self.assertTrue(self.call_records.escalations)

    def test_an_anonymous_caller_can_reach_a_person(self):
        """The reason the tool is granted while anonymous at all (issue #48).

        A caller who cannot get through the PIN check is exactly who needs this, and being locked
        out of authentication must not also mean being cut off. No PIN is keyed here.
        """
        self._run(reason=REASONS[0])
        self.assertEqual(len(self.call_records.escalations), 1)

    def test_an_anonymous_escalation_never_touches_core_banking(self):
        # B1's target does not move, stated where it is observable: escalation reaches the store and
        # nothing that holds money. The client saw nothing at all on this call.
        self._run()
        self.assertEqual(self.core_banking.calls, [])

    def test_an_authenticated_caller_can_escalate_too(self):
        self._run(keyed=True)
        self.assertEqual(len(self.call_records.escalations), 1)
        self.assertEqual(self.core_banking.calls, ["verify_pin"])

    def test_a_reason_the_model_invented_is_malformed_and_records_nothing(self):
        # The schema's enum is a request, not a guarantee. The handler re-checks it, and an
        # unrecognised reason is a malformed tool call rather than a record nobody can group by.
        _, realtime = self._run(reason="the caller sounded upset")
        self.assertEqual(
            json.loads(dict(realtime.tool_outputs)["call-escalate"]),
            {"error": tools_module.MALFORMED},
        )
        self.assertEqual(self.call_records.escalations, [])

    def test_a_malformed_escalation_does_not_end_the_call(self):
        # The call carries on, so the model can ask again. Ending a call on a malformed tool call
        # would make a mis-picked reason code cost the caller their call.
        _, realtime = self._run(reason="not-a-reason-code")
        self.assertIn("call-after", dict(realtime.tool_outputs))

    def test_a_failed_record_still_ends_the_call_with_the_same_apology(self):
        """The one place in this phase where a store failure is NOT fail-closed.

        Reaching a person matters more than recording that somebody asked to. Deliberate, stated in
        the exit criteria as criterion 9, and asserted here so it cannot be mistaken later for a
        fail-closed branch somebody forgot to write.
        """
        self.call_records.fail_with = store_unavailable()
        _, realtime = self._run()
        self.assertEqual(
            json.loads(dict(realtime.tool_outputs)["call-escalate"]),
            {"result": tools_module.ESCALATED},
        )
        self.assertNotIn("call-after", dict(realtime.tool_outputs))

    def test_a_failed_record_is_logged_loudly(self):
        self.call_records.fail_with = store_unavailable()
        transport, realtime, correlation_id = self._call()
        with self.assertLogs("dispatch", level="ERROR") as cm:
            asyncio.run(
                run_call(transport, realtime, self.core_banking, self.call_records, correlation_id)
            )
        self.assertTrue(any("escalation record NOT written" in line for line in cm.output))

    def test_no_outbound_leg_is_ever_attempted(self):
        """Decision 17, asserted rather than trusted.

        There is no ACS transfer API reachable from this path, and the way to know is the same way
        the whole-call tests already know a call opens no network connection: make any outbound
        connection attempt fail the test. An escalation that quietly dialled somebody would show up
        here and nowhere else.
        """
        transport, realtime, correlation_id = self._call()
        with patch.object(socket.socket, "connect", side_effect=AssertionError("outbound leg")), \
             patch.object(socket.socket, "connect_ex", side_effect=AssertionError("outbound leg")):
            asyncio.run(
                run_call(transport, realtime, self.core_banking, self.call_records, correlation_id)
            )
        self.assertEqual(len(self.call_records.escalations), 1)

    def test_the_relay_imports_no_call_transfer_api(self):
        # The other direction, and the cheap one: the relay cannot place a leg it has no way to
        # name. Asserted on the module's own namespace so a future import turns this red.
        for forbidden in ("transfer_call", "redirect_call", "add_participant", "CallAutomation"):
            with self.subTest(name=forbidden):
                self.assertFalse(hasattr(session_module, forbidden))

    def test_the_record_carries_no_keyed_digit(self):
        # B2 over the first persisted record the voice agent owns. The caller keys a real PIN here,
        # so there is genuinely something for the record to have leaked.
        self._run(keyed=True)
        record = self.call_records.escalations[0]
        for value in (record.correlation_id, record.reason, record.occurred_at):
            self.assertNotIn(DEFAULT_PIN, str(value))


class TheClosedPath(unittest.TestCase):
    """**`T-B4-FAILCLOSED`** -- a test, not a name (issue #49).

    Three ways the store can fail to answer, and an exhausted day, all produce the same closed path.
    Asserted on **what the caller is told and on the call ending**, never on an internal flag: a
    brake is only a brake if the caller hears the refusal, and an assertion on a boolean somewhere
    would pass just as happily for a brake nobody consulted.
    """

    def setUp(self):
        self.call_records = FakeCallRecordStore()

    def _closed_call(self):
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("were-closed"), response_done()], respond_after_appends=0
        )
        return transport, realtime

    def _spoken_notes(self, realtime):
        return [
            part["text"]
            for message in realtime.sent
            if message["type"] == "conversation.item.create"
            and message["item"].get("type") == "message"
            for part in message["item"]["content"]
        ]

    def _assert_budget_refused(self, store):
        with self.assertRaises(caps.DailyBudgetSpent):
            asyncio.run(budget_or_closed(store))

    def test_an_exhausted_day_refuses(self):
        self._assert_budget_refused(
            FakeCallRecordStore(minutes={day_key(): caps.MAX_DAILY_MINUTES})
        )

    def test_a_day_over_its_budget_refuses(self):
        self._assert_budget_refused(
            FakeCallRecordStore(minutes={day_key(): caps.MAX_DAILY_MINUTES + 99})
        )

    def test_a_store_that_raises_refuses(self):
        self._assert_budget_refused(FakeCallRecordStore(fail_with=store_unavailable()))

    def test_a_store_that_times_out_refuses(self):
        # A timeout is not a distinct standing: the client turns every way of not answering into
        # one type, precisely so nobody downstream can treat one of them as benign.
        self._assert_budget_refused(FakeCallRecordStore(fail_with=store_unavailable("timed out")))

    def test_a_store_that_never_answers_at_all_refuses(self):
        """Criterion 11's "times out" branch, driven by a store that actually hangs.

        The test above arranges a store that has *already decided* to fail, which proves the
        client's own timeout is translated correctly but proves nothing about there being one.
        Until 2026-09-11 there was not: no timeout was set when the table client was built and no
        deadline wrapped the read, so a Storage endpoint that accepted the connection and never
        replied stalled the media socket with a caller on it. The evidence for the criterion was a
        fake pre-raising the exception the code was supposed to produce -- "a claim that outruns
        its evidence", which the phase had named as its own risk (/code-review, 2026-09-11).
        """
        class NeverAnswers:
            async def minutes_used(self, day):
                await asyncio.Event().wait()  # a socket that is open and silent

            async def record_minutes(self, day, minutes):
                await asyncio.Event().wait()

        started = time.monotonic()
        self._assert_budget_refused(NeverAnswers())
        # And it refused on a deadline rather than by luck: bounded, and bounded by roughly the
        # configured value rather than by the suite's own patience.
        self.assertLess(time.monotonic() - started, session_module.LEDGER_DEADLINE_SECONDS + 2)

    def test_a_store_that_answers_unreadably_refuses(self):
        # The real client raises the same type for a row it cannot parse -- proved directly in
        # tests/test_call_records.py. Arranged here through the fake so the branch is covered at
        # this seam too.
        self._assert_budget_refused(
            FakeCallRecordStore(fail_with=store_unavailable("the row could not be read"))
        )

    def test_an_intact_budget_serves_the_call(self):
        # Not trivially always-closed: without this, a brake wired permanently shut would pass every
        # test above. **Returning at all is the assertion** -- the guard hands back nothing since
        # 2026-09-11, because its one caller discarded the remaining-minutes figure it used to
        # compute (/code-review, 2026-09-11).
        self.assertIsNone(asyncio.run(budget_or_closed(FakeCallRecordStore())))

    def test_a_day_just_under_its_budget_still_serves(self):
        # The boundary still matters even though no figure comes back: a cap that refused the last
        # minute of the day would be off by one in the direction that strands a real caller.
        store = FakeCallRecordStore(minutes={day_key(): caps.MAX_DAILY_MINUTES - 1})
        self.assertIsNone(asyncio.run(budget_or_closed(store)))

    def test_the_caller_is_told_the_service_is_closed(self):
        transport, realtime = self._closed_call()
        asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertEqual(self._spoken_notes(realtime), [session_module.CLOSED])

    def test_the_closed_sentence_is_injected_through_phase_fours_mechanism(self):
        # An item followed by a response request -- not a second way of making the agent say
        # something it did not decide.
        transport, realtime = self._closed_call()
        asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertEqual(
            realtime.sent_types, ["session.update", "conversation.item.create", "response.create"]
        )

    def test_the_closed_path_is_bounded_to_one_turn(self):
        # The relay stops at the first `response.done`. A second scripted response is never reached,
        # so the bound is the relay's rather than the model choosing to be brief.
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                audio_delta("were-closed"),
                response_done(),
                audio_delta("and-something-else"),
                response_done(),
            ],
            respond_after_appends=0,
        )
        asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertEqual(transport.sent_audio_payloads, ["were-closed"])

    def test_the_turn_bound_is_the_named_constant_and_not_a_coincidence(self):
        """`MAX_CLOSED_CALL_TURNS` actually decides where the path stops.

        The bound above held structurally -- the relay returned on the first `response.done` --
        while `cost/caps.py`'s constant was referenced nowhere in the codebase. So the test above
        would have passed with the constant set to 1, to 50, or deleted, and the caps module's
        claim that the bound is "enforced by the relay rather than by the model choosing to be
        brief" pointed at a value that enforced nothing (/code-review, 2026-09-11).

        Raising it has to change behaviour, or the constant is decoration.
        """
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                audio_delta("were-closed"),
                response_done(),
                audio_delta("and-something-else"),
                response_done(),
            ],
            respond_after_appends=0,
        )
        with patch.object(caps, "MAX_CLOSED_CALL_TURNS", 2):
            asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertEqual(
            transport.sent_audio_payloads, ["were-closed", "and-something-else"]
        )

    def test_the_closed_path_is_bounded_in_wall_clock_too(self):
        """A model that never finishes must not hold the line open.

        The turn bound alone would wait forever for a `response.done` that is not coming, which is
        exactly the shape of "the brake became the cost".
        """
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(hang=True)
        with patch.object(caps, "MAX_CLOSED_CALL_SECONDS", 0.05):
            asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertTrue(self._spoken_notes(realtime))

    def test_the_closed_path_never_reaches_core_banking(self):
        # It has no client at all: `run_closed_call` does not take one. Asserted on the signature so
        # the property is structural rather than a matter of what the body happens to do today.
        self.assertNotIn("core_banking", inspect.signature(run_closed_call).parameters)

    def test_the_closed_paths_own_minutes_are_charged(self):
        # A brake whose usage was invisible in the one place it matters would not be a brake
        # anybody could audit.
        transport, realtime = self._closed_call()
        asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertIn("record_minutes", self.call_records.calls)
        self.assertGreater(self.call_records.minutes[day_key()], 0)

    def test_an_unwritable_ledger_does_not_break_the_closed_path(self):
        # The call is already over; raising here would turn a bookkeeping failure into a relay
        # failure on a call that had otherwise finished.
        transport, realtime = self._closed_call()
        self.call_records.fail_with = store_unavailable()
        asyncio.run(run_closed_call(transport, realtime, self.call_records))

    def test_an_unwritable_ledger_is_logged_as_undercounting(self):
        transport, realtime = self._closed_call()
        self.call_records.fail_with = store_unavailable()
        with self.assertLogs("bridge", level="ERROR") as cm:
            asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertTrue(any("undercounting" in line for line in cm.output))

    def test_exhausted_and_unreadable_are_one_branch_not_two(self):
        """Fail-closed is one branch, not two that could drift (issue #49).

        And the caller hears one sentence: somebody who could tell "we are closed" from "we could
        not check" would have a probing oracle for exactly the condition that costs money.
        """
        spent = FakeCallRecordStore(minutes={day_key(): caps.MAX_DAILY_MINUTES})
        unreadable = FakeCallRecordStore(fail_with=store_unavailable())
        for store in (spent, unreadable):
            with self.subTest(store=type(store).__name__), \
                 self.assertRaises(caps.DailyBudgetSpent):
                asyncio.run(budget_or_closed(store))


class TheDayBoundary(unittest.TestCase):
    """"Today" is a date in a stated timezone, tested against an injected clock (issue #49).

    The same arrangement the circuit breaker's open window uses, and for the same reason: a rollover
    asserted by waiting would be a test that takes a day.
    """

    def test_the_day_is_a_date_in_the_stated_timezone(self):
        moment = datetime.datetime(2026, 9, 11, 23, 59, tzinfo=datetime.UTC)
        self.assertEqual(day_key(moment), "2026-09-11")

    def test_a_moment_in_another_zone_is_converted_not_truncated(self):
        # 2026-09-12 01:30 in UTC+2 is still 2026-09-11 in UTC. A key that took the local date would
        # charge the call to tomorrow.
        elsewhere = datetime.timezone(datetime.timedelta(hours=2))
        moment = datetime.datetime(2026, 9, 12, 1, 30, tzinfo=elsewhere)
        self.assertEqual(day_key(moment), "2026-09-11")

    def test_minutes_land_on_different_days_across_a_rollover(self):
        store = FakeCallRecordStore()
        before = datetime.datetime(2026, 9, 11, 23, 59, tzinfo=datetime.UTC)
        after = datetime.datetime(2026, 9, 12, 0, 1, tzinfo=datetime.UTC)
        asyncio.run(store.record_minutes(day_key(before), 5.0))
        asyncio.run(store.record_minutes(day_key(after), 3.0))
        self.assertEqual(store.minutes, {"2026-09-11": 5.0, "2026-09-12": 3.0})

    def test_a_spent_day_does_not_refuse_the_next_one(self):
        before = datetime.datetime(2026, 9, 11, 23, 59, tzinfo=datetime.UTC)
        after = datetime.datetime(2026, 9, 12, 0, 1, tzinfo=datetime.UTC)
        store = FakeCallRecordStore(minutes={day_key(before): caps.MAX_DAILY_MINUTES})
        with self.assertRaises(caps.DailyBudgetSpent):
            asyncio.run(budget_or_closed(store, now=before))
        # Rollover: a fresh budget, instantly, with no waiting and no clock patching of the module.
        # The refusal above and the return here are the whole contrast -- the same store, the same
        # ledger, one minute apart.
        self.assertIsNone(asyncio.run(budget_or_closed(store, now=after)))


class RefusesToSend(FakeRealtimeServer):
    """A realtime connection that fails on the very first frame the relay sends.

    Written once rather than three times inside the tests that use it (/code-review, 2026-09-11):
    three verbatim copies of a four-line fake is three places for "the first frame" to stop meaning
    the same thing.
    """

    async def send(self, message):
        raise RuntimeError("the realtime connection broke on the first frame")


class MinutesAreRecordedOnEveryPathOut(unittest.TestCase):
    """A brake that reads but never writes never trips (issue #50).

    The previous class proves a spent day refuses calls. This proves the day ever becomes spent --
    and specifically that it does so on **every** way a call can end, including the ways that raise.
    Minutes that go unrecorded are minutes the cap cannot see, and a cap that undercounts fails
    open, which is the direction that costs money.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def _run(self, transport, realtime):
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))

    def _assert_charged(self):
        self.assertIn("record_minutes", self.call_records.calls)
        self.assertGreaterEqual(self.call_records.minutes.get(day_key(), -1), 0)

    def test_a_clean_hangup_is_charged(self):
        self._run(FakeTransport(frames=[audio_frame("hi")], hang=False),
                  FakeRealtimeServer(events=[response_done()], respond_after_appends=1))
        self._assert_charged()

    def test_a_turn_cap_is_charged(self):
        with patch.object(caps, "MAX_CALL_TURNS", 1):
            self._run(FakeTransport(frames=[audio_frame("hi")], hang=True),
                      FakeRealtimeServer(events=[response_done()], respond_after_appends=1))
        self._assert_charged()

    def test_a_wall_clock_cap_is_charged(self):
        with patch.object(caps, "MAX_CALL_SECONDS", 0.05):
            self._run(FakeTransport(hang=True), FakeRealtimeServer(hang=True))
        self._assert_charged()

    def test_exhausted_attempts_are_charged(self):
        frames = _keyed("9999") + _keyed("8888") + _keyed("7777")
        self._run(FakeTransport(frames=frames, hang=True),
                  FakeRealtimeServer(events=[], respond_after_appends=0))
        self._assert_charged()

    def test_an_escalation_is_charged(self):
        transport = FakeTransport(frames=[audio_frame("a-person-please")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call(
                    "escalate_to_human", json.dumps({"reason": REASONS[0]}), call_id="esc"
                ),
                response_done(),
            ],
            respond_after_appends=1,
        )
        self._run(transport, realtime)
        self._assert_charged()

    def test_an_unhandled_failure_is_charged(self):
        """The path that matters most, and the one a `finally` exists for.

        A relay failure propagates out of `run_call` -- it is not an expected ending -- and the day
        still has to be charged for the minutes the call burned before it broke. Arranged by making
        the transport raise something the relay does not catch.
        """
        class Exploding(FakeTransport):
            async def receive_text(self):
                raise RuntimeError("the transport broke")

        with self.assertRaises(RuntimeError):
            self._run(Exploding(hang=True), FakeRealtimeServer(hang=True))
        self._assert_charged()

    def test_a_send_that_fails_before_the_relay_starts_is_still_charged(self):
        """The gap in "every path out": the three frames sent *before* the `try` opened.

        `run_call` took its start time, sent the session update and the greeting, and only then
        entered the `try` whose `finally` records minutes and ends the call's auth state. A
        realtime send that raised on either of those two frames skipped both -- so a call that
        reached AOAI, burned wall clock and failed left no trace in the day's ledger, and the
        authenticator's buffer was never zeroed. The docstring on `_record_minutes` said "on
        every path out" the whole time (/code-review, 2026-09-11).

        Small minutes, but B4's own module names undercounting as the fail-open direction, and a
        backend failing at the first frame is exactly the condition under which every call in a
        row takes this path.
        """
        with self.assertRaises(RuntimeError):
            self._run(FakeTransport(hang=True), RefusesToSend(hang=True))
        self._assert_charged()

    def test_a_send_that_fails_before_the_relay_starts_still_ends_the_auth_state(self):
        # The other half of the same `finally`. `authenticator.end_call()` zeroes the keypad
        # buffer, and B2's rule is that the PIN does not outlive the call that keyed it -- a call
        # that skipped this left the buffer holding whatever it held.
        ended = []
        real_end_call = auth_module.Authenticator.end_call

        def spy(self):
            ended.append(True)
            return real_end_call(self)

        with patch.object(auth_module.Authenticator, "end_call", spy), \
             self.assertRaises(RuntimeError):
            self._run(FakeTransport(hang=True), RefusesToSend(hang=True))
        self.assertEqual(ended, [True])

    def test_the_closed_path_is_charged_even_if_its_first_frame_fails(self):
        # The closed path had the same three-sends-before-the-`try` shape as `run_call`, and its
        # own docstring makes the stronger claim: "Its own minutes count too... a brake whose
        # usage was invisible in the one place it matters would not be a brake anybody could
        # audit." A closed call that failed on its first frame was invisible.
        with self.assertRaises(RuntimeError):
            asyncio.run(run_closed_call(
                FakeTransport(hang=True), RefusesToSend(hang=True), self.call_records
            ))
        self._assert_charged()

    def test_the_minutes_recorded_are_the_minutes_the_call_took(self):
        # Not a constant, and not the per-call ceiling: a cap fed a fixed number per call would be
        # a call counter wearing a minute cap's name.
        self._run(FakeTransport(frames=[audio_frame("hi")], hang=False),
                  FakeRealtimeServer(events=[response_done()], respond_after_appends=1))
        recorded = self.call_records.minutes[day_key()]
        self.assertGreater(recorded, 0)
        self.assertLess(recorded, caps.MAX_CALL_SECONDS / 60)

    def test_two_calls_accumulate_against_the_same_day(self):
        for _ in range(2):
            self._run(FakeTransport(frames=[audio_frame("hi")], hang=False),
                      FakeRealtimeServer(events=[response_done()], respond_after_appends=1))
        self.assertEqual(
            [name for name in self.call_records.calls if name == "record_minutes"],
            ["record_minutes"] * 2,
        )

    def test_an_unwritable_ledger_does_not_break_a_call_that_had_finished(self):
        self.call_records.fail_with = store_unavailable()
        self._run(FakeTransport(frames=[audio_frame("hi")], hang=False),
                  FakeRealtimeServer(events=[response_done()], respond_after_appends=1))

    def test_an_unwritable_ledger_says_so_loudly(self):
        self.call_records.fail_with = store_unavailable()
        with self.assertLogs("bridge", level="ERROR") as cm:
            self._run(FakeTransport(frames=[audio_frame("hi")], hang=False),
                      FakeRealtimeServer(events=[response_done()], respond_after_appends=1))
        self.assertTrue(any("undercounting" in line for line in cm.output))


class TheAgentGreetsWithoutWaiting(unittest.TestCase):
    """The dead-air gap, unparked (issue #51).

    Parked at Phase 3 kickoff and again at Phase 4's, as a greeting-path defect rather than an
    auth-path one. It stopped being parkable in the phase whose exit depends on a caller keying a
    PIN they were never asked for: the greeting is the thing that asks, so a caller who said nothing
    was waiting on a prompt that had not been triggered and never would be.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()
        self.call_records = FakeCallRecordStore()

    def test_the_agent_speaks_before_the_caller_does(self):
        """The property, stated as what an observer would see.

        The fake model holds its events until a caller frame has been forwarded, so the assertion
        that actually bites is the one below about ordering. This one says the plain thing: a call
        where the caller never says a word still produces speech.
        """
        transport = FakeTransport(frames=[], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("hello-please-key-your-pin"), response_done()],
            respond_after_appends=0,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(transport.sent_audio_payloads, ["hello-please-key-your-pin"])

    def test_the_response_is_requested_immediately_after_the_session_is_configured(self):
        transport = FakeTransport(frames=[audio_frame("hi")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(realtime.sent_types[:2], ["session.update", "response.create"])

    def test_nothing_is_appended_before_the_greeting_is_asked_for(self):
        # The ordering that makes the dead air go away: the request must not be behind the first
        # caller frame, or it would be the thing it replaced.
        transport = FakeTransport(frames=[audio_frame("hi")], hang=True)
        realtime = FakeRealtimeServer(events=[response_done()], respond_after_appends=1)
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        greeting = realtime.sent_types.index("response.create")
        appended = realtime.sent_types.index("input_audio_buffer.append")
        self.assertLess(greeting, appended)

    def test_a_handoff_does_not_fire_a_second_greeting(self):
        # Handoff already sends its own session.update + response.create pair. What must not happen
        # is the opening greeting being re-sent, which would have the specialist greet the caller
        # again -- the thing every specialist's instructions explicitly tell it not to do.
        transport = FakeTransport(frames=[audio_frame("balance-please")], hang=True)
        realtime = FakeRealtimeServer(
            events=[
                function_call("handoff_to_banking", "{}", call_id="handoff"),
                response_done(),
            ],
            respond_after_appends=1,
        )
        asyncio.run(run_call(transport, realtime, self.core_banking, self.call_records))
        self.assertEqual(realtime.sent_types.count("session.update"), 2)
        self.assertEqual(realtime.sent_types.count("response.create"), 2)

    def test_the_closed_path_does_not_gain_a_greeting_turn(self):
        # The closed path builds its own opening -- session.update, the closed item, one request --
        # and must stay at one turn. A greeting ahead of the closed sentence would double the cost
        # of refusing a call.
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("were-closed"), response_done()], respond_after_appends=0
        )
        asyncio.run(run_closed_call(transport, realtime, self.call_records))
        self.assertEqual(realtime.sent_types.count("response.create"), 1)

    def test_turn_detection_matches_the_2026_09_12_tuning(self):
        """`server_vad` moved exactly once, deliberately, and everything else about it stayed put.

        This pinned `silence_duration_ms: 200` until the interrupt-the-caller defect (open item 9)
        reproduced a third time on Phase 5's second real call, described as talking over the caller
        rather than the earlier one-off. Raised to 600 (Marco, 2026-09-12) -- isolated to this one
        field so a regression on a later real call is attributable to this line, not to whatever
        else that phase touches. The greeting (issue #51) is the same discipline applied earlier:
        changing when the agent first speaks *and* how it detects turns in one phase would make a
        regression unattributable to either.
        """
        self.assertEqual(
            session_module._AUDIO_CONFIG["input"]["turn_detection"],
            {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 600,
                "create_response": True,
                "interrupt_response": True,
            },
        )
