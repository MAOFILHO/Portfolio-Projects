"""Issue #26 criterion 2: this service runs without the voice agent installed.

It was true by construction and proved by nothing. `make test` installs both packages into one
shared venv and runs both suites there, so an accidental import of the voice agent's package from
this side would pass every test in the repo and only fail in the container, where the voice agent is
not installed (/code-review, 2026-09-09, spec axis; previously recorded as a known-partial in
PROJECT_STATE.md). Its name is spelled once, below, and split -- see the comment there.

What is asserted here is the structural claim, statically: nothing under `mock-core-banking/`
mentions the voice agent, and nothing in its dependency list pulls it in. That is deliberately not
the same as booting the service in an empty venv -- doing that per test run costs a full install for
a claim that only changes when someone writes an import, which is exactly what this catches.
"""
import pathlib
import tomllib
import unittest

#: Split on purpose: this file scans every `.py` under the deployable, itself included, so spelling
#: the name out here would make the scan find its own assertion and fail forever.
VOICE_AGENT = "azbank" + "_voice_agent"

DEPLOYABLE = pathlib.Path(__file__).resolve().parent.parent


class SharedNothing(unittest.TestCase):
    def test_no_file_in_this_deployable_mentions_the_voice_agent(self):
        offenders = [
            path.relative_to(DEPLOYABLE).as_posix()
            for path in sorted(DEPLOYABLE.rglob("*.py"))
            if VOICE_AGENT in path.read_text()
        ]
        self.assertEqual(offenders, [])

    def test_the_dependency_list_does_not_pull_in_the_voice_agent(self):
        project = tomllib.loads((DEPLOYABLE / "pyproject.toml").read_text())["project"]
        declared = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            declared.extend(extra)
        for requirement in declared:
            with self.subTest(requirement=requirement):
                self.assertNotIn(VOICE_AGENT.replace("_", "-"), requirement)
                self.assertNotIn(VOICE_AGENT, requirement)

    def test_the_image_does_not_install_the_voice_agent(self):
        # The Dockerfile is the other place a dependency can enter: a `pip install` line naming the
        # voice agent would defeat both checks above without touching a .py file or the manifest.
        self.assertNotIn(VOICE_AGENT, (DEPLOYABLE / "Dockerfile").read_text())


if __name__ == "__main__":
    unittest.main()
