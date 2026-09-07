"""The B3 static check is a CI gate, so it gets tested like one.

A checker that silently passes everything is worse than no checker: it reads green in CI and
enforces nothing. These cases prove it actually detects, and that it reads its allowlist from the
guard rather than carrying a stale copy.
"""
import pathlib
import subprocess
import sys
import unittest

from azbank_voice_agent import boot

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_b3_allowlist.py"


def _run_checker():
    return subprocess.run(
        [sys.executable, str(CHECKER)], capture_output=True, text=True, cwd=REPO_ROOT
    )


class TheCheckerPassesOnTheRealTree(unittest.TestCase):
    def test_the_package_as_committed_is_clean(self):
        result = _run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TheCheckerActuallyDetects(unittest.TestCase):
    """Writes a disallowed model name into the package, runs the checker, and always restores the
    file -- if this test can't fail the checker, the checker isn't a gate."""

    TARGET = REPO_ROOT / "voice-agent" / "azbank_voice_agent" / "agents" / "specs.py"

    def setUp(self):
        self._original = self.TARGET.read_text()
        self.addCleanup(self.TARGET.write_text, self._original)

    def test_a_disallowed_model_name_fails_the_check(self):
        self.TARGET.write_text(self._original + '\nBAD = "gpt-4o-realtime-preview"\n')
        result = _run_checker()
        self.assertEqual(result.returncode, 1)
        self.assertIn("gpt-4o-realtime-preview", result.stdout)

    def test_an_allowlisted_model_name_passes(self):
        allowed_name = boot.ACTIVE_REALTIME_MODEL[0]
        self.TARGET.write_text(self._original + f'\nFINE = "{allowed_name}"\n')
        result = _run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_an_allowed_name_carrying_a_rejected_version_fails_the_check(self):
        # THE case a name-only allowlist waves through: R-01's own finding (one model name,
        # multiple live versions, different retirement dates) -- see check_b3_allowlist.py's
        # module docstring, "check 2".
        allowed_name = boot.ACTIVE_REALTIME_MODEL[0]
        self.TARGET.write_text(self._original + f'\nBAD = ("{allowed_name}", "2025-12-15")\n')
        result = _run_checker()
        self.assertEqual(result.returncode, 1)
        self.assertIn("unapproved version", result.stdout)

    def test_an_allowed_pair_written_as_a_literal_tuple_passes(self):
        name, version = boot.ACTIVE_REALTIME_MODEL
        self.TARGET.write_text(self._original + f'\nFINE = ("{name}", "{version}")\n')
        result = _run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TheCheckerCoversTheWizardScripts(unittest.TestCase):
    """The provisioning script is the one place outside the package that can actually name a
    model for `az ... deployment create` -- found unscanned by /code-review of Phase 2,
    2026-09-07. Same always-restore discipline as TheCheckerActuallyDetects."""

    TARGET = REPO_ROOT / "docs" / "phase0" / "wizard" / "01-provision.sh"

    def setUp(self):
        self._original = self.TARGET.read_text()
        self.addCleanup(self.TARGET.write_text, self._original)

    def test_a_disallowed_model_name_in_the_wizard_script_fails_the_check(self):
        self.TARGET.write_text(self._original + '\nBAD="gpt-4o-realtime-preview"\n')
        result = _run_checker()
        self.assertEqual(result.returncode, 1)
        self.assertIn("gpt-4o-realtime-preview", result.stdout)
        self.assertIn("01-provision.sh", result.stdout)


class TheCheckerReadsTheRealAllowlist(unittest.TestCase):
    def test_its_allowed_names_come_from_the_boot_guard(self):
        # Not a restated copy: if the guard's allowlist changes, the checker must follow it
        # automatically, or it would keep passing against a list nobody uses any more.
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import check_b3_allowlist

        self.assertEqual(
            check_b3_allowlist.allowed_names(),
            {name for name, _ in boot.ALLOWED_REALTIME_MODELS},
        )

    def test_its_allowed_pairs_come_from_the_boot_guard(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import check_b3_allowlist

        self.assertEqual(
            check_b3_allowlist.allowed_pairs(),
            {(name, version) for name, version in boot.ALLOWED_REALTIME_MODELS},
        )

    def test_the_pattern_recognises_realtime_model_ids(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import check_b3_allowlist

        for model_id in ("gpt-realtime-mini", "gpt-realtime-1-5", "gpt-4o-realtime-preview"):
            with self.subTest(model_id=model_id):
                self.assertTrue(check_b3_allowlist.MODEL_PATTERN.search(f'X = "{model_id}"'))

    def test_the_pair_pattern_recognises_a_literal_name_version_pair(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import check_b3_allowlist

        match = check_b3_allowlist.PAIR_PATTERN.search('X = ("gpt-realtime-mini", "2025-10-06")')
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("gpt-realtime-mini", "2025-10-06"))

    def test_scan_targets_include_the_package_and_the_wizard_scripts(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import check_b3_allowlist

        targets = check_b3_allowlist.scan_targets()
        self.assertTrue(any(p.name == "boot.py" for p in targets))
        self.assertTrue(any(p.name == "01-provision.sh" for p in targets))
        self.assertFalse(any("tests" in p.parts for p in targets))


if __name__ == "__main__":
    unittest.main()
