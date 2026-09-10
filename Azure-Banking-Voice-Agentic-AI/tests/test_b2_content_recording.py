"""B2's fourth surface, asserted the only way it can honestly be asserted today.

`docs/phase4/exit-check.md` criterion 10 reports B2's OTel span-attribute surface as **uncovered
rather than met**, because this project emits no spans. That is still true and this file does not
change it. What it does is turn one part of that surface from "nothing to check" into something
checkable, which the research in `docs/phase4/research-carried-findings.md` §3 made possible by
establishing what the surface will actually be.

**Three independent reasons the surface is empty, each separately checkable** (§3d, §3e):

1. Nothing emits spans at all yet. Phase 6's work.
2. **The realtime WebSocket path is uninstrumented by everything off the shelf.** The OpenTelemetry
   OpenAI instrumentation wraps exactly five call sites -- chat completions, embeddings, responses --
   and none of them is the realtime connection. The Azure Monitor distro's auto-instrumented library
   list contains no GenAI library at all. Adding either in Phase 6 produces spans for FastAPI, httpx
   and the Azure SDK, and **zero `gen_ai.*` attributes**. Any such attribute in this project would
   have to be written by this project.
3. **Both content-recording switches default to off**, and neither is set here. That is what this
   file asserts.

**This is a negative assertion, and it is deliberately the cheap one.** It costs no spans, no
deployment and no cloud call, and it fails the day somebody turns content recording on without
reading B2 -- which is exactly the day it needs to fail. It is not a claim that the surface is
covered; it is a claim that the surface is not being filled.

**Why the switch matters more than it looks.** Azure's own realtime SDK for a neighbouring service
shipped a fix for emitting transcripts and function-call arguments *unconditionally*, ignoring this
very opt-in (§3e). The failure mode is real and has already happened once in shipped Azure code.
"""
import pathlib
import unittest

#: The two environment variables that turn GenAI content capture on. Names and defaults confirmed
#: against primary sources 2026-09-10 (`docs/phase4/research-carried-findings.md` §3d): the
#: OpenTelemetry one is read with a hard-coded `"false"` default in the Python implementation, and
#: Azure's is documented as defaulting to `false`. Azure is migrating to the OTel name and keeps its
#: own as a fallback, so **both** have to stay unset, not either one.
CONTENT_RECORDING_SWITCHES = (
    "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT",
    "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED",
)

#: A third way content leaves the process, and the one a span scanner could never see: the
#: completion hook uploads prompts and completions to a filesystem or object store, so the content
#: is not on the span at all -- only a reference is.
CONTENT_UPLOAD_SWITCHES = (
    "OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK",
    "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH",
)

PROJECT = pathlib.Path(__file__).resolve().parent.parent

#: Where this project says what runs and with what environment. Deliberately **not** `docs/` or
#: `tests/`: naming a variable in order to forbid it is not setting it, and a rule that could not
#: tell those apart would forbid its own explanation.
CONFIGURING_PATHS = (
    "voice-agent",
    "mock-core-banking",
    "infra",
    "scripts",
)

#: Suffixes worth reading in those trees. Source, container definitions, infrastructure.
CONFIGURING_SUFFIXES = {".py", ".bicep", ".json", ".yaml", ".yml", ".sh", ".toml", ""}


def _configuring_files():
    """Every file that could put a variable into a running container's environment."""
    for directory in CONFIGURING_PATHS:
        root = PROJECT / directory
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".venv", "__pycache__", ".mypy_cache"} for part in path.parts):
                continue
            if path.suffix in CONFIGURING_SUFFIXES or path.name.startswith("Dockerfile"):
                yield path


class NoContentRecordingIsConfiguredAnywhere(unittest.TestCase):
    """Neither switch is set by anything that defines what this project deploys."""

    def test_the_files_this_reads_actually_exist(self):
        # A scan over an empty file list passes every assertion below and proves nothing -- the
        # same trap `docs/phase4/findings.md` records for B2's run-wide scan.
        files = list(_configuring_files())
        self.assertGreater(len(files), 10, "the configuring-file scan found almost nothing")
        names = {path.name for path in files}
        self.assertIn("Dockerfile", names, "the container definitions were not scanned")
        self.assertIn("session.py", names, "the relay was not scanned")

    def _switches_found(self, switches):
        """Where any of `switches` appears, as (path, switch) pairs.

        **Membership is tested here rather than with `assertNotIn`** so that a failure names the
        file and the switch and nothing else. `assertNotIn` renders the container it searched, which
        for a file scan means printing the whole file into the test output -- in a suite whose
        entire purpose is to keep specific strings out of specific places, a detector that dumps
        source on failure is the wrong shape of detector.
        """
        return [
            (str(path.relative_to(PROJECT)), switch)
            for path in _configuring_files()
            for switch in switches
            if switch in path.read_text(errors="replace")
        ]

    def test_no_content_recording_switch_is_set(self):
        found = self._switches_found(CONTENT_RECORDING_SWITCHES)
        if found:
            self.fail(
                "GenAI content recording is configured: "
                + "; ".join(f"{switch} in {path}" for path, switch in found)
                + ". If deliberate, B2 gains a surface nothing in this project scans yet -- see "
                "docs/phase4/research-carried-findings.md section 3."
            )

    def test_no_content_upload_hook_is_configured(self):
        # The upload hook is worse than the span attribute, not better: the content leaves the
        # process entirely and a span scanner sees only a reference to it.
        found = self._switches_found(CONTENT_UPLOAD_SWITCHES)
        if found:
            self.fail(
                "GenAI content upload is configured, which puts content outside every scanner "
                "this project has: "
                + "; ".join(f"{switch} in {path}" for path, switch in found)
            )


class NoSpansAreEmittedYet(unittest.TestCase):
    """The reason criterion 10 reports this surface as uncovered rather than met.

    Kept as a test rather than a sentence in a document so that the day it stops being true is the
    day something goes red, rather than the day somebody notices the document is stale. When Phase 6
    makes this fail, that is the signal to build the scanner the constraint actually needs -- by
    `gen_ai.*` prefix and by value, never by a fixed list of attribute names, because the older
    `gen_ai.prompt` and `gen_ai.completion` names are already gone from the spec.
    """

    def test_nothing_in_the_deployables_imports_opentelemetry(self):
        importers = []
        for path in _configuring_files():
            if path.suffix != ".py":
                continue
            body = path.read_text(errors="replace")
            if "import opentelemetry" in body or "from opentelemetry" in body:
                importers.append(str(path.relative_to(PROJECT)))
        self.assertEqual(
            importers, [],
            "this project now emits spans, so B2's fourth surface is real: it needs a scanner over "
            "the gen_ai.* namespace, and this test needs replacing rather than deleting.",
        )


if __name__ == "__main__":
    unittest.main()
