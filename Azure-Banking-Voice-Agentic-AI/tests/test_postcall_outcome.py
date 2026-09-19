"""Phase 8 D17 -- how a call's raw `end_reason` becomes one of D10's five Call outcomes.

Pure function, no Azure. The mapping is literal D10: only four end reasons resolve to a named
outcome, and everything else -- including a value nobody has invented yet -- is `error`, never left
unclassified (exit criterion 3).
"""
import itertools
import pathlib
import re
import unittest

from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.postcall import outcome

_SESSION_SOURCE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "voice-agent" / "azbank_voice_agent" / "realtime" / "session.py"
)


class TheEnumIsExactlyDTenFiveValues(unittest.TestCase):
    def test_the_five_values(self):
        self.assertEqual(
            outcome.CALL_OUTCOMES,
            frozenset({"authenticated_served", "escalated", "caller_hangup", "closed_path", "error"}),
        )


class EachNamedOutcomeComesFromItsOwnEndReason(unittest.TestCase):
    def test_the_closed_path_is_closed_path(self):
        self.assertEqual(outcome.call_outcome("closed", gate.ANONYMOUS), "closed_path")

    def test_an_escalation_is_escalated_in_either_auth_state(self):
        for state in (gate.ANONYMOUS, gate.AUTHENTICATED):
            self.assertEqual(outcome.call_outcome("escalated", state), "escalated")

    def test_a_hangup_is_caller_hangup_in_either_auth_state(self):
        for state in (gate.ANONYMOUS, gate.AUTHENTICATED):
            self.assertEqual(outcome.call_outcome("caller_hangup", state), "caller_hangup")

    def test_the_model_ending_an_authenticated_call_is_authenticated_served(self):
        self.assertEqual(
            outcome.call_outcome("model_ended", gate.AUTHENTICATED), "authenticated_served"
        )


class EverythingElseIsError(unittest.TestCase):
    def test_the_model_ending_an_anonymous_call_is_error(self):
        # Nobody was served: the caller never authenticated.
        self.assertEqual(outcome.call_outcome("model_ended", gate.ANONYMOUS), "error")

    def test_the_caps_the_timeout_and_exhausted_pin_attempts_are_error(self):
        for reason in ("cost_cap", "timeout", "attempts_exhausted", "error"):
            for state in (gate.ANONYMOUS, gate.AUTHENTICATED):
                self.assertEqual(outcome.call_outcome(reason, state), "error", (reason, state))

    def test_a_value_nobody_has_invented_yet_is_error_not_a_crash(self):
        self.assertEqual(outcome.call_outcome("something_new", gate.AUTHENTICATED), "error")

    def test_a_missing_end_reason_is_error(self):
        self.assertEqual(outcome.call_outcome(None, gate.AUTHENTICATED), "error")


class NoInputEverEscapesTheEnum(unittest.TestCase):
    def test_every_known_reason_in_every_state_lands_in_the_enum(self):
        for reason, state in itertools.product(
            [*sorted(outcome.KNOWN_END_REASONS), "something_new", None],
            (gate.ANONYMOUS, gate.AUTHENTICATED, "anything_else"),
        ):
            self.assertIn(outcome.call_outcome(reason, state), outcome.CALL_OUTCOMES, (reason, state))


class TheMappingKnowsEveryEndReasonTheSessionCanEmit(unittest.TestCase):
    """The drift guard. A new `end_reason` added to session.py would fall to `error` here without
    anyone deciding that -- so it fails until the mapping names it on purpose."""

    def test_every_end_reason_literal_in_session_py_is_a_known_one(self):
        source = _SESSION_SOURCE.read_text()
        emitted = set(re.findall(r'end_reason\s*=\s*"(\w+)"', source))
        emitted |= set(re.findall(r'set_attribute\(\s*"end_reason",\s*"(\w+)"', source))
        self.assertTrue(emitted, "found no end_reason literals -- the regex, not the code, is wrong")
        self.assertEqual(emitted - outcome.KNOWN_END_REASONS, set())


if __name__ == "__main__":
    unittest.main()
