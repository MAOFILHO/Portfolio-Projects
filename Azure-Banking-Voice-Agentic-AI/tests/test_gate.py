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

    def test_authenticated_has_no_permissions_yet(self):
        # Phase 4 adds the transition into this state and the permissions it unlocks. Until then
        # the state exists but grants nothing -- if this starts passing tools, a phase boundary
        # was crossed without the work that was supposed to come with it.
        for tool in (t["name"] for t in tools.TOOLS):
            self.assertFalse(gate.is_allowed(gate.BANKING_AGENT, gate.AUTHENTICATED, tool))

    def test_triage_agent_is_deny_all_same_as_banking(self):
        # Issue #20 gave the gate a second real identity (a call starts on TRIAGE_AGENT, not
        # BANKING_AGENT -- realtime/session.py). PERMISSIONS being empty already denies both, but
        # this pins that fact for the identity that actually opens every call, not just the one
        # that used to be the only one.
        for tool in (t["name"] for t in tools.TOOLS):
            self.assertFalse(gate.is_allowed(gate.TRIAGE_AGENT, gate.ANONYMOUS, tool))
            self.assertFalse(gate.is_allowed(gate.TRIAGE_AGENT, gate.AUTHENTICATED, tool))

    def test_it_is_pure_same_answer_every_time(self):
        answers = {
            gate.is_allowed(gate.BANKING_AGENT, gate.ANONYMOUS, "get_balance")
            for _ in range(50)
        }
        self.assertEqual(len(answers), 1)

    def test_the_permission_table_is_exactly_what_was_reviewed(self):
        # A pinned table, not a smoke test. Every widening of B1 has to edit this literal, which
        # means it shows up in a diff and cannot be an accident. CLAUDE.md: a diff touching
        # dispatch/gate.py never gets auto-accepted. Empty until Phase 4 adds AUTHENTICATED rows.
        self.assertEqual(gate.PERMISSIONS, {})


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
