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
        # All four pairs, including the three empty ones. is_allowed() treats an absent key and an
        # empty set identically, so writing the empty rows out changes nothing about behaviour --
        # it makes the table state its own completeness, and it makes this assertion able to catch
        # a row being deleted rather than only a row being widened.
        self.assertEqual(gate.PERMISSIONS, {
            (gate.TRIAGE_AGENT, gate.ANONYMOUS): frozenset(),
            (gate.TRIAGE_AGENT, gate.AUTHENTICATED): frozenset(),
            (gate.BANKING_AGENT, gate.ANONYMOUS): frozenset(),
            (gate.BANKING_AGENT, gate.AUTHENTICATED): frozenset({
                "get_balance", "transfer", "list_accounts",
            }),
        })


class TheExhaustiveCrossProduct(unittest.TestCase):
    """Every declared tool against every (agent, auth state) pair (issue #38).

    Generated from the declared tool list rather than hand-maintained: a tool added to
    dispatch/tools.py later is covered here the moment it is declared, with no second list to keep
    in sync and no chance of a new tool being permitted by an omission nobody noticed.

    This is the first of B1's three tiers. The other two are the red-team corpus and the spy on the
    core-banking client -- this one proves what the table says, and those prove what actually
    reaches the system of record.
    """

    #: The one pair that grants anything, and exactly what it grants.
    GRANTED = frozenset({"get_balance", "transfer", "list_accounts"})

    def _pairs(self):
        for agent in (gate.TRIAGE_AGENT, gate.BANKING_AGENT):
            for auth_state in (gate.ANONYMOUS, gate.AUTHENTICATED):
                yield agent, auth_state

    def test_every_tool_against_every_pair_is_exactly_the_table(self):
        for agent, auth_state in self._pairs():
            granting = (agent, auth_state) == (gate.BANKING_AGENT, gate.AUTHENTICATED)
            for tool in (t["name"] for t in tools.TOOLS):
                with self.subTest(agent=agent, auth_state=auth_state, tool=tool):
                    self.assertEqual(
                        gate.is_allowed(agent, auth_state, tool),
                        granting and tool in self.GRANTED,
                    )

    def test_no_tool_is_reachable_while_a_call_is_anonymous(self):
        # Criterion 2, on both agents. An anonymous caller routed to banking is refused everything
        # there, which is what keeps routing from being mistaken for authorization.
        for agent in (gate.TRIAGE_AGENT, gate.BANKING_AGENT):
            for tool in (t["name"] for t in tools.TOOLS):
                with self.subTest(agent=agent, tool=tool):
                    self.assertFalse(gate.is_allowed(agent, gate.ANONYMOUS, tool))

    def test_authenticating_grants_triage_nothing(self):
        # Triage has no banking tools of its own, and authenticating does not change what triage
        # is for. This is the row most likely to be widened by accident later.
        for tool in (t["name"] for t in tools.TOOLS):
            with self.subTest(tool=tool):
                self.assertFalse(gate.is_allowed(gate.TRIAGE_AGENT, gate.AUTHENTICATED, tool))

    def test_the_granting_row_covers_every_declared_tool_and_nothing_more(self):
        # The two lists have to agree in both directions: a declared tool missing from the row
        # would be permanently unreachable, and a name in the row that no tool declares would be
        # dead permission nobody could see was dead.
        declared = {tool["name"] for tool in tools.TOOLS}
        self.assertEqual(gate.PERMISSIONS[(gate.BANKING_AGENT, gate.AUTHENTICATED)], declared)

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
                        tool, self._arguments_for(tool), core_banking=self.core_banking
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
