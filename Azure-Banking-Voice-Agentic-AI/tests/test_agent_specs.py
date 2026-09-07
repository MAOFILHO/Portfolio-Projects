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

    def test_triage_has_no_real_banking_tools_only_a_handoff(self):
        declared = [tool["name"] for tool in specs.tools_for(gate.TRIAGE_AGENT)]
        self.assertEqual(declared, ["handoff_to_banking"])

    def test_banking_declares_every_tool_dispatch_knows_about(self):
        # Today's only specialist covers the whole declared tool list -- if a new tool is added
        # to dispatch/tools.py without a home in some agent's tool_names, it becomes unreachable
        # from any call. This would fail then, rather than silently.
        declared = {tool["name"] for tool in specs.tools_for(gate.BANKING_AGENT)}
        self.assertEqual(declared, {tool["name"] for tool in TOOLS})

    def test_banking_has_no_handoff_of_its_own(self):
        self.assertEqual(specs.AGENTS[gate.BANKING_AGENT].handoff_to, frozenset())


class HandoffTargetRecognisesOnlyRealHandoffTools(unittest.TestCase):
    def test_a_real_handoff_tool_resolves_to_its_target(self):
        self.assertEqual(specs.handoff_target("handoff_to_banking"), gate.BANKING_AGENT)

    def test_an_ordinary_banking_tool_is_not_a_handoff(self):
        for name in ("get_balance", "transfer", "list_accounts"):
            with self.subTest(tool=name):
                self.assertIsNone(specs.handoff_target(name))

    def test_a_handoff_shaped_name_to_a_nonexistent_agent_is_not_recognised(self):
        # "handoff_to_" is only meaningful when what follows is a real entry in AGENTS -- a
        # lookalike name (typo, or a model hallucinating an agent) must not be treated as routing.
        self.assertIsNone(specs.handoff_target("handoff_to_nonexistent"))

    def test_every_agents_handoff_tool_name_round_trips(self):
        for identity, spec in specs.AGENTS.items():
            for target in spec.handoff_to:
                with self.subTest(identity=identity, target=target):
                    self.assertEqual(specs.handoff_target(specs.handoff_tool_name(target)), target)


if __name__ == "__main__":
    unittest.main()
