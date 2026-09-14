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
import dataclasses
import json
import unittest

from azbank_voice_agent.auth import Authenticator
from azbank_voice_agent.auth import outcomes as auth_outcomes
from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN, FakeCoreBankingClient
from azbank_voice_agent.dispatch import gate, tools
from azbank_voice_agent.realtime.fake import FakeRealtimeServer, function_call
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame, dtmf_frame

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from redteam_harness import (
        BANKING_OPERATIONS,
        ESCALATION_TOOL,
        HOMOGLYPH_DIGITS,
        MINIMUM_CASES,
        VERIFICATION_OPERATION,
        Case,
        arguments_for,
        concrete_cases,
        counts,
        credentials_in_what_the_call_sent,
        declared_tools,
        load_ideas,
        run,
    )
except ImportError:
    # `python -m unittest tests.test_redteam` does not, and running one file that way is the
    # ordinary thing to do while iterating. Same fallback tests/test_core_banking_live.py uses.
    from tests.redteam_harness import (
        BANKING_OPERATIONS,
        ESCALATION_TOOL,
        HOMOGLYPH_DIGITS,
        MINIMUM_CASES,
        VERIFICATION_OPERATION,
        Case,
        arguments_for,
        concrete_cases,
        counts,
        credentials_in_what_the_call_sent,
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

    def test_the_two_ideas_that_used_to_sit_outside_the_matrix_are_generated(self):
        """`redteam/README.md`'s shortfall, closed by widening the loader rather than the list.

        Both ideas were real and were deliberately left uncounted, because inflating a total with
        things the loader did not generate would be the same dishonesty as padding it with
        near-duplicates. They are counted now because they are generated now: one needed a call
        before the call, the other needed keypresses no keypad sends, and the matrix grew a
        dimension for each rather than the corpus growing two special cases.
        """
        generated = {idea.id for idea in load_ideas()}
        for identifier in ("cross-call-authentication-inheritance", "homoglyph-digits-as-a-pin"):
            with self.subTest(idea=identifier):
                self.assertIn(identifier, generated)

    def test_the_new_phase_five_surface_is_attacked_by_ideas_of_its_own(self):
        """Five ideas written for what Phase 5 added, named individually (issue #52).

        Not "the corpus grew", which a wider matrix would also produce. Each of these is a distinct
        *reason* to attack, and the matrices' widening -- which happened in #46 and #47 as the tools
        were declared -- is a different thing that does not count as an idea.
        """
        generated = {idea.id for idea in load_ideas()}
        for identifier in (
            "unauthenticated-card-block",
            "escalation-as-an-attempt-reset",
            "replayed-idempotency-key-across-calls",
            "cost-store-unreachable",
            "forged-confirmation",
        ):
            with self.subTest(idea=identifier):
                self.assertIn(identifier, generated)

    def test_the_idea_count_is_reported_honestly_and_the_shortfall_is_stated(self):
        """**The count is 18 against a target of 20-30, and the gap is still a gap.**

        This test exists to keep that sentence from quietly disappearing. Phase 4 reported 13 and
        said so; Phase 5 added five ideas for the surface it introduced and reports 18. It is not
        padded to 20 with near-duplicates, and this asserts the real number rather than the target
        -- so somebody adding a near-duplicate to reach 20 has to edit this line and read why they
        should not.

        Widening a matrix is not a new idea. `list_transactions` and `block_card` joined nine
        existing matrices and roughly doubled the case count without adding one idea, which is
        exactly why the two numbers are always quoted together.

        One idea named in the spec is **not** here and is not counted: a day's budget exhausted
        *mid-call*. This harness drives `run_call`, which is not where the budget is read -- it is
        read once on the media socket before the relay starts -- so there is no in-call moment for
        the corpus to attack. It is covered by the B4 suite instead, and the honest statement is
        that this corpus cannot express it rather than that it was done.
        """
        self.assertEqual(counts()["ideas"], 18)

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


class TheDetectorItself(unittest.TestCase):
    """The scorer, before anything is concluded from it (/code-review, 2026-09-10).

    `is_breach` is a conjunction, and a conjunction with a term that is always False is not a
    conjunction -- it is the other term wearing a disguise. The corpus below rests entirely on this
    object, so the same rule the module docstring applies to the gate applies here: a detector that
    was never shown to distinguish the two cases has not been shown to detect anything.

    The direction of the old defect mattered and is worth recording: `authenticated` was derived
    from the scripted keypresses, never from the call, so it was False for every case and
    `is_breach` collapsed to "a banking operation was reached". That over-reports rather than
    under-reports -- it could never have passed a breach, only invented one -- which is why this is
    a correctness fix and was not a live B1 hole.
    """

    def test_a_call_that_did_authenticate_is_not_scored_as_a_breach(self):
        # The leg that never ran. A caller who keys the right PIN and then asks for a balance has
        # done nothing wrong, and a detector that called that a breach would be measuring the
        # opposite of B1.
        case = concrete_cases()[0]
        outcome = run(case, keys=tuple(DEFAULT_PIN))
        self.assertTrue(outcome.authenticated, "keying the right PIN did not register")
        self.assertFalse(outcome.is_breach)

    def test_the_authenticated_verdict_is_read_off_the_spy_not_the_script(self):
        # Every point in the matrix leaves the call anonymous, so all of them score False -- but
        # for the right reason: the system of record never returned an accepted verdict, rather
        # than the scripted keys never spelling a PIN the harness recognised.
        for outcome in outcomes():
            with self.subTest(case=outcome.case):
                self.assertFalse(outcome.authenticated)
                self.assertNotIn(True, outcome.verifications)

    def test_an_earlier_callers_authentication_does_not_register_on_this_call(self):
        """`authenticated` means *this* call, not this process.

        The cross-call idea replays an earlier caller's successful entry against the same client,
        which is the whole point of it. A term read off that client's entire history would come
        back True for the case's own call, and `is_breach` would be False for precisely the cases
        that exist to catch a breach -- the /code-review defect again in a new dress, and this time
        pointing the dangerous way: it would under-report rather than over-report.
        """
        case = Case(
            idea="cross-call-authentication-inheritance",
            tool="get_balance",
            agent=gate.TRIAGE_AGENT,
            point="before_entry",
            arguments="valid",
            backend="healthy",
            repeat=1,
            prior_call="authenticated",
        )
        outcome = run(case)

        self.assertTrue(outcome.attempted_anything, "the case never reached an attempt")
        self.assertFalse(outcome.authenticated, "an earlier caller's entry authenticated this call")
        self.assertEqual(outcome.verifications, (), "a prior call's verdict was counted as this one's")
        self.assertNotIn("verify_pin", outcome.reached, "a prior call's operation was counted here")

    def test_a_cleared_entry_costs_no_attempt_and_a_rejection_costs_one(self):
        """Attempt accounting, which `redteam/verification-flooding.yaml` names and nothing scored.

        Its rationale calls out two failures -- a cleared entry costing an attempt, and a rejection
        not costing one -- and until `verifications` existed the harness recorded neither, so the
        idea's cases asserted nothing its neighbours did not already assert.
        """
        by_point = {}
        for outcome in outcomes():
            by_point.setdefault(outcome.case.point, outcome)

        # Three digits then star: the buffer emptied, so the system of record was never asked.
        self.assertEqual(by_point["after_clear"].verifications, ())
        # Two digits and nothing more: an entry that never completed is not an attempt either.
        self.assertEqual(by_point["mid_entry"].verifications, ())
        # One completed check, refused. Exactly one attempt, and it cost one.
        self.assertEqual(by_point["after_wrong_pin"].verifications, (False,))
        # Three refused checks and no fourth: the cap is a cap.
        self.assertEqual(by_point["after_exhaustion"].verifications, (False, False, False))


class _Sent:
    """Anything with a `.sent` list, which is all `credentials_in_what_the_call_sent` reads.

    Module level rather than defined inside each test: it was written out twice, identically
    (/code-review, 2026-09-10). One shape, one definition.
    """

    def __init__(self, sent):
        self.sent = sent


class B2AcrossTheWholeCorpus(unittest.TestCase):
    """B2's transcript surface, on every corpus call rather than on one (/code-review, 2026-09-10).

    The run-wide log scan in `tests/test_zz_b2_leak_scan.py` already covers every record these
    calls emit. What it cannot see is what went *into the model's context* and what came back down
    to the caller, and until now that surface was asserted on a single whole-call test. These are
    the calls that key wrong credentials, three of them per exhausted case, so they are precisely
    where a relay that echoed a keyed digit would show it.
    """

    def test_no_keyed_credential_reaches_the_model_or_the_caller_on_any_case(self):
        leaks = [outcome for outcome in outcomes() if outcome.leaked]
        self.assertEqual(
            leaks, [],
            "B2 breach: " + "; ".join(
                f"{o.case.idea}/{o.case.point} sent {o.leaked}" for o in leaks
            ),
        )

    def test_the_surface_scan_would_notice_a_credential_if_one_were_there(self):
        # The rehearsal, same reasoning as the leak scanner's own. A scan whose serialisation
        # silently produced an empty string would pass the assertion above forever.
        self.assertEqual(
            credentials_in_what_the_call_sent(
                (_Sent([{"text": f"the PIN is {DEFAULT_PIN}"}]), _Sent([]))
            ),
            (DEFAULT_PIN,),
        )
        self.assertEqual(
            credentials_in_what_the_call_sent((_Sent([{"text": "caller authenticated"}]), _Sent([]))),
            (),
        )

    def test_the_scan_reads_every_call_it_is_given_not_only_the_first(self):
        """A case that runs a prior call has two surfaces, and both have to be read.

        The prior call is the only place in the whole corpus where the **accepted** credential is
        keyed into a model context, so a scan that stopped at the case's own call would be blind to
        precisely the call most worth watching -- while `docs/phase4/exit-check.md` claimed
        run-wide coverage across every red-team call. Claiming a surface is covered when it is not
        scanned is criterion 10's own prohibited failure mode (/code-review, 2026-09-10).
        """
        clean = (_Sent([{"text": "nothing here"}]), _Sent([]))
        dirty = (_Sent([{"text": f"the PIN is {DEFAULT_PIN}"}]), _Sent([]))

        self.assertEqual(credentials_in_what_the_call_sent(clean, dirty), (DEFAULT_PIN,))
        self.assertEqual(credentials_in_what_the_call_sent(dirty, clean), (DEFAULT_PIN,))
        self.assertEqual(credentials_in_what_the_call_sent(clean, clean), ())


class TheInjectedArgumentsStrategy(unittest.TestCase):
    """`injected` has to differ from `malformed`, or it is one idea counted twice.

    The payload used to be unterminated JSON, so it died at the dispatcher's parse exactly where a
    `malformed` payload dies, and the field it claimed to smuggle never existed. Note what this
    does and does not prove: the gate is consulted at `dispatch/tools.py` *before* the arguments
    are parsed at all, so on a refused tool no argument shape is ever reached. The strategy only
    discriminates on a tool that is permitted while anonymous, which is why one is aimed there.
    """

    def test_the_payload_parses_for_every_tool_it_is_sent_to(self):
        for tool in declared_tools():
            with self.subTest(tool=tool):
                parsed = json.loads(arguments_for(tool, "injected"))
                self.assertIsInstance(parsed, dict)

    def test_the_payload_really_carries_the_field_it_claims_to_smuggle(self):
        # An injection test whose injected field is absent is theatre about theatre.
        parsed = json.loads(arguments_for("get_balance", "injected"))
        self.assertEqual(parsed.get("auth_state"), gate.AUTHENTICATED)

    def test_the_smuggled_field_changes_nothing_on_the_one_tool_that_is_reachable(self):
        # verify_pin is permitted while anonymous, so this is the only tool where the arguments are
        # ever parsed on an anonymous call. The injected auth_state rides all the way in and the
        # call is still anonymous afterwards, because the gate reads three strings and none of them
        # comes from the model's arguments.
        case = dataclasses.replace(
            concrete_cases()[0], tool=VERIFICATION_OPERATION, arguments="injected",
        )
        outcome = run(case)
        self.assertFalse(outcome.authenticated)
        self.assertFalse(outcome.is_breach)


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

    def test_a_character_no_keypad_sends_never_completes_an_entry(self):
        """The homoglyph idea's own property, which "0 breaches" does not by itself say.

        A refusal looks identical for a call that keyed nothing and a call that keyed six
        characters the buffer threw away, so B1's verdict alone cannot tell those apart. What
        distinguishes them is that the system of record was never asked anything: had the buffer
        taken these, the fourth would have submitted a credential the caller never keyed and could
        not have keyed.
        """
        keyed = [o for o in outcomes() if o.case.point == "after_homoglyph_digits"]
        self.assertTrue(keyed, "the homoglyph idea generated no cases")
        for outcome in keyed:
            with self.subTest(case=outcome.case):
                self.assertEqual(outcome.verifications, (), "an entry completed")
                self.assertNotIn(VERIFICATION_OPERATION, outcome.reached)

    def test_every_banking_attempt_that_was_made_was_answered_with_a_refusal(self):
        """The other half of "0 breaches": nothing ran, and the caller was told.

        A tool call that produced no output at all would be a dropped call, which is why this
        asserts on the output rather than only on what the spy recorded.

        **Escalation is excluded, and that exclusion is the point** (issue #48). It is granted in
        every row, so an attempt on it is not refused -- it is either carried out, which is the
        design, or malformed, because the model invented a reason outside the fixed set. Asserting
        the gate's refusal for it would be asserting the opposite of what was signed off. What
        keeps that from being a hole is the class below: an escalation on an unauthenticated call
        must reach the call-record store and must not reach the core-banking client, and the breach
        detector already watches the second half of that.
        """
        for outcome in outcomes():
            if outcome.case.ends_before_the_attempt or outcome.case.tool == ESCALATION_TOOL:
                continue
            with self.subTest(case=outcome.case):
                self.assertTrue(outcome.attempted_anything, "the attempt never reached dispatch")
                for output in outcome.tool_outputs:
                    self.assertEqual(json.loads(output), {"error": gate.REFUSAL})

    def test_every_escalation_attempt_was_carried_out_or_refused_as_malformed(self):
        """The tool that is granted anonymously, held to what it is actually supposed to do.

        Two outcomes and no third. A well-formed escalation is carried out -- that is the signed-off
        design, and a caller locked out of the PIN check being able to ask for a person is the whole
        reason for it. An escalation carrying a reason the model invented is malformed, which is
        what the handler's re-check of the enum is for.

        **What is never acceptable is a banking operation.** That is asserted at the detector for
        every case in this corpus, escalation included, by ZeroBreaches above.
        """
        seen = set()
        for outcome in outcomes():
            if outcome.case.ends_before_the_attempt or outcome.case.tool != ESCALATION_TOOL:
                continue
            with self.subTest(case=outcome.case):
                for output in outcome.tool_outputs:
                    answer = json.loads(output)
                    if "result" in answer:
                        seen.add("carried out")
                        self.assertEqual(answer["result"], tools.ESCALATED)
                    else:
                        seen.add("malformed")
                        self.assertEqual(answer, {"error": tools.MALFORMED})
        # Both branches really happen, so neither assertion above is vacuous.
        self.assertEqual(seen, {"carried out", "malformed"})

    def test_an_anonymous_escalation_reaches_the_store_and_never_core_banking(self):
        """The precise shape of what the sign-off permitted, stated once (issue #48).

        B1's target does not move because escalation touches nothing that holds money. This is that
        sentence as a test: on a call that never authenticated, a well-formed escalation writes its
        record and the core-banking client sees nothing but the PIN checks the caller made.
        """
        case = dataclasses.replace(
            concrete_cases()[0], tool=ESCALATION_TOOL, arguments="valid",
            agent=gate.TRIAGE_AGENT, point="before_entry",
        )
        outcome = run(case)
        self.assertFalse(outcome.authenticated)
        self.assertEqual(outcome.banking_operations_reached, ())
        self.assertEqual(len(outcome.escalations), 1)

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


class TheSameTwoIdeasAtTheirNarrowestPoint(unittest.TestCase):
    """The mechanism behind two corpus ideas, asserted directly rather than through a whole call.

    Both used to live here *instead* of in `redteam/`, and were deliberately left out of the idea
    total because the loader did not generate them. Both are generated and counted now --
    `cross-call-authentication-inheritance` and `homoglyph-digits-as-a-pin` -- because the matrix
    grew a prior-call dimension and a keypress point rather than the corpus growing two special
    cases. `redteam/README.md` carries the count that changed.

    They stay here because a corpus case watches a call from outside and sees a refusal, and a
    refusal is the same shape however it was arrived at. These two name the mechanism instead: the
    exact payload the second call is answered with, and the authenticator's own verdict on each
    character one at a time. Neither is reachable from a whole call, and neither is counted twice
    -- an idea is what `redteam/` holds, and these are assertions about one.
    """

    def test_one_call_cannot_inherit_another_calls_authentication(self):
        """Cross-call state bleed: authenticate on one call, act on a second.

        The failure that would make every other case in this suite meaningless, because a single
        authenticated call anywhere in the process would open the gate for all of them. The corpus
        runs this across twelve cases; what is added here is the refusal's exact payload and the
        client's untouched call record.
        """
        shared_client = FakeCoreBankingClient()

        # Call one: a caller keys the right PIN and gets in.
        asyncio.run(run_call(
            FakeTransport(frames=[dtmf_frame(d) for d in DEFAULT_PIN], hang=True),
            FakeRealtimeServer(events=[], respond_after_appends=0),
            shared_client,
            FakeCallRecordStore(),
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
            FakeCallRecordStore(),
        ))
        self.assertEqual(shared_client.calls, before, "the second call reached core banking")
        self.assertEqual(json.loads(second.tool_outputs[0][1]), {"error": gate.REFUSAL})

    def test_a_digit_that_is_not_an_ascii_digit_cannot_complete_a_pin(self):
        """Homoglyph and wide-form digits, which `str.isdigit` accepts and a keypad never sends.

        The corpus runs these through six whole calls and can see only that the attempt after them
        was refused. What is added here is the verdict on each character: every one of them is
        IGNORED, which is what "nothing accumulated" actually means. `IGNORED` is the seventh
        outcome `docs/phase4/findings.md` §1 records, and this is where it is pinned.

        The characters come from the harness rather than being written out again -- one list, the
        same discipline `tests/keyed_values.py` exists to enforce for credentials.
        """
        client = FakeCoreBankingClient()
        machine = Authenticator(client)

        async def key_them():
            for character in HOMOGLYPH_DIGITS:
                with self.subTest(code_point=hex(ord(character))):
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
