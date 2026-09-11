"""B1 — the auth gate.

Two separate claims, tested separately, because proving one does not prove the other:

  1. The gate denies correctly        -> GateIsAPureDenyAllFunction
  2. The gate is actually in the path -> EveryDeclaredToolIsBehindTheGate

A gate that denies perfectly and is never called protects nothing, and that failure would pass
every test in the first class. The second class is what makes docs/PLAN.md's Phase 2 exit wording
-- "provably in front of every tool, even stub ones" -- a proof rather than an assertion.
"""
import json
import unittest
from unittest.mock import patch

from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.dispatch import gate, tools

#: The permission table exactly as it was reviewed, pinned here rather than imported from the module
#: under test -- a test that read `gate.PERMISSIONS` to check `gate.PERMISSIONS` would pass whatever
#: the table said. Every widening of B1 has to edit this literal, which means it shows up in a diff
#: and cannot be an accident (CLAUDE.md: a diff touching dispatch/gate.py never gets auto-accepted).
EXPECTED_PERMISSIONS = {
    (gate.TRIAGE_AGENT, gate.ANONYMOUS): frozenset(),
    (gate.TRIAGE_AGENT, gate.AUTHENTICATED): frozenset(),
    (gate.BANKING_AGENT, gate.ANONYMOUS): frozenset(),
    (gate.BANKING_AGENT, gate.AUTHENTICATED): frozenset({
        "get_balance", "transfer", "list_accounts", "list_transactions",
    }),
    (gate.CARDS_AGENT, gate.ANONYMOUS): frozenset(),
    (gate.CARDS_AGENT, gate.AUTHENTICATED): frozenset({"block_card"}),
}


class GateIsAPureDenyAllFunction(unittest.TestCase):
    def test_an_unknown_agent_is_refused_everything(self):
        for tool in (t["name"] for t in tools.TOOLS):
            self.assertFalse(gate.is_allowed("no-such-agent", gate.ANONYMOUS, tool))

    def test_an_unknown_auth_state_is_refused_everything(self):
        for tool in (t["name"] for t in tools.TOOLS):
            self.assertFalse(gate.is_allowed(gate.BANKING_AGENT, "no-such-state", tool))

    def test_an_unknown_tool_is_refused_for_a_recognized_agent_and_state(self):
        # A distinct axis from the two tests above: (BANKING_AGENT, ANONYMOUS) is a real,
        # recognized pair (not garbage like "no-such-agent"/"no-such-state") -- refused here
        # because the tool name itself is unrecognized, not because the pair is unrecognized.
        # Renamed from "...even_for_a_permitted_pair" (found stale by /code-review of Phase 2
        # follow-up, 2026-09-07): PERMISSIONS is empty now, so no pair is "permitted" for
        # anything -- the old name implied a precondition this diff removed.
        self.assertFalse(gate.is_allowed(gate.BANKING_AGENT, gate.ANONYMOUS, "drain_account"))

    def test_it_is_pure_same_answer_every_time(self):
        answers = {
            gate.is_allowed(gate.BANKING_AGENT, gate.ANONYMOUS, "get_balance")
            for _ in range(50)
        }
        self.assertEqual(len(answers), 1)

    def test_the_permission_table_is_exactly_what_was_reviewed(self):
        # A pinned table, not a smoke test. Every widening of B1 has to edit this literal, which
        # means it shows up in a diff and cannot be an accident. CLAUDE.md: a diff touching
        # dispatch/gate.py never gets auto-accepted.
        #
        # All six pairs, including the empty ones. is_allowed() treats an absent key and an empty
        # set identically, so writing the empty rows out changes nothing about behaviour -- it
        # makes the table state its own completeness, and it makes this assertion able to catch a
        # row being deleted rather than only a row being widened. Six since Phase 5's third agent
        # (issue #47); the table's job of stating its own completeness is the reason growing it
        # stayed a one-line-per-row edit rather than a redesign.
        self.assertEqual(gate.PERMISSIONS, EXPECTED_PERMISSIONS)


class TheExhaustiveCrossProduct(unittest.TestCase):
    """Every declared tool against every (agent, auth state) pair (issue #38).

    Generated from the declared tool list rather than hand-maintained: a tool added to
    dispatch/tools.py later is covered here the moment it is declared, with no second list to keep
    in sync and no chance of a new tool being permitted by an omission nobody noticed.

    This is the first of B1's three tiers. The other two are the red-team corpus and the spy on the
    core-banking client -- this one proves what the table says, and those prove what actually
    reaches the system of record.
    """

    def _pairs(self):
        return EXPECTED_PERMISSIONS

    def test_every_tool_against_every_pair_is_exactly_the_table(self):
        """Two agents became three without this test changing shape (issue #47).

        It was written against "the one granting row" and is now written against the pinned table
        itself, which is the generalisation the third agent forced. What did not change is what it
        is driven off: the declared tool list, never a hand-maintained one.
        """
        for (agent, auth_state), granted in self._pairs().items():
            for tool in (t["name"] for t in tools.TOOLS):
                with self.subTest(agent=agent, auth_state=auth_state, tool=tool):
                    self.assertEqual(gate.is_allowed(agent, auth_state, tool), tool in granted)

    def test_no_tool_is_reachable_while_a_call_is_anonymous(self):
        # Criterion 2, on every agent that exists. An anonymous caller routed to a specialist is
        # refused everything there, which is what keeps routing from being mistaken for
        # authorization -- and it has to hold for the third agent exactly as it does for the
        # second, or handing a caller to Cards would become a way in.
        for agent in (gate.TRIAGE_AGENT, gate.BANKING_AGENT, gate.CARDS_AGENT):
            for tool in (t["name"] for t in tools.TOOLS):
                with self.subTest(agent=agent, tool=tool):
                    self.assertFalse(gate.is_allowed(agent, gate.ANONYMOUS, tool))

    def test_authenticating_grants_triage_nothing(self):
        # Triage has no banking tools of its own, and authenticating does not change what triage
        # is for. This is the row most likely to be widened by accident later.
        for tool in (t["name"] for t in tools.TOOLS):
            with self.subTest(tool=tool):
                self.assertFalse(gate.is_allowed(gate.TRIAGE_AGENT, gate.AUTHENTICATED, tool))

    def test_the_granting_row_names_no_tool_that_does_not_exist(self):
        """Half of the old both-directions assertion, split so a failure says which half broke.

        A name in the row that no tool declares is dead permission nobody can see is dead. This
        direction is unconditional: there is never a reason for it to hold a name that is not a
        tool.
        """
        declared = {tool["name"] for tool in tools.TOOLS}
        for pair, granted in gate.PERMISSIONS.items():
            with self.subTest(pair=pair):
                self.assertEqual(
                    granted - declared, set(), "a permission row names tools that do not exist"
                )

    def test_every_declared_tool_is_named_in_the_granting_row(self):
        """The other half -- and the one that is a deliberate tripwire, not an invariant.

        A declared tool absent from this row is *refused for everyone, in every state*. That is the
        gate failing closed, which `dispatch/gate.py` calls the whole point, so nothing is broken
        at runtime when it happens -- the tool is simply unreachable and silent.

        This test exists to make that silence loud. Phase 5 added `list_transactions` (#46) and
        `block_card` (#47), and each one turned this red until it was written into the table on
        purpose; `escalate_to_human` (#48) is the third and will do the same.

        **"The granting row" became "any granting row" with the third agent** (#47). The
        generalisation is forced rather than a weakening: `block_card` is granted to Cards and to
        nothing else, so a test demanding every tool appear in banking's row would demand the wrong
        thing.

        What it still refuses to become is a **subset check** (/code-review, 2026-09-10 asked
        whether it should be relaxed to one; it should not). A new banking capability reaching
        callers because a permission was inferred from a tool list is precisely the failure B1
        exists to prevent, and a red build asking "did you mean to grant this?" is the cheapest
        possible place to ask it.
        """
        declared = {tool["name"] for tool in tools.TOOLS}
        granted = set().union(*gate.PERMISSIONS.values())
        self.assertEqual(
            declared - granted, set(),
            "a declared tool is in no permission row, so it is refused for every caller in every "
            "state. If that is deliberate, grant it explicitly or move it out of tools.TOOLS -- "
            "do not weaken this test to a subset check",
        )

    def test_no_handoff_tool_appears_anywhere_in_the_table(self):
        # Handoff stays ungated. Gating it would put a routing decision inside the control and give
        # the gate a second job.
        for permitted in gate.PERMISSIONS.values():
            for name in permitted:
                with self.subTest(tool=name):
                    self.assertFalse(name.startswith("handoff_to_"))


class EveryDeclaredToolIsBehindTheGate(unittest.IsolatedAsyncioTestCase):
    """The in-path proof. Driven off the declared tool list, so a tool added later is covered
    automatically -- there is no second list to keep in sync.

    Async since Phase 3 (issue #28): the dispatcher does network I/O now and so is a coroutine.
    **What these tests assert is unchanged** -- only how they call the dispatcher, and what
    "nothing mutated" is measured against (the injected fake, rather than the deleted in-memory
    module). dispatch/gate.py itself is byte-identical to its pre-Phase-3 state.
    """

    def setUp(self):
        self.core_banking = FakeCoreBankingClient()

    def _arguments_for(self, tool_name):
        return {
            "get_balance": '{"account": "chequing"}',
            "transfer": '{"from_account": "chequing", "to_account": "savings", "amount": 1.0}',
            "list_accounts": "{}",
            "list_transactions": '{"account": "chequing"}',
            "block_card": "{}",
        }[tool_name]

    async def test_no_declared_tool_executes_when_the_gate_says_no(self):
        # Force the gate closed and try every declared tool. Nothing may run, and nothing may
        # mutate. If a tool ever gets a code path that skips the gate, this is what catches it.
        before = dict(self.core_banking.accounts)
        with patch.object(gate, "is_allowed", return_value=False):
            for tool in (t["name"] for t in tools.TOOLS):
                with self.subTest(tool=tool):
                    out = json.loads(await tools.dispatch_tool_call(
                        tool, self._arguments_for(tool), core_banking=self.core_banking
                    ))
                    self.assertEqual(out, {"error": gate.REFUSAL})
        self.assertEqual(self.core_banking.accounts, before)  # no tool mutated anything
        # Stronger than "no mutation": a refused tool never reached core banking at all.
        self.assertEqual(self.core_banking.calls, [])

    async def test_every_declared_tool_is_reachable_when_the_gate_says_yes(self):
        # The mirror image: the gate is the only thing standing in the way, so opening it must
        # let every declared tool through. Without this, a tool could be permanently broken and
        # the test above would still pass.
        with patch.object(gate, "is_allowed", return_value=True):
            for tool in (t["name"] for t in tools.TOOLS):
                with self.subTest(tool=tool):
                    out = json.loads(await tools.dispatch_tool_call(
                        tool, self._arguments_for(tool), core_banking=self.core_banking,
                        # The relay's per-call key (issue #47). `block_card` is the one declared
                        # tool that needs one, and without it the service refuses the request as
                        # malformed -- which would make this test report the gate as the thing in
                        # the way when it was not.
                        idempotency_key="idem_aaaaaaaa",
                    ))
                    self.assertNotIn("error", out)

    async def test_a_refusal_is_logged_at_warning(self):
        with patch.object(gate, "is_allowed", return_value=False), \
             self.assertLogs("dispatch", level="WARNING") as cm:
            await tools.dispatch_tool_call(
                "get_balance", '{"account": "chequing"}', core_banking=self.core_banking
            )
        self.assertTrue(any("gate refused" in line for line in cm.output))

    async def test_a_refusal_does_not_leak_why_it_was_refused(self):
        # The spoken refusal must not tell a caller which state would have worked -- that turns
        # the gate into a probing oracle.
        out = json.loads(await tools.dispatch_tool_call(
            "get_balance", "{}", gate.BANKING_AGENT, "no-such-state",
            core_banking=self.core_banking,
        ))
        self.assertEqual(out, {"error": gate.REFUSAL})
        for leak in ("authenticated", "anonymous", "permission", "auth_state"):
            self.assertNotIn(leak, out["error"].lower())


if __name__ == "__main__":
    unittest.main()
