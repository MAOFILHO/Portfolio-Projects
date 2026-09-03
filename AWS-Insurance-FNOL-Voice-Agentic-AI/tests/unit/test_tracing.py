"""`ADR-018`/Phase 14 -- `observability/tracing.py`.

Uses `opentelemetry.sdk.trace.export.in_memory_span_exporter.InMemorySpanExporter` with a `SimpleSpanProcessor`
(exports synchronously on `span.end()`, no batching/background-thread timing to fight in a test) instead of
`tracing.py`'s own `BatchSpanProcessor`/OTLP-HTTP setup -- installed by monkeypatching `tracing._PROVIDER`
directly, so `traced_span`/`start_turn_span` (both read `_get_tracer_provider()`, which returns `_PROVIDER`
once it is non-`None`) exercise the SAME code paths production does, against a provider these tests can
actually inspect. `monkeypatch.setattr` restores `tracing._PROVIDER` after every test, so no test here leaks
tracing state into another (including `test_lex_codehook.py`'s own subprocess boto3-absence test, which is
unaffected regardless -- it never touches this module's globals at all).
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from typing import Any

import pytest
from moto import mock_aws
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased

from fnol_voice_agent.agents.graph import build_graph
from fnol_voice_agent.agents.testing.fake_llm import (
    FakeBedrockConverseClient,
    converse_tool_use_response,
)
from fnol_voice_agent.aws.checkpointer import build_test_checkpointer
from fnol_voice_agent.guardrails.client import BedrockGuardrailClient, MockGuardrailClient
from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, MockEmbedder
from fnol_voice_agent.observability import tracing

_ROUTER_MODEL = "us.amazon.nova-micro-v1:0"

# Seeded PII-shaped literals for the "no PII in any span attribute" regression guard below -- synthetic,
# not real (same convention as every other fixture value in this test suite).
_PII_POLICY_NUMBER = "PY4821"
_PII_PHONE = "416-555-0199"
_PII_EMAIL = "jane.doe@example.com"


@pytest.fixture
def in_memory_spans(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Installs a real `TracerProvider` backed by `InMemorySpanExporter`, in place of `tracing.py`'s own
    lazily-built OTLP-HTTP provider -- see module docstring. `ParentBased(root=ALWAYS_ON)` matches
    `tracing._install()`'s own sampler exactly, so nothing about the sampling decision differs from
    production; only the exporter differs.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ParentBased(root=ALWAYS_ON))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_PROVIDER", provider)
    monkeypatch.setattr(tracing, "_INSTALL_FAILED", False)
    return exporter


def _classification(intent: str, *, confidence: float = 0.95) -> dict[str, Any]:
    return converse_tool_use_response(
        "classify_turn",
        {
            "safety_flag": False,
            "intent": intent,
            "intent_confidence": confidence,
            "coverage_question_type": "not_applicable",
        },
    )


# ---------------------------------------------------------------------------------------------------
# Constraint 1: import-safe with opentelemetry present and (separately) absent.
# ---------------------------------------------------------------------------------------------------


def test_module_imports_fine_with_a_real_opentelemetry_present() -> None:
    """This whole test file already imports `tracing` at module load -- if that import failed, nothing
    below would even collect. Asserted explicitly anyway, so this property has its own named test rather
    than being an implicit side effect of every other test in this file passing."""
    assert tracing._otel_trace is not None


def test_module_imports_fine_when_opentelemetry_is_absent() -> None:
    """Run in a subprocess, mirroring `test_lex_codehook.py::test_the_module_imports_without_botocore_
    being_loaded`'s own subprocess pattern -- reloading this module in-process would leave every
    already-imported caller (`agents/graph.py`, `aws/bedrock_router.py`, the four `mcp/*_server.py`
    modules, all of which do `from fnol_voice_agent.observability import tracing` at their own import
    time) holding a stale reference to a module object a monkeypatch-and-reload would replace out from
    under them. `sys.modules['opentelemetry'] = None` is Python's own sentinel for "this import
    previously failed" -- it forces the next `import opentelemetry...` anywhere in the subprocess to
    raise `ImportError` without needing the package actually uninstalled from this dev environment.
    """
    script = textwrap.dedent(
        """
        import sys
        sys.modules["opentelemetry"] = None
        import fnol_voice_agent.observability.tracing as tracing

        assert tracing._otel_trace is None, "opentelemetry import should have been blocked"

        # Every span-creating helper must be a transparent no-op / pass-through with otel absent.
        def _fn():
            return 42

        wrapped = tracing.traced("some.span")(_fn)
        assert wrapped is _fn, "traced() must return fn UNCHANGED when opentelemetry is absent"
        assert wrapped() == 42

        wrapped_mcp = tracing.traced_mcp_tool("Tool", "domain")(_fn)
        assert wrapped_mcp is _fn, "traced_mcp_tool() must return fn UNCHANGED when opentelemetry is absent"

        with tracing.traced_span("child") as span:
            assert span is None

        span = tracing.start_turn_span(contact_id="c1", turn_input_len=3)
        assert span is None
        tracing.end_turn_span(span)  # must not raise on None
        tracing.set_span_attribute(span, "fnol.contact_id", "c1")  # must not raise on None
        tracing.annotate_current_span({"fnol.contact_id": "c1"})  # must not raise
        tracing.flush(timeout_millis=200)  # must not raise, no provider was ever built

        print("OK")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip().splitlines()[-1] == "OK", result.stderr


# ---------------------------------------------------------------------------------------------------
# The allowlist boundary: an unlisted attribute key is dropped, not set, and does not raise.
# ---------------------------------------------------------------------------------------------------


def test_set_span_attribute_drops_an_unlisted_key(
    in_memory_spans: InMemorySpanExporter, caplog: pytest.LogCaptureFixture
) -> None:
    with tracing.traced_span("test.span") as span:
        tracing.set_span_attribute(span, "fnol.contact_id", "c1")  # allowed
        tracing.set_span_attribute(span, "turn_input", "raw caller text")  # NOT allowed -- dropped

    (recorded,) = in_memory_spans.get_finished_spans()
    assert recorded.attributes is not None
    assert recorded.attributes.get("fnol.contact_id") == "c1"
    assert "turn_input" not in recorded.attributes
    assert any("dropped span attribute" in message for message in caplog.messages)


def test_set_span_attribute_and_annotate_current_span_are_no_ops_on_none_span() -> None:
    # No provider installed (default state) -- traced_span yields None, and every helper must tolerate it.
    tracing.set_span_attribute(None, "fnol.contact_id", "c1")  # must not raise
    tracing.annotate_current_span(
        {"fnol.contact_id": "c1"}
    )  # must not raise (no current span either)


# ---------------------------------------------------------------------------------------------------
# bedrock.apply_guardrail -- exercised directly against BedrockGuardrailClient (the graph-turn fixture
# below uses MockGuardrailClient, which is never decorated -- ADR-018's instruction names only the real
# client's method).
# ---------------------------------------------------------------------------------------------------


class _FakeGuardrailBotoClient:
    """Minimal stand-in for the real `bedrock-runtime` client's `apply_guardrail` response shape,
    carrying a masked PII entity -- proves the guardrail span never captures the masked text itself,
    only the metrics `guardrails/client.py::_parse_response` already extracts from it."""

    def apply_guardrail(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "action": "GUARDRAIL_INTERVENED",
            "outputs": [{"text": "Your number is {PHONE}."}],
            "assessments": [
                {
                    "sensitiveInformationPolicy": {
                        "piiEntities": [{"type": "PHONE_NUMBER", "action": "ANONYMIZED"}]
                    }
                }
            ],
            "usage": {
                "sensitiveInformationPolicyUnits": 1,
                "sensitiveInformationPolicyFreeUnits": 0,
            },
        }


def test_apply_guardrail_span_carries_metrics_never_pii(
    in_memory_spans: InMemorySpanExporter,
) -> None:
    client = BedrockGuardrailClient("gr-fake", "1", region="us-west-2")
    client._client = (
        _FakeGuardrailBotoClient()
    )  # bypasses _get_client()'s real-AWS construction path

    result = client.apply_guardrail("OUTPUT", f"Your number is {_PII_PHONE}.")
    assert result.masked is True
    assert result.blocked is False

    (span,) = in_memory_spans.get_finished_spans()
    assert span.name == "bedrock.apply_guardrail"
    assert span.attributes is not None
    assert span.attributes["fnol.guardrail.source"] == "OUTPUT"
    assert span.attributes["fnol.guardrail.action"] == "GUARDRAIL_INTERVENED"
    assert span.attributes["fnol.guardrail.blocked"] is False
    assert span.attributes["fnol.guardrail.masked"] is True
    usage = json.loads(str(span.attributes["fnol.guardrail.usage_json"]))
    assert usage == {"sensitiveInformationPolicyUnits": 1, "sensitiveInformationPolicyFreeUnits": 0}

    for key, value in span.attributes.items():
        assert key in tracing._ALLOWED_SPAN_ATTRIBUTES
        assert _PII_PHONE not in str(value)


# ---------------------------------------------------------------------------------------------------
# Full graph turn -- span shape, nesting, allowlist compliance, and the PII scan.
# ---------------------------------------------------------------------------------------------------


def _build_traced_graph(table_suffix: str) -> tuple[Any, Any]:
    store = DynamoVectorStore(table_name=f"fnol-tracing-test-kb-{table_suffix}", region="us-west-2")
    store.ensure_table()
    embedder = MockEmbedder()
    checkpointer = build_test_checkpointer(f"fnol-tracing-test-checkpoints-{table_suffix}")
    caller = FakeBedrockConverseClient(
        by_model={_ROUTER_MODEL: _classification("UpdateContactInfo")}
    )
    graph = build_graph(
        vector_store=store,
        embedder=embedder,
        bedrock_caller=caller,
        guardrail_client=MockGuardrailClient(),
        checkpointer=checkpointer,
    )
    return graph, caller


def test_full_turn_span_shape_nesting_and_no_pii(in_memory_spans: InMemorySpanExporter) -> None:
    """Drives a real `UpdateContactInfo` turn (same pre-filled-slots shape as `scripts/verify_lambda_
    execution.py`'s own D87-regression event) through the real graph, wrapped in `fnol.turn` the same way
    `api/lex_codehook.py::handler` wraps a real invocation. `new_value` carries a PII-shaped phone number
    on purpose -- `update_contact_info_node`'s own response text interpolates it directly
    (`f"That's {filled['new_value']} -- is that right?"`), so if any span-setting code ever started
    passing response_text/slot values through to a span attribute, THIS is the turn that would catch it.
    """
    with mock_aws():
        graph, caller = _build_traced_graph("nesting")
        turn_span = tracing.start_turn_span(contact_id="contact-tracing-test", turn_input_len=20)
        try:
            result = graph.invoke(
                {
                    "contact_id": "contact-tracing-test",
                    "turn_input": "update my phone number",
                    "filled_slots": {
                        "policy_number": _PII_POLICY_NUMBER,
                        "field": "phone",
                        "new_value": _PII_PHONE,
                        "confirm_update_contact_info": True,
                    },
                    "retry_counts": {},
                    "is_barge_in": False,
                },
                {"configurable": {"thread_id": "contact-tracing-test"}},
            )
        finally:
            tracing.end_turn_span(turn_span)

    assert "Done" in result["response_text"]
    assert caller.call_count >= 1  # route_and_classify really called classify_turn

    spans = in_memory_spans.get_finished_spans()
    root = next(s for s in spans if s.name == "fnol.turn")
    node_spans = [s for s in spans if s.name.startswith("fnol.node.")]
    bedrock_spans = [s for s in spans if s.name.startswith("bedrock.")]
    mcp_spans = [s for s in spans if s.name.startswith("mcp.")]

    assert node_spans, "expected at least one fnol.node.* span"
    assert (
        bedrock_spans
    ), "expected at least one bedrock.* span (route_and_classify's classify_turn call)"
    assert mcp_spans, "expected at least one mcp.* span (update_contact_info's real MCP call)"

    # --- Nesting: every node span is a direct child of the fnol.turn root. ---
    for node_span in node_spans:
        assert node_span.parent is not None
        assert (
            node_span.parent.span_id == root.context.span_id
        ), f"{node_span.name} is not a direct child of fnol.turn"

    # --- Nesting: every bedrock./mcp. span is a child of SOME fnol.node.* span, not a sibling of one. ---
    node_span_ids = {s.context.span_id for s in node_spans}
    for leaf_span in bedrock_spans + mcp_spans:
        assert leaf_span.parent is not None
        assert (
            leaf_span.parent.span_id in node_span_ids
        ), f"{leaf_span.name}'s parent is not one of the fnol.node.* spans"

    # --- Allowlist compliance: every attribute key set on every span is a member of the allowlist. ---
    for span in spans:
        for key in span.attributes or {}:
            assert (
                key in tracing._ALLOWED_SPAN_ATTRIBUTES
            ), f"{span.name} set an attribute {key!r} not in _ALLOWED_SPAN_ATTRIBUTES"

    # --- The PII scan: none of the seeded literals appear in ANY attribute value on ANY span. ---
    pii_literals = (_PII_POLICY_NUMBER, _PII_PHONE, _PII_EMAIL)
    for span in spans:
        for key, value in (span.attributes or {}).items():
            rendered = str(value)
            for literal in pii_literals:
                assert literal not in rendered, (
                    f"{span.name}'s attribute {key!r}={rendered!r} contains a seeded PII literal "
                    f"({literal!r}) -- ADR-018's IDs-and-metrics-only boundary is broken"
                )
