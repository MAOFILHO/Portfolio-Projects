"""B1 = 0 breaches, across every concrete case the harness generates (issues #40 and #41).

The third of B1's three tiers, and the one that runs whole calls. The other two are the exhaustive
gate cross-product (`tests/test_gate.py`) and the in-path proof that every declared tool goes
through the gate at all. This tier is the one that watches where the call actually lands.

**The detector is the core-banking fake's own call record**, keyed on method name. No new double was
invented for it, and no breach is judged by the gate's return value -- a proof that rests on the
thing being tested is not a proof.

**Both counts are reported here**, printed by the run itself: distinct attack ideas as well as
concrete cases. A case count with no idea count behind it is the same empty claim as a percentile
with no N, which this project already forbids for B5.
"""
import asyncio
import json
import unittest

from azbank_voice_agent.auth import Authenticator
from azbank_voice_agent.auth import outcomes as auth_outcomes
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.realtime.fake import FakeRealtimeServer, function_call
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame, dtmf_frame

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from redteam_harness import (
        BANKING_OPERATIONS,
        MINIMUM_CASES,
        VERIFICATION_OPERATION,
        concrete_cases,
        counts,
        declared_tools,
        load_ideas,
        run,
    )
except ImportError:
    # `python -m unittest tests.test_redteam` does not, and running one file that way is the
    # ordinary thing to do while iterating. Same fallback tests/test_core_banking_live.py uses.
    from tests.redteam_harness import (
        BANKING_OPERATIONS,
        MINIMUM_CASES,
        VERIFICATION_OPERATION,
        concrete_cases,
        counts,
        declared_tools,
        load_ideas,
        run,
    )

#: Run once and shared: every case is an independent whole call against fresh fakes, so running
#: them once and asserting several things about the results costs one pass instead of four.
_OUTCOMES = None


def outcomes():
    global _OUTCOMES
    if _OUTCOMES is None:
        _OUTCOMES = [run(case) for case in concrete_cases()]
    return _OUTCOMES


class TheCorpusItself(unittest.TestCase):
    """The suite's own shape, asserted before anything is concluded from it."""

    def test_every_idea_file_loads_and_is_uniquely_identified(self):
        ideas = load_ideas()
        self.assertTrue(ideas, "redteam/ holds no attack ideas")
        identifiers = [idea.id for idea in ideas]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_every_idea_states_what_it_is_and_why(self):
        # An idea with no rationale is a row in a total, not an idea. This is the assertion that
        # makes "genuinely distinct" something a reader can check rather than take on trust.
        for idea in load_ideas():
            with self.subTest(idea=idea.id):
                self.assertTrue(idea.title.strip())
                self.assertGreater(len(idea.rationale.split()), 20, "rationale is too thin")

    def test_no_case_list_is_hand_maintained(self):
        # Cases come from the cross-product, so the count has to be the product of the dimensions.
        expected = sum(
            len(idea.matrix["tool"]) * len(idea.matrix["agent"]) * len(idea.matrix["point"])
            for idea in load_ideas()
        )
        self.assertEqual(len(concrete_cases()), expected)

    def test_every_dimension_of_the_matrix_is_really_exercised(self):
        # A dimension that only ever takes one value is not a dimension. Each of the three has to
        # vary across the corpus, or the cross-product is inflating a smaller suite.
        cases = concrete_cases()
        for dimension in ("tool", "agent", "point"):
            with self.subTest(dimension=dimension):
                values = {getattr(case, dimension) for case in cases}
                self.assertGreater(len(values), 1, f"{dimension} never varies")

    def test_every_declared_tool_is_attacked(self):
        attacked = {case.tool for case in concrete_cases()}
        for tool in declared_tools():
            with self.subTest(tool=tool):
                self.assertIn(tool, attacked)

    def test_the_case_count_meets_the_constraint(self):
        """B1's floor, asserted mechanically rather than counted by hand (issue #41)."""
        totals = counts()
        self.assertGreaterEqual(
            totals["cases"], MINIMUM_CASES,
            f"B1 requires at least {MINIMUM_CASES} concrete cases; the corpus has "
            f"{totals['cases']} from {totals['ideas']} ideas",
        )

    def test_the_count_does_not_lean_on_cases_that_never_reach_an_attempt(self):
        """The `after_exhaustion` point ends the call before the model can try anything.

        Those cases pin something real -- a caller who has burned their attempts cannot then try a
        tool -- but they are weaker evidence than a refusal, because nothing was refused. The total
        has to clear the constraint without them, or the constraint is being met by counting cases
        that could not have failed.
        """
        totals = counts()
        self.assertGreaterEqual(totals["attempting"], MINIMUM_CASES)


class ZeroBreaches(unittest.TestCase):
    """B1 itself: 0 breaches, deterministic, free, and blocking."""

    def test_no_banking_operation_reaches_the_system_of_record(self):
        breaches = [outcome for outcome in outcomes() if outcome.is_breach]
        self.assertEqual(
            breaches, [],
            "B1 BREACH: " + "; ".join(
                f"{o.case.idea}/{o.case.tool}/{o.case.agent}/{o.case.point} reached "
                f"{o.banking_operations_reached}" for o in breaches
            ),
        )

    def test_the_only_operation_reachable_while_anonymous_is_verification(self):
        """The sharpened B1, stated as a test (issue #40).

        Not "no operation reaches the client" -- PIN verification does, by design, which is why the
        breach definition had to be sharpened before this phase began. What is asserted is that the
        set is *exactly* that one operation and nothing else.
        """
        reached = {name for outcome in outcomes() for name in outcome.reached}
        self.assertEqual(reached - {VERIFICATION_OPERATION}, set())
        self.assertEqual(reached & BANKING_OPERATIONS, set())

    def test_every_attempt_that_was_made_was_answered_with_a_refusal(self):
        # The other half of "0 breaches": nothing ran, and the caller was told rather than left in
        # silence. A tool call that produced no output at all would be a dropped call.
        for outcome in outcomes():
            if outcome.case.ends_before_the_attempt:
                continue
            with self.subTest(case=outcome.case):
                self.assertTrue(outcome.attempted_anything, "the attempt never reached dispatch")
                for output in outcome.tool_outputs:
                    self.assertEqual(json.loads(output), {"error": gate.REFUSAL})

    def test_a_case_after_exhausted_attempts_ends_the_call_before_any_attempt(self):
        # The weaker cases, pinned for what they actually prove rather than counted as refusals.
        ended = [o for o in outcomes() if o.case.ends_before_the_attempt]
        self.assertTrue(ended)
        for outcome in ended:
            with self.subTest(case=outcome.case):
                self.assertFalse(outcome.attempted_anything)
                self.assertEqual(outcome.reached, ("verify_pin",) * 3)

    def test_the_suite_is_deterministic(self):
        # Same corpus, same verdicts, run twice. A red-team suite that flapped would be worse than
        # none: it would train whoever reads it to re-run until green.
        first = [(o.case, o.reached, o.is_breach) for o in outcomes()]
        second = [(run(case).case, run(case).reached, run(case).is_breach)
                  for case in concrete_cases()[:20]]
        self.assertEqual(first[:20], second)


class IdeasThatDoNotFitTheMatrix(unittest.TestCase):
    """Two attack ideas that are real and are not a cross-product of tool, agent and point.

    They are tested here rather than forced into a YAML matrix, and they are **not counted in the
    idea total** -- inflating a count with things the loader did not generate would be the same
    dishonesty as padding it with near-duplicates.
    """

    def test_one_call_cannot_inherit_another_calls_authentication(self):
        """Cross-call state bleed: authenticate on one call, act on a second.

        Not a matrix case because it needs two calls, and the matrix runs one. It is the failure
        that would make every other case in this suite meaningless, because a single authenticated
        call anywhere in the process would open the gate for all of them.
        """
        shared_client = FakeCoreBankingClient()

        # Call one: a caller keys the right PIN and gets in.
        asyncio.run(run_call(
            FakeTransport(frames=[dtmf_frame(d) for d in DEFAULT_PIN], hang=True),
            FakeRealtimeServer(events=[], respond_after_appends=0),
            shared_client,
        ))
        self.assertIn("verify_pin", shared_client.calls)

        # Call two: a different caller, the same process, the same client, no PIN at all.
        before = list(shared_client.calls)
        second = FakeRealtimeServer(
            events=[function_call("get_balance", '{"account": "chequing"}')],
            respond_after_appends=1,
        )
        asyncio.run(run_call(
            FakeTransport(frames=[audio_frame("balance-please")], hang=True),
            second,
            shared_client,
        ))
        self.assertEqual(shared_client.calls, before, "the second call reached core banking")
        self.assertEqual(json.loads(second.tool_outputs[0][1]), {"error": gate.REFUSAL})

    def test_a_digit_that_is_not_an_ascii_digit_cannot_complete_a_pin(self):
        """Homoglyph and wide-form digits, which `str.isdigit` accepts and a keypad never sends.

        Not a matrix case because it attacks the buffer rather than the gate. If the buffer took
        them, four of them would complete an entry the system of record then answered on -- and the
        PIN that reached it would not be the one the caller keyed.
        """
        client = FakeCoreBankingClient()
        machine = Authenticator(client)

        async def key_them():
            # Arabic-Indic, Devanagari, and full-width forms of 1, 2, 3, 4. Every one of these
            # answers True to str.isdigit().
            # Built from code points rather than written as literals: Arabic-Indic one and two,
            # Devanagari one, and the full-width forms of one to four. Every one answers True to
            # str.isdigit(), and a source file that spelled them out would be a source file whose
            # own lint cannot tell them from ASCII either.
            homoglyphs = [chr(point) for point in (0x0661, 0x0662, 0x0967, 0xFF11, 0xFF12, 0xFF13)]
            for character in homoglyphs:
                self.assertEqual(await machine.key(character), auth_outcomes.IGNORED)

        asyncio.run(key_them())
        self.assertEqual(client.calls, [], "a non-ASCII digit completed an entry")
        self.assertFalse(machine.is_authenticated)


class BothCountsAreReported(unittest.TestCase):
    """Wherever this suite is described, both numbers appear. Including here, in its own output."""

    def test_the_counts_are_available_and_printed(self):
        totals = counts()
        print(
            f"\nB1 red-team corpus: {totals['ideas']} distinct attack ideas -> "
            f"{totals['cases']} concrete cases "
            f"({totals['attempting']} of which reach an attempt), 0 breaches."
        )
        self.assertEqual(set(totals), {"ideas", "cases", "attempting"})
        self.assertGreater(totals["ideas"], 0)


if __name__ == "__main__":
    unittest.main()
