"""The latency probe's signature guard, and nothing else about the probe (issue #54).

`scripts/b5_probe.py` is an ops tool. It synthesizes audio with macOS `say`, opens a real realtime
connection and dials nothing -- none of which belongs in L1, which is "deterministic, every pull
request, zero cloud dependency". So this file does not test the probe; it tests **the one thing
whose absence cost two phases**.

Phase 3 gave `run_call` a third required parameter. The probe went on passing two, raised
`TypeError` before it opened a connection, and stayed broken through Phase 4 -- because an ops tool
has no test and nobody ran it. The first anybody would have learned of it is an operator trying to
produce the figure B5 freezes on.

**The guard is a deliberate assertion about shape rather than behaviour**, which this project
otherwise avoids. It is one of exactly two: the other is B2's leak detector, which leaks on purpose
to prove it fires. Both exist for the same reason -- a check that silently stopped checking would
pass forever.
"""
import importlib.util
import inspect
import pathlib
import sys
import unittest

_PROBE = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "b5_probe.py"


def _load_probe():
    """Import the probe as a module, without running it.

    Importing is safe: everything that reads the environment or touches the network lives inside a
    function or under `if __name__ == "__main__"`. `sys.path` already carries the voice-agent
    package, because the suite runs with it installed.
    """
    spec = importlib.util.spec_from_file_location("b5_probe_under_test", _PROBE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TheProbeMatchesTheRelayItDrives(unittest.TestCase):
    def setUp(self):
        self.probe = _load_probe()
        self.addCleanup(sys.modules.pop, "b5_probe_under_test", None)

    def test_the_guard_passes_against_the_real_run_call(self):
        # The probe is not broken right now, which is the thing Phase 3 and Phase 4 could not have
        # said about themselves.
        self.probe.assert_probe_matches_run_call()

    def test_the_guard_fails_when_a_parameter_is_inserted(self):
        """The half that matters: it has to fail, or it is decoration.

        A parameter inserted before the ones the probe passes is the exact shape of what happened in
        Phase 3 -- the probe's positional arguments silently start meaning something else.
        """
        def drifted(transport, realtime, something_new, core_banking, call_records):
            pass

        with self.patched(drifted), self.assertRaises(SystemExit):
            self.probe.assert_probe_matches_run_call()

    def test_the_guard_fails_when_a_required_parameter_is_appended(self):
        # Phase 3's actual failure mode: a new required argument on the end, which a caller passing
        # the old ones does not supply. Positionally the prefix still matches, so this needs the
        # second check rather than the first.
        def drifted(transport, realtime, core_banking, call_records, something_required):
            pass

        with self.patched(drifted), self.assertRaises(SystemExit):
            self.probe.assert_probe_matches_run_call()

    def test_the_guard_tolerates_a_new_optional_parameter(self):
        # Not every change is a break. A parameter with a default is one the probe can keep not
        # passing, and a guard that failed on those would be turned off within a phase.
        def widened(transport, realtime, core_banking, call_records, correlation_id=None):
            pass

        with self.patched(widened):
            self.probe.assert_probe_matches_run_call()

    def test_the_guard_names_both_signatures_when_it_fails(self):
        # An operator reading this message has to be able to fix the probe from it. "Out of date"
        # with no shapes in it would send them to read two files.
        def drifted(transport, realtime, something_new, core_banking, call_records):
            pass

        with self.patched(drifted):
            with self.assertRaises(SystemExit) as caught:
                self.probe.assert_probe_matches_run_call()
        message = str(caught.exception)
        self.assertIn("this probe passes", message)
        self.assertIn("run_call now takes", message)

    def patched(self, replacement):
        from unittest.mock import patch
        return patch.object(self.probe, "run_call", replacement)


class TheProbeMeasuresTheRightThing(unittest.TestCase):
    """Two properties that make the frozen figure mean what the plan says it means.

    Asserted on the probe's source and signature rather than by running it: running it needs a live
    deployment and a spawned service, which is what keeps it out of L1 in the first place.
    """

    def setUp(self):
        self.probe = _load_probe()
        self.addCleanup(sys.modules.pop, "b5_probe_under_test", None)

    def test_it_keys_a_pin(self):
        # Without this the gate refuses every tool call and the probe re-measures Phase 2's
        # refusals under a new name.
        self.assertIn("keys", inspect.signature(self.probe._SyntheticTransport.__init__).parameters)
        self.assertIn("DtmfData", _PROBE.read_text())

    def test_it_takes_a_real_core_banking_address(self):
        self.assertIn("HttpCoreBankingClient", _PROBE.read_text())

    def test_it_refuses_to_run_without_one(self):
        # Refused rather than defaulted, for the reason the boot guard refuses an unconfigured
        # backend: a probe pointed at nothing reports a p95 for a system in which every tool call
        # failed, which looks like a measurement and is not one.
        self.assertIn("--core-banking-url", _PROBE.read_text())
        self.assertIn("is required", _PROBE.read_text())

    def test_it_prints_its_own_n(self):
        # Every percentile this project quotes states the turn count behind it. A probe that made
        # the operator count log lines would be inviting the figure to be reported without one.
        self.assertIn("B5 probe pool", _PROBE.read_text())

    def test_it_says_the_two_pools_are_never_merged(self):
        self.assertIn("SEPARATE from the real-call", _PROBE.read_text())


if __name__ == "__main__":
    unittest.main()
