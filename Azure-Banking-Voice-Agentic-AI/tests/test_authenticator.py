"""The keypad's rules, tested with no call, no socket and no model (issue #36).

This is the one new seam Phase 4 adds. It mirrors the two-claim structure the gate's own tests
already use: here the machine's rules are proved directly, and tests/test_whole_call.py separately
proves it is actually in the path. A control that decides perfectly and is never consulted protects
nothing, and that failure would pass every test of the first kind.

**Nothing here asserts how many digits are buffered or what the internal state is called.** Those
are private to the machine by design -- the gate's key space stays at two agents by two states
precisely because the digit count never leaves this object. What is asserted is what an outside
observer sees: what reached the system of record, what the caller is told, what a log line carries.
"""
import ast
import inspect
import pathlib
import unittest

from azbank_voice_agent.auth import SENTENCES, Authenticator, outcomes, sentence_for
from azbank_voice_agent.core_banking import CoreBankingUnavailable
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient


class ExplodingClient:
    """A client that fails the test if it is touched at all.

    Used to prove the buffer transitions are pure: feeding digits that do not complete a PIN must
    reach no client, which is what makes the keypad's rules testable with no backend.
    """

    def __init__(self, test):
        self._test = test

    async def verify_pin(self, pin):
        self._test.fail("a buffer transition reached the core-banking client")


def _keys(*presses):
    """Spelled out so a test reads as a caller's keypresses rather than as a string index."""
    return list(presses)


class TheKeypadProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_four_digits_submit_automatically_on_the_fourth(self):
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in DEFAULT_PIN[:3]:
            self.assertEqual(await machine.key(key), outcomes.ACCUMULATING)
        self.assertEqual(client.calls, [], "nothing may be submitted before the fourth digit")
        self.assertEqual(await machine.key(DEFAULT_PIN[3]), outcomes.AUTHENTICATED)
        self.assertEqual(client.calls, ["verify_pin"])

    async def test_no_terminator_is_needed_and_pound_is_ignored(self):
        # A fixed length needs no terminator, so pound does nothing at all -- it neither submits
        # nor clears. A caller who keys it mid-entry must not lose the digits already keyed.
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in _keys("1", "2", "#", "3"):
            await machine.key(key)
        self.assertEqual(client.calls, [], "pound must not submit a short entry")
        self.assertEqual(await machine.key("4"), outcomes.AUTHENTICATED)

    async def test_pound_is_ignored_rather_than_accumulated(self):
        self.assertEqual(await Authenticator(ExplodingClient(self)).key("#"), outcomes.IGNORED)

    async def test_star_clears_the_buffer(self):
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in _keys("9", "9"):
            await machine.key(key)
        self.assertEqual(await machine.key("*"), outcomes.CLEARED)
        # The cleared digits are gone: four fresh digits authenticate, which they could not do if
        # the two nines were still in front of them.
        for key in DEFAULT_PIN[:3]:
            await machine.key(key)
        self.assertEqual(await machine.key(DEFAULT_PIN[3]), outcomes.AUTHENTICATED)

    async def test_a_mis_key_cleared_before_submission_costs_nothing(self):
        # Issue #36's own example, and CONTEXT.md's definition of an attempt: a submission that
        # never completed is not an attempt. Being careful must not be punished.
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in _keys("9", "9", "9", "*"):
            await machine.key(key)
        self.assertEqual(client.calls, [], "a cleared entry reaches the system of record")
        for key in DEFAULT_PIN:
            outcome = await machine.key(key)
        self.assertEqual(outcome, outcomes.AUTHENTICATED)

    async def test_a_key_that_is_neither_a_digit_nor_star_nor_pound_is_ignored(self):
        # DTMF carries A-D and there is no rule for them, so they do nothing rather than crash a
        # call. Anything unhandled on this path would take the call down with it.
        machine = Authenticator(ExplodingClient(self))
        for key in _keys("A", "B", "C", "D", "", "12", None, 4):
            with self.subTest(key=repr(key)):
                self.assertEqual(await machine.key(key), outcomes.IGNORED)

    def test_no_timer_of_any_kind_exists_in_this_package(self):
        """No inter-digit timeout, deliberately (issue #36).

        It is the only piece of Phase 4 that would put a timer on the audio event loop, so its
        absence is asserted rather than left to a comment that can rot. A partial entry stays
        partial for as long as the caller leaves it.

        Parsed rather than grepped: the module's own prose says the word "timeout" several times
        explaining why there isn't one, and a scan of raw source cannot tell that apart from a
        call to one. Names actually used in the code can.
        """
        from azbank_voice_agent.auth import authenticator as module

        tree = ast.parse(pathlib.Path(module.__file__).read_text())
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.Import):
                used.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                used.add((node.module or "").split(".")[0])
        forbidden = {
            "asyncio", "time", "threading", "sched", "sleep", "call_later", "call_at",
            "monotonic", "perf_counter", "wait_for", "Timer", "timeout",
        }
        self.assertEqual(used & forbidden, set())


class BufferTransitionsArePure(unittest.IsolatedAsyncioTestCase):
    """The only await is the submission (issue #36).

    That split is what keeps "pure state machine" honest for the part that is one, and it is
    asserted the way an outside observer can see it: a transition that is not a submission reaches
    no client at all.
    """

    async def test_accumulating_clearing_and_ignoring_reach_no_client(self):
        machine = Authenticator(ExplodingClient(self))
        for key in _keys("1", "2", "*", "#", "3", "A", "*"):
            await machine.key(key)


class TheTransitionIsOneWay(unittest.IsolatedAsyncioTestCase):
    async def test_further_digits_after_authentication_are_ignored(self):
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in DEFAULT_PIN:
            await machine.key(key)
        self.assertTrue(machine.is_authenticated)
        for key in _keys("9", "9", "9", "9"):
            self.assertEqual(await machine.key(key), outcomes.IGNORED)
        self.assertEqual(client.calls, ["verify_pin"], "a second check was submitted")
        self.assertTrue(machine.is_authenticated)

    async def test_no_path_returns_the_call_to_anonymous(self):
        # Including the one that looks most like it should: clearing the buffer after passing.
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in DEFAULT_PIN:
            await machine.key(key)
        for key in _keys("*", "#", "0"):
            await machine.key(key)
        self.assertTrue(machine.is_authenticated)

    async def test_a_fresh_machine_starts_anonymous(self):
        self.assertFalse(Authenticator(ExplodingClient(self)).is_authenticated)


class Attempts(unittest.IsolatedAsyncioTestCase):
    """An attempt is a completed check that came back a rejected credential (CONTEXT.md)."""

    def _machine(self, **kwargs):
        client = FakeCoreBankingClient(**kwargs)
        return client, Authenticator(client)

    async def _submit(self, machine, pin):
        outcome = None
        for key in pin:
            outcome = await machine.key(key)
        return outcome

    async def test_three_rejections_exhaust_the_attempts(self):
        client, machine = self._machine()
        self.assertEqual(await self._submit(machine, "9999"), outcomes.REJECTED)
        self.assertEqual(await self._submit(machine, "8888"), outcomes.REJECTED)
        self.assertEqual(await self._submit(machine, "7777"), outcomes.EXHAUSTED)
        self.assertEqual(client.calls, ["verify_pin"] * 3)
        self.assertFalse(machine.is_authenticated)

    async def test_the_right_pin_on_the_last_attempt_still_authenticates(self):
        # Exhaustion is three rejections, not three submissions.
        _, machine = self._machine()
        await self._submit(machine, "9999")
        await self._submit(machine, "8888")
        self.assertEqual(await self._submit(machine, DEFAULT_PIN), outcomes.AUTHENTICATED)

    async def test_an_unavailable_check_consumes_no_attempt(self):
        """The glossary's rule, and the caller-facing reason for it (issue #36).

        A check the bank never answered produced no verdict, so there is nothing to count. A
        caller must not have their three tries spent by somebody else's outage.
        """
        client = FakeCoreBankingClient(fail_with=CoreBankingUnavailable("down"))
        machine = Authenticator(client)
        for _ in range(5):
            self.assertEqual(await self._submit(machine, DEFAULT_PIN), outcomes.UNAVAILABLE)
        self.assertFalse(machine.is_authenticated)

        # And the attempts really are all still there: a working service now gets three rejections
        # before exhausting them, not fewer.
        client.fail_with = None
        self.assertEqual(await self._submit(machine, "9999"), outcomes.REJECTED)
        self.assertEqual(await self._submit(machine, "8888"), outcomes.REJECTED)
        self.assertEqual(await self._submit(machine, "7777"), outcomes.EXHAUSTED)

    async def test_an_unavailable_check_never_authenticates(self):
        # Fails closed: an outage is never a way in, which is the reason verification goes through
        # the client that already has the breaker.
        client = FakeCoreBankingClient(fail_with=CoreBankingUnavailable("down"))
        machine = Authenticator(client)
        self.assertEqual(await self._submit(machine, DEFAULT_PIN), outcomes.UNAVAILABLE)
        self.assertFalse(machine.is_authenticated)

    async def test_keys_after_exhaustion_are_ignored(self):
        client, machine = self._machine()
        for pin in ("9999", "8888", "7777"):
            await self._submit(machine, pin)
        for key in DEFAULT_PIN:
            self.assertEqual(await machine.key(key), outcomes.IGNORED)
        self.assertEqual(client.calls, ["verify_pin"] * 3, "a check ran after exhaustion")
        self.assertFalse(machine.is_authenticated)


class TheBufferIsZeroed(unittest.IsolatedAsyncioTestCase):
    """On submit, on clear, and on call end whatever the outcome (issue #36).

    Asserted through behaviour rather than by reading the buffer, which is private: digits that
    survived would show up as a later entry authenticating with the wrong keys, or failing with
    the right ones.
    """

    async def test_the_buffer_is_zeroed_on_submit(self):
        client = FakeCoreBankingClient()
        machine = Authenticator(client)
        for key in "9999":
            await machine.key(key)
        # If the four nines survived, these four would be the fifth to eighth digits and nothing
        # would submit here.
        for key in DEFAULT_PIN[:3]:
            await machine.key(key)
        self.assertEqual(await machine.key(DEFAULT_PIN[3]), outcomes.AUTHENTICATED)

    async def test_the_buffer_is_zeroed_on_call_end(self):
        machine = Authenticator(ExplodingClient(self))
        for key in DEFAULT_PIN[:3]:
            await machine.key(key)
        machine.end_call()
        # A fourth digit after the call ended must not complete the entry that was in flight.
        self.assertEqual(await machine.key(DEFAULT_PIN[3]), outcomes.IGNORED)

    async def test_ending_the_call_is_safe_whatever_the_outcome(self):
        # Called from the relay's cleanup, so it runs after success, after exhaustion, and after
        # nothing at all. None of those may raise.
        client = FakeCoreBankingClient()
        authenticated = Authenticator(client)
        for key in DEFAULT_PIN:
            await authenticated.key(key)
        for machine in (authenticated, Authenticator(client), Authenticator(client)):
            machine.end_call()
            machine.end_call()


class WhatTheCallerIsTold(unittest.IsolatedAsyncioTestCase):
    """The sentences are composed here, never in the service (issue #36).

    The same inversion rule Phase 3 established for mock-core-banking, restated for the second
    module that owns caller-facing prose: the system of record returns outcome tokens, and every
    sentence a caller hears is written on this side.
    """

    def test_every_outcome_the_relay_acts_on_has_a_sentence(self):
        for outcome in (outcomes.AUTHENTICATED, outcomes.REJECTED,
                        outcomes.EXHAUSTED, outcomes.UNAVAILABLE):
            with self.subTest(outcome=outcome):
                self.assertTrue(sentence_for(outcome))

    def test_the_silent_outcomes_have_no_sentence(self):
        # Accumulating, cleared and ignored are the caller keying: there is nothing to say, and
        # saying something would talk over a caller mid-entry.
        for outcome in (outcomes.ACCUMULATING, outcomes.CLEARED, outcomes.IGNORED):
            with self.subTest(outcome=outcome):
                self.assertIsNone(sentence_for(outcome))

    def test_no_sentence_carries_a_digit_or_an_attempt_count(self):
        """The rejection tells the caller it was wrong and nothing more.

        Same reasoning as the gate's refusal: an explanation of how many tries are left, or of
        which part was wrong, is a probing oracle for whoever found the phone.
        """
        for outcome, sentence in SENTENCES.items():
            with self.subTest(outcome=outcome):
                self.assertFalse(any(character.isdigit() for character in sentence), sentence)
                for counting_word in ("first", "second", "third", "last", "one", "two", "three"):
                    self.assertNotIn(counting_word, sentence.lower())


class WhatIsLogged(unittest.IsolatedAsyncioTestCase):
    """Every attempt is logged, and carries no digit (issue #36).

    Same reasoning the gate already uses for refusals: a failure is either an attack or a bug, and
    both are worth seeing. The attempt number is what makes a run of them visible.
    """

    async def _submit(self, machine, pin):
        for key in pin:
            outcome = await machine.key(key)
        return outcome

    async def test_a_successful_authentication_is_logged_at_info(self):
        with self.assertLogs("auth", level="INFO") as captured:
            await self._submit(Authenticator(FakeCoreBankingClient()), DEFAULT_PIN)
        self.assertTrue(any(r.levelname == "INFO" for r in captured.records))

    async def test_each_rejection_is_logged_at_warning_with_its_number(self):
        machine = Authenticator(FakeCoreBankingClient())
        with self.assertLogs("auth", level="INFO") as captured:
            await self._submit(machine, "9999")
            await self._submit(machine, "8888")
        warnings = [r for r in captured.records if r.levelname == "WARNING"]
        self.assertEqual(len(warnings), 2)
        # The attempt number is in the record's arguments, which is what a structured log carries.
        self.assertIn(1, warnings[0].args)
        self.assertIn(2, warnings[1].args)

    async def test_no_log_record_anywhere_carries_a_keyed_digit(self):
        """B2 at this module's own surface, over every path that logs.

        Both the rendered message and the raw arguments, because a PIN passed as a lazy formatting
        argument never appears in a rendered message at all -- which is the most likely way this
        would break.
        """
        client = FakeCoreBankingClient()
        with self.assertLogs("auth", level="DEBUG") as captured:
            machine = Authenticator(client)
            for key in _keys("9", "*", "8", "8", "8", "8"):
                await machine.key(key)
            for key in DEFAULT_PIN:
                await machine.key(key)
            client.fail_with = CoreBankingUnavailable("down")
            unavailable = Authenticator(client)
            for key in DEFAULT_PIN:
                await unavailable.key(key)
        for record in captured.records:
            with self.subTest(message=record.msg):
                for secret in (DEFAULT_PIN, "8888", "9"):
                    self.assertNotIn(secret, record.getMessage())
                    self.assertNotIn(secret, repr(record.args))


class OneCallCannotSeeAnother(unittest.IsolatedAsyncioTestCase):
    async def test_progress_is_per_instance_with_no_module_level_state(self):
        client = FakeCoreBankingClient()
        first, second = Authenticator(client), Authenticator(client)
        for key in DEFAULT_PIN[:3]:
            await first.key(key)
        # The second call keys one digit. If progress were shared, this would be the fourth.
        self.assertEqual(await second.key(DEFAULT_PIN[3]), outcomes.ACCUMULATING)
        self.assertFalse(first.is_authenticated)
        self.assertFalse(second.is_authenticated)

    async def test_one_call_exhausting_its_attempts_does_not_spend_anothers(self):
        client = FakeCoreBankingClient()
        first, second = Authenticator(client), Authenticator(client)
        for pin in ("9999", "8888", "7777"):
            for key in pin:
                await first.key(key)
        outcome = None
        for key in "9999":
            outcome = await second.key(key)
        self.assertEqual(outcome, outcomes.REJECTED)


class TheMachineIsAgentIndependent(unittest.IsolatedAsyncioTestCase):
    async def test_it_is_never_told_which_agent_the_call_is_on(self):
        """It sees digits, not agents, so the caller can authenticate before or after a handoff.

        Asserted at the constructor and at the entry point, because a machine that took an agent
        would make the moment a caller may authenticate depend on routing they cannot see.
        """
        for function in (Authenticator.__init__, Authenticator.key):
            with self.subTest(function=function.__name__):
                self.assertNotIn("agent", inspect.signature(function).parameters)


if __name__ == "__main__":
    unittest.main()
