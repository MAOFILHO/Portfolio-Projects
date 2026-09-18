"""Pure ordering-logic tests for `azbank_deploy.resources` -- the module lifted from the validated
prototype (`infra/PROTOTYPE-deploy-teardown-ordering.html`, throwaway branch
`throwaway/phase7-deploy-teardown-prototype`), now checked against the real 8-resource graph traced
from the actual Bicep modules rather than the prototype's simplified one.
"""
import unittest

from azbank_deploy.resources import (
    ORDER,
    RESOURCES,
    can_deploy,
    can_teardown,
    initial_state,
    legal_deploy_order,
    legal_teardown_order,
)


class FreshBringUp(unittest.TestCase):
    def test_deploys_every_resource_exactly_once(self):
        steps = legal_deploy_order(initial_state())
        self.assertEqual(sorted(steps), sorted(ORDER))
        self.assertEqual(len(steps), len(set(steps)))

    def test_every_step_comes_after_its_own_dependencies(self):
        """The mechanical statement of legality: at the point each resource is deployed, every one
        of its declared deps already appears earlier in the list."""
        steps = legal_deploy_order(initial_state())
        position = {key: i for i, key in enumerate(steps)}
        for key in steps:
            for dep in RESOURCES[key].deps:
                self.assertLess(
                    position[dep], position[key],
                    f"{dep} must deploy before {key}",
                )

    def test_acs_does_not_wait_on_voice_agent(self):
        """The circularity that resolves for free: acs.bicep needs the voice agent's future URL,
        which is computable from container_apps_env alone (deterministic Container Apps FQDN) -- so
        acs must be legally deployable with only container_apps_env up, before voice_agent exists."""
        state = initial_state({"container_apps_env": "deployed"})
        ok, reason = can_deploy(state, "acs")
        self.assertTrue(ok, reason)

    def test_call_records_rbac_waits_on_both_the_bootstrap_and_voice_agent(self):
        """The one circularity that does NOT resolve for free (documented in resources.py's module
        docstring): the real call-records-store.bicep deploy needs the account to already exist
        (the bootstrap workaround) AND the voice agent's principal id."""
        state = initial_state({"call_records_account": "deployed"})
        ok, reason = can_deploy(state, "call_records_rbac")
        self.assertFalse(ok)
        self.assertIn("Voice-agent", reason)

        state["voice_agent"] = "deployed"
        ok, reason = can_deploy(state, "call_records_rbac")
        self.assertTrue(ok, reason)


class TheChickenAndEggAttempt(unittest.TestCase):
    def test_aoai_rbac_is_refused_before_voice_agent_exists(self):
        ok, reason = can_deploy(initial_state(), "aoai")
        self.assertFalse(ok)
        self.assertIn("Voice-agent", reason)

    def test_and_succeeds_once_voice_agent_is_up(self):
        state = initial_state({"container_apps_env": "deployed", "voice_agent": "deployed"})
        ok, reason = can_deploy(state, "aoai")
        self.assertTrue(ok, reason)


class IdempotentReRun(unittest.TestCase):
    def test_a_partial_deploy_resumes_without_touching_what_already_exists(self):
        """The prototype's scenario 3, validated: a first run died after app_insights and
        container_apps_env. Re-running must finish the job and must not re-list either of those."""
        state = initial_state({"app_insights": "deployed", "container_apps_env": "deployed"})
        steps = legal_deploy_order(state)
        self.assertNotIn("app_insights", steps)
        self.assertNotIn("container_apps_env", steps)
        self.assertEqual(sorted(steps), sorted(set(ORDER) - {"app_insights", "container_apps_env"}))

    def test_deploying_an_already_deployed_resource_is_refused_not_silently_skipped(self):
        state = initial_state({"app_insights": "deployed"})
        ok, reason = can_deploy(state, "app_insights")
        self.assertFalse(ok)
        self.assertIn("already deployed", reason)


class TeardownToZero(unittest.TestCase):
    def _fully_deployed(self):
        return initial_state({key: "deployed" for key in ORDER})

    def test_tears_down_every_eligible_resource(self):
        steps = legal_teardown_order(self._fully_deployed())
        self.assertEqual(sorted(steps), sorted(set(ORDER) - {"acs"}))

    def test_acs_is_never_in_the_list(self):
        steps = legal_teardown_order(self._fully_deployed())
        self.assertNotIn("acs", steps)

    def test_acs_is_refused_even_when_nothing_depends_on_it(self):
        """D5's floor: not a side effect of ordering, a hard refusal regardless of state."""
        state = initial_state({"container_apps_env": "deployed", "acs": "deployed"})
        ok, reason = can_teardown(state, "acs")
        self.assertFalse(ok)
        self.assertIn("D5", reason)

    def test_every_step_comes_before_its_own_dependencies_are_torn_down(self):
        steps = legal_teardown_order(self._fully_deployed())
        position = {key: i for i, key in enumerate(steps)}
        for key in steps:
            for dep in RESOURCES[key].deps:
                if dep == "acs":
                    continue
                self.assertLess(
                    position[key], position[dep],
                    f"{key} must tear down before {dep}",
                )


class IllegalTeardownOrder(unittest.TestCase):
    def test_the_environment_is_refused_while_apps_still_live_inside_it(self):
        state = initial_state({
            "container_apps_env": "deployed",
            "mock_core_banking": "deployed",
            "voice_agent": "deployed",
        })
        ok, reason = can_teardown(state, "container_apps_env")
        self.assertFalse(ok)
        self.assertTrue("Mock core-banking" in reason or "Voice-agent" in reason)

    def test_and_succeeds_once_both_apps_are_gone(self):
        state = initial_state({"container_apps_env": "deployed"})
        ok, reason = can_teardown(state, "container_apps_env")
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main()
