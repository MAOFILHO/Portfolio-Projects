"""B2's fourth surface, asserted the only way it can honestly be asserted today.

`docs/phase4/exit-check.md` criterion 10 reports B2's OTel span-attribute surface as **uncovered
rather than met**, because this project emits no spans. That is still true and this file does not
change it. What it does is turn one part of that surface from "nothing to check" into something
checkable, which the research in `docs/phase4/research-carried-findings.md` §3 made possible by
establishing what the surface will actually be.

**Three independent reasons the surface is empty, each separately checkable** (§3d, §3e):

1. Nothing emits spans at all yet. Phase 6's work.
2. **The realtime path is uninstrumented by everything off the shelf.** The OpenTelemetry
   OpenAI instrumentation wraps exactly five call sites -- chat completions, embeddings, responses --
   and none of them is the realtime session. The Azure Monitor distro's auto-instrumented library
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
import tempfile
import unittest

from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking.fake import FakeCoreBankingClient
from azbank_voice_agent.realtime.fake import FakeRealtimeServer, audio_delta, response_done
from azbank_voice_agent.realtime.session import run_call
from azbank_voice_agent.transport.fake import FakeTransport, audio_frame

try:
    # `make test` runs `unittest discover -s tests`, which puts this directory on sys.path.
    from telemetry_harness import run_traced_call
except ImportError:
    # `python -m unittest tests.test_b2_content_recording` does not. Same fallback
    # tests/test_redteam.py uses for tests/redteam_harness.py.
    from tests.telemetry_harness import run_traced_call

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

#: The **programmatic** half of the same switch, which an environment scan cannot see
#: (/code-review, 2026-09-10). The research note asks for "neither variable is set … **and no code
#: sets the programmatic equivalent**", and the environment rules above answer only the first
#: clause: an Azure SDK call enabling content recording in code would set no variable and import no
#: OpenTelemetry package, so every other rule in this file would still pass.
#:
#: Matched as substrings and case-insensitively, because these are spelled differently across SDKs
#: and languages and the point is to catch the concept rather than one library's parameter name.
CONTENT_RECORDING_IDENTIFIERS = (
    "content_recording",
    "contentrecording",
    "capture_message_content",
    "capture_content",
    "enable_content",
)

#: B2's widened third channel (issue #65): a log record on OpenTelemetry's own **logging** signal,
#: which is a different pipeline from the two above. The switches above gate *GenAI instrumentation*
#: emitting content onto whichever signal it's configured for (span, span event, or log record --
#: `OTEL_SEMCONV_STABILITY_OPT_IN`'s `span_only`/`event_only`/`span_and_event` modes, `docs/phase4/
#: research-carried-findings.md` §3d); this is the separate, structural question of whether an OTel
#: `LoggerProvider` exists in this project *at all*. `observability/telemetry.py` wires a
#: `TracerProvider` and a `MeterProvider` and nothing else -- no `opentelemetry.sdk._logs` import,
#: no `LoggerProvider`, no `LoggingHandler` anywhere in the tree (confirmed by this scan). Matched
#: case-insensitively for the same reason `CONTENT_RECORDING_IDENTIFIERS` is: catch the concept,
#: not one spelling of it.
LOGGING_PIPELINE_IDENTIFIERS = (
    "loggerprovider",
    "logginghandler",
    "opentelemetry.sdk._logs",
    "opentelemetry._logs",
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
    """Neither content-capture switch, the upload hook, nor an OTel logging pipeline is set by
    anything that defines what this project deploys (the third widened by issue #65)."""

    def test_the_files_this_reads_actually_exist(self):
        # A scan over an empty file list passes every assertion below and proves nothing -- the
        # same trap `docs/phase4/findings.md` records for B2's run-wide scan.
        files = list(_configuring_files())
        self.assertGreater(len(files), 10, "the configuring-file scan found almost nothing")
        names = {path.name for path in files}
        self.assertIn("Dockerfile", names, "the container definitions were not scanned")
        self.assertIn("session.py", names, "the relay was not scanned")

    def _switches_found(self, switches, files=None, casefold=False):
        """Where any of `switches` appears, as (path, switch) pairs.

        **Membership is tested here rather than with `assertNotIn`** so that a failure names the
        file and the switch and nothing else. `assertNotIn` renders the container it searched, which
        for a file scan means printing the whole file into the test output -- in a suite whose
        entire purpose is to keep specific strings out of specific places, a detector that dumps
        source on failure is the wrong shape of detector.

        **`files`, overridable** (issue #65) -- defaults to the real `_configuring_files()` scan,
        the same optional-override-for-testability shape `tests/test_zz_b2_leak_scan.py`'s
        `offending_records`/`offending_span_attributes` already use, so the rehearsal below can
        point this at a planted file instead of reimplementing the match logic to test it.
        """
        return [
            (str(path.relative_to(PROJECT)) if path.is_relative_to(PROJECT) else str(path), switch)
            for path in (_configuring_files() if files is None else files)
            for switch in switches
            for body in [path.read_text(errors="replace")]
            for haystack in [body.casefold() if casefold else body]
            if switch in haystack
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

    def test_no_otel_logging_pipeline_is_wired_anywhere(self):
        """B2's widened third channel (issue #65) -- see `LOGGING_PIPELINE_IDENTIFIERS`'s own
        docstring for why this is a different question from the two switches above."""
        found = self._switches_found(LOGGING_PIPELINE_IDENTIFIERS, casefold=True)
        if found:
            self.fail(
                "an OpenTelemetry logging pipeline may be configured, which is a third B2 channel "
                "nothing here scans the content of: "
                + "; ".join(f"{identifier} in {path}" for path, identifier in found)
            )

    def test_the_switch_scan_would_catch_a_planted_one(self):
        """Follows `tests/test_zz_b2_leak_scan.py::TheDetectorItselfWorks`'s own pattern (issue
        #65): a scanner that quietly stopped matching anything would pass every check above
        forever. Proves `_switches_found` -- the one mechanism the three checks above all share --
        actually finds a planted marker in a real file, not just an empty scan."""
        with tempfile.TemporaryDirectory() as directory:
            planted = pathlib.Path(directory) / "planted.py"
            planted.write_text("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT = 'true'\n")
            found = self._switches_found(CONTENT_RECORDING_SWITCHES, files=[planted])
        self.assertTrue(found, "the scan's own matching logic did not catch a planted switch")

    def test_no_code_enables_content_recording_programmatically(self):
        """The clause the environment rules above cannot reach.

        A span-content scanner is not what this is: it is the cheaper check that nothing here asks
        for content to be recorded in the first place, by either route. Setting a flag in code is
        the route that leaves no trace in an environment and needs no OpenTelemetry import.
        """
        found = []
        for path in _configuring_files():
            body = path.read_text(errors="replace").casefold()
            for identifier in CONTENT_RECORDING_IDENTIFIERS:
                if identifier in body:
                    found.append((str(path.relative_to(PROJECT)), identifier))
        if found:
            self.fail(
                "content recording may be enabled in code: "
                + "; ".join(f"{identifier} in {path}" for path, identifier in found)
            )


class NoGenAIAttributeEverSurvivesTheAllowlist(unittest.TestCase):
    """What "nothing imports OpenTelemetry" becomes now that something does (issue #61,
    Phase 6). This class used to assert the opposite of its own name -- that no file in the tree
    imported `opentelemetry` at all, so the GenAI attribute surface named above was necessarily
    empty. That import now exists (`observability/telemetry.py`, and every module it wires spans
    into), so the guarantee has to be re-derived from what actually happens at runtime instead of
    from an absent import.

    **Built exactly the way this class's own prior docstring predicted**: "by `gen_ai.*` prefix and
    by value, never by a fixed list of attribute names" -- because the OTel GenAI semantic
    conventions have already renamed this surface once (`gen_ai.prompt`/`gen_ai.completion` are
    gone; `gen_ai.event.content` and `gen_ai.prompt.variable.<name>` exist now), so a fixed list of
    names would go stale the next time they rename it again.

    This project's own code never sets a `gen_ai.*` attribute, and the auto-instrumentation it
    enables (FastAPI, httpx) does not either -- the OpenTelemetry OpenAI instrumentation this
    project has never added is the one that would, and it targets chat completions, embeddings and
    the Responses API, none of which is the realtime session this project speaks (`docs/phase4/
    research-carried-findings.md` §3). But **D9's allowlist filter is what makes that fact durable
    rather than accidental**: any attribute outside D15's four named spans is dropped regardless of
    its own name, `gen_ai.*` included, so a future instrumentation that started emitting one would
    still not survive without an explicit, reviewable edit to `telemetry.ALLOWLIST`. That is the
    property this test actually exercises, on a real fake call, rather than assuming it from the
    absence of an import.
    """

    def test_no_span_from_a_whole_call_carries_a_gen_ai_attribute(self):
        transport = FakeTransport(frames=[audio_frame("hello")], hang=True)
        realtime = FakeRealtimeServer(
            events=[audio_delta("agent-says-hi"), response_done()], respond_after_appends=1,
        )
        spans = run_traced_call(
            run_call(transport, realtime, FakeCoreBankingClient(), FakeCallRecordStore())
        )
        self.assertTrue(spans, "the call produced no spans at all -- nothing was actually exercised")
        offending = [
            (span.name, key) for span in spans for key in span.attributes if key.startswith("gen_ai.")
        ]
        self.assertEqual(offending, [])


if __name__ == "__main__":
    unittest.main()
