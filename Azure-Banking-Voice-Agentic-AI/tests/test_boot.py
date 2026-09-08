"""B3 — the startup guard.

Every branch runs with the live-model reader injected, so the whole guard is exercised with no
cloud dependency, no credentials, and no spend. The one leg not covered here is the real reader's
HTTP and auth path, which this project has never run live -- its response *parsing* is covered
below against the exact shape recorded in docs/phase0/findings.md, "B3 end-to-end check".
"""
import logging
import unittest

from azbank_voice_agent import boot

#: A valid environment. CORE_BANKING_URL joined it in Phase 3 (issue #29): the guard now refuses
#: to start without an address for mock-core-banking, so an env fixture without one is no longer a
#: valid environment.
_ENV = {
    "AOAI_DEPLOYMENT": "gpt-realtime-mini",
    "CORE_BANKING_URL": "http://core-banking.internal:8001",
}


def _reader_returning(pair):
    def reader(deployment_name):
        return pair
    return reader


def _reader_raising(exc):
    def reader(deployment_name):
        raise exc
    return reader


class BootSucceedsOnAnApprovedModel(unittest.TestCase):
    def test_the_active_pin_boots_without_a_warning(self):
        with self.assertLogs(boot.log, level="INFO") as cm:
            live = boot.assert_boot_safety(
                reader=_reader_returning(boot.ACTIVE_REALTIME_MODEL), env=dict(_ENV)
            )
        self.assertEqual(live, boot.ACTIVE_REALTIME_MODEL)
        self.assertFalse(any(r.levelno >= logging.WARNING for r in cm.records))

    def test_the_successor_boots_but_warns_that_it_is_a_migration(self):
        # Allowed, so a migration can be rehearsed -- but never silently.
        with self.assertLogs(boot.log, level="WARNING") as cm:
            live = boot.assert_boot_safety(
                reader=_reader_returning(boot.SUCCESSOR_REALTIME_MODEL), env=dict(_ENV)
            )
        self.assertEqual(live, boot.SUCCESSOR_REALTIME_MODEL)
        self.assertTrue(any("deliberate migration" in line for line in cm.output))


class BootRefusesAnythingElse(unittest.TestCase):
    def test_a_known_name_carrying_an_unapproved_version_is_refused(self):
        # THE case a name-only allowlist would wave through, and the reason B3 is keyed on the
        # pair: same deployment name, different version, different retirement date and rate limit.
        name, _ = boot.ACTIVE_REALTIME_MODEL
        with self.assertRaises(SystemExit) as caught:
            boot.assert_boot_safety(
                reader=_reader_returning((name, "2025-12-15")), env=dict(_ENV)
            )
        self.assertIn("not in the allowlist", str(caught.exception))

    def test_an_unknown_model_name_is_refused(self):
        with self.assertRaises(SystemExit):
            boot.assert_boot_safety(
                reader=_reader_returning(("gpt-4o-realtime-preview", "2024-10-01")),
                env=dict(_ENV),
            )

    def test_an_unreadable_deployment_fails_closed(self):
        # An unverifiable deployment is treated as an unapproved one. It must never fall back to
        # trusting configuration -- that trust is the thing this guard exists to remove.
        with self.assertRaises(SystemExit) as caught:
            boot.assert_boot_safety(
                reader=_reader_raising(RuntimeError("ARM unreachable")), env=dict(_ENV)
            )
        self.assertIn("unverifiable deployment", str(caught.exception))

    def test_a_missing_deployment_pin_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            boot.assert_boot_safety(
                reader=_reader_returning(boot.ACTIVE_REALTIME_MODEL), env={}
            )
        self.assertIn("AOAI_DEPLOYMENT", str(caught.exception))

    def test_an_ambient_sdk_key_is_refused_before_anything_else_is_checked(self):
        # Checked first, and checked even when everything else is valid: an ambient key would let
        # the SDK authenticate as something this project never configured.
        reached = []

        def reader(deployment_name):
            reached.append(deployment_name)
            return boot.ACTIVE_REALTIME_MODEL

        env = dict(_ENV, AZURE_OPENAI_API_KEY="sk-whatever")
        with self.assertRaises(SystemExit) as caught:
            boot.assert_boot_safety(reader=reader, env=env)
        self.assertIn(boot.AMBIENT_SDK_KEY_VAR, str(caught.exception))
        self.assertEqual(reached, [])  # refused before the deployment was even read


class AllowlistShape(unittest.TestCase):
    def test_the_allowlist_holds_exactly_the_active_pin_and_one_successor(self):
        # Pinned deliberately: widening B3 must edit this literal and show up in a diff.
        self.assertEqual(
            boot.ALLOWED_REALTIME_MODELS,
            frozenset({("gpt-realtime-mini", "2025-10-06"), ("gpt-realtime-1-5", "2026-02-23")}),
        )
        self.assertEqual(len(boot.ALLOWED_REALTIME_MODELS), 2)

    def test_every_allowlist_entry_is_a_name_and_version_pair(self):
        for entry in boot.ALLOWED_REALTIME_MODELS:
            self.assertEqual(len(entry), 2)
            self.assertTrue(all(isinstance(part, str) and part for part in entry))


class ParsingTheLiveResponse(unittest.TestCase):
    """The real reader's HTTP and auth legs have never been run live. Its parsing has, in the
    sense that this is the exact response shape Phase 0 recorded from the live deployment."""

    def test_it_reads_the_shape_phase_0_recorded_live(self):
        payload = {
            "name": "gpt-realtime-mini",
            "properties": {
                "model": {"format": "OpenAI", "name": "gpt-realtime-mini", "version": "2025-10-06"},
                "provisioningState": "Succeeded",
                "versionUpgradeOption": "NoAutoUpgrade",
            },
            "sku": {"name": "GlobalStandard", "capacity": 1},
        }
        self.assertEqual(
            boot.parse_deployment_response(payload), ("gpt-realtime-mini", "2025-10-06")
        )

    def test_a_response_missing_the_model_block_raises_rather_than_returning_a_partial(self):
        # Feeds straight into the fail-closed path in assert_boot_safety: better to refuse than to
        # compare against a half-populated tuple.
        with self.assertRaises(ValueError):
            boot.parse_deployment_response({"name": "gpt-realtime-mini", "properties": {}})

    def test_a_response_missing_only_the_version_raises(self):
        with self.assertRaises(ValueError):
            boot.parse_deployment_response(
                {"properties": {"model": {"name": "gpt-realtime-mini"}}}
            )


class BootRefusesAnUnconfiguredCoreBanking(unittest.TestCase):
    """Issue #29. A misconfigured deployment should die at startup, where a health check catches it
    and the revision never takes traffic -- not mid-call, in front of a caller, on the first tool
    call of the day. Same fail-closed reasoning as the model pin: no defaults, ever."""

    def test_a_missing_core_banking_url_is_refused(self):
        env = {k: v for k, v in _ENV.items() if k != "CORE_BANKING_URL"}
        with self.assertRaises(SystemExit) as caught:
            boot.assert_boot_safety(
                reader=_reader_returning(boot.ACTIVE_REALTIME_MODEL), env=env
            )
        self.assertIn("CORE_BANKING_URL", str(caught.exception))

    def test_an_empty_core_banking_url_is_refused(self):
        # An empty string is not a configured value -- it is the shape a misconfigured deployment
        # actually takes when a template renders a variable that was never set.
        with self.assertRaises(SystemExit):
            boot.assert_boot_safety(
                reader=_reader_returning(boot.ACTIVE_REALTIME_MODEL),
                env={**_ENV, "CORE_BANKING_URL": ""},
            )

    def test_the_url_is_returned_when_configured(self):
        self.assertEqual(
            boot.core_banking_url(env=dict(_ENV)), "http://core-banking.internal:8001"
        )

    def test_it_fails_at_startup_not_per_tool_call(self):
        # The distinction that matters: this is a SystemExit out of the boot guard, so the process
        # never starts, rather than something a tool call discovers later.
        env = {k: v for k, v in _ENV.items() if k != "CORE_BANKING_URL"}
        with self.assertRaises(SystemExit):
            boot.core_banking_url(env=env)


if __name__ == "__main__":
    unittest.main()
