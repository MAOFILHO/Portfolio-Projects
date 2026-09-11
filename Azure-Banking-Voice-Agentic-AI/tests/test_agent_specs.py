"""The declarative agent table itself (issue #20), independent of any call.

test_whole_call.py's WholeCallWithMidCallHandoff proves the table drives a real handoff; these
cases prove the table's own shape and helpers, so a broken AgentSpec entry fails here rather than
only showing up as a confusing whole-call assertion.
"""
import unittest

from azbank_voice_agent.agents import specs
from azbank_voice_agent.dispatch import gate
from azbank_voice_agent.dispatch.tools import TOOLS


class TheAgentTableIsDeclarative(unittest.TestCase):
    def test_both_agents_exist_keyed_by_their_gate_identity(self):
        # AgentSpec.identity has to be the same string dispatch/gate.py's PERMISSIONS keys on, or
        # a permission row added there later would key on nothing this table ever produces.
        self.assertEqual(specs.AGENTS[gate.TRIAGE_AGENT].identity, gate.TRIAGE_AGENT)
        self.assertEqual(specs.AGENTS[gate.BANKING_AGENT].identity, gate.BANKING_AGENT)

    def test_triage_has_no_real_banking_tools_only_handoffs(self):
        # Two handoffs since Phase 5's third agent (issue #47), and still no banking tool of its
        # own: authenticating does not change what triage is for, and neither does a second
        # specialist existing.
        declared = sorted(tool["name"] for tool in specs.tools_for(gate.TRIAGE_AGENT))
        self.assertEqual(declared, ["handoff_to_banking", "handoff_to_cards"])

    def test_every_declared_tool_has_a_home_on_some_agent(self):
        """A tool no agent declares is a tool no call can reach (issue #47 generalised this).

        It used to read "banking declares every tool", which was true while banking was the only
        specialist and became the wrong question the moment Cards existed -- `block_card` belongs
        to Cards and to nothing else. What the test is actually for is unchanged: a tool added to
        dispatch/tools.py with no home is unreachable and silent, and this makes that loud.
        """
        homed = set().union(*(spec.tool_names for spec in specs.AGENTS.values()))
        self.assertEqual(homed, {tool["name"] for tool in TOOLS})

    def test_no_specialist_declares_a_handoff_of_its_own(self):
        # Neither specialist can route onward -- not back to triage and not to each other. A model
        # on Cards that decides the caller now wants a balance cannot move the call itself;
        # handoff_target() checks the edge against the calling agent's own handoff_to.
        for identity in (gate.BANKING_AGENT, gate.CARDS_AGENT):
            with self.subTest(agent=identity):
                self.assertEqual(specs.AGENTS[identity].handoff_to, frozenset())

    def test_cards_declares_exactly_one_tool(self):
        self.assertEqual(specs.AGENTS[gate.CARDS_AGENT].tool_names, frozenset({"block_card"}))


class HandoffTargetRecognisesOnlyRealHandoffTools(unittest.TestCase):
    def test_a_real_handoff_tool_resolves_to_its_target(self):
        self.assertEqual(
            specs.handoff_target("handoff_to_banking", gate.TRIAGE_AGENT), gate.BANKING_AGENT
        )

    def test_an_ordinary_banking_tool_is_not_a_handoff(self):
        for name in ("get_balance", "transfer", "list_accounts"):
            with self.subTest(tool=name):
                self.assertIsNone(specs.handoff_target(name, gate.TRIAGE_AGENT))

    def test_a_handoff_shaped_name_to_a_nonexistent_agent_is_not_recognised(self):
        # "handoff_to_" is only meaningful when what follows is a real entry in AGENTS -- a
        # lookalike name (typo, or a model hallucinating an agent) must not be treated as routing.
        self.assertIsNone(specs.handoff_target("handoff_to_nonexistent", gate.TRIAGE_AGENT))

    def test_a_target_the_calling_agent_has_no_declared_edge_to_is_rejected(self):
        # BANKING.handoff_to is empty -- TRIAGE is a real agent, but BANKING has no declared edge
        # to it. Without this check, a hallucinated handoff_to_triage call while on BANKING would
        # still succeed (silently reconfiguring the session, never reaching the gate), making
        # handoff_to purely cosmetic outside tools_for()'s tool-list generation -- found by
        # /code-review of #20, 2026-09-07 (both Standards and Spec axes, independently).
        self.assertIsNone(specs.handoff_target("handoff_to_triage", gate.BANKING_AGENT))

    def test_every_agents_handoff_tool_name_round_trips(self):
        for identity, spec in specs.AGENTS.items():
            for target in spec.handoff_to:
                with self.subTest(identity=identity, target=target):
                    self.assertEqual(
                        specs.handoff_target(specs.handoff_tool_name(target), identity), target
                    )


if __name__ == "__main__":
    unittest.main()
