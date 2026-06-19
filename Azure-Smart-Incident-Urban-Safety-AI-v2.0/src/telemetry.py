"""
Observability and telemetry via Azure Monitor OpenTelemetry.

Uses the Azure Monitor OpenTelemetry Distro (standard OTel SDKs, not proprietary).
Surfaces traces, logs, and metrics in Application Insights — including the dedicated
Agents view for per-run traces, tool calls, token usage, and error rates.

Usage:
    from src.telemetry import init_telemetry, trace_rag_query

    init_telemetry()  # Call once at startup

    with trace_rag_query("user question") as trace:
        docs = hybrid_search(...)
        trace.set_retrieval(docs)
        answer = generate(...)
        trace.set_generation(answer, tokens=123)
"""

import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("contoso.incident_assistant")

_TELEMETRY_ENABLED = False
_tracer = None
_meter = None

# Metric instruments
_query_counter = None
_query_latency = None
_retrieval_count = None
_error_counter = None


def init_telemetry() -> bool:
    global _TELEMETRY_ENABLED, _tracer, _meter
    global _query_counter, _query_latency, _retrieval_count, _error_counter

    conn_str = os.getenv("APPINSIGHTS_CONNECTION_STRING")
    if not conn_str:
        logger.info("Telemetry disabled: APPINSIGHTS_CONNECTION_STRING not set")
        _TELEMETRY_ENABLED = False
        return False

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry import metrics, trace

        configure_azure_monitor(
            connection_string=conn_str,
            enable_live_metrics=True,
        )

        _tracer = trace.get_tracer(
            "contoso.incident_assistant",
            schema_url="https://opentelemetry.io/schemas/1.21.0",
        )
        _meter = metrics.get_meter("contoso.incident_assistant")

        _query_counter = _meter.create_counter(
            "rag.queries.total",
            description="Total RAG queries processed",
        )
        _query_latency = _meter.create_histogram(
            "rag.query.duration_ms",
            description="RAG query end-to-end latency in milliseconds",
        )
        _retrieval_count = _meter.create_histogram(
            "rag.retrieval.document_count",
            description="Number of documents retrieved per query",
        )
        _error_counter = _meter.create_counter(
            "rag.errors.total",
            description="Total RAG query errors",
        )

        _TELEMETRY_ENABLED = True
        logger.info("Telemetry enabled: Azure Monitor OpenTelemetry configured")
        return True

    except ImportError as e:
        logger.warning(
            f"OpenTelemetry packages not installed ({e}). "
            "Install with: pip install azure-monitor-opentelemetry"
        )
        _TELEMETRY_ENABLED = False
        return False

    except Exception as e:
        logger.error(f"Telemetry initialization failed: {e}")
        _TELEMETRY_ENABLED = False
        return False


@dataclass
class RAGTrace:
    query: str
    start_time: float = field(default_factory=time.time)
    retrieval_docs: list[dict] = field(default_factory=list)
    retrieval_count: int = 0
    retrieval_latency_ms: float = 0
    generation_answer: str = ""
    generation_tokens: int = 0
    generation_latency_ms: float = 0
    total_latency_ms: float = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _retrieval_start: float = field(default=0, repr=False)
    _generation_start: float = field(default=0, repr=False)

    def start_retrieval(self):
        self._retrieval_start = time.time()

    def set_retrieval(self, docs: list[dict]):
        if self._retrieval_start:
            self.retrieval_latency_ms = (time.time() - self._retrieval_start) * 1000
        self.retrieval_docs = docs
        self.retrieval_count = len(docs)

    def start_generation(self):
        self._generation_start = time.time()

    def set_generation(self, answer: str, tokens: int = 0):
        if self._generation_start:
            self.generation_latency_ms = (time.time() - self._generation_start) * 1000
        self.generation_answer = answer
        self.generation_tokens = tokens

    def set_error(self, error: str):
        self.error = error

    def finalize(self):
        self.total_latency_ms = (time.time() - self.start_time) * 1000


@contextmanager
def trace_rag_query(query: str, **metadata):
    trace = RAGTrace(query=query, metadata=metadata)

    if _TELEMETRY_ENABLED and _tracer:
        from opentelemetry import trace as otel_trace

        with _tracer.start_as_current_span(
            "rag.query",
            kind=otel_trace.SpanKind.SERVER,
            attributes={
                "gen_ai.system": "azure_openai",
                "gen_ai.operation.name": "rag_query",
                "gen_ai.request.model": os.getenv("AZURE_GPT_DEPLOYMENT", "gpt-4o"),
                "rag.query.text": query[:500],
            },
        ) as span:
            try:
                yield trace
            except Exception as e:
                trace.set_error(str(e))
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
            finally:
                trace.finalize()
                span.set_attributes({
                    "rag.retrieval.count": trace.retrieval_count,
                    "rag.retrieval.latency_ms": round(trace.retrieval_latency_ms, 1),
                    "rag.generation.latency_ms": round(trace.generation_latency_ms, 1),
                    "rag.total_latency_ms": round(trace.total_latency_ms, 1),
                    "gen_ai.usage.output_tokens": trace.generation_tokens,
                    "rag.source_types": str(list({d.get("type", "") for d in trace.retrieval_docs})),
                    "rag.has_error": trace.error is not None,
                })
                _emit_metrics(trace)
    else:
        try:
            yield trace
        except Exception as e:
            trace.set_error(str(e))
            raise
        finally:
            trace.finalize()
            _log_trace(trace)


def _emit_metrics(trace: RAGTrace):
    attrs = {"rag.has_error": str(trace.error is not None).lower()}

    if _query_counter:
        _query_counter.add(1, attrs)
    if _query_latency:
        _query_latency.record(trace.total_latency_ms, attrs)
    if _retrieval_count:
        _retrieval_count.record(trace.retrieval_count, attrs)
    if trace.error and _error_counter:
        _error_counter.add(1, attrs)


def _log_trace(trace: RAGTrace):
    if trace.error:
        logger.error(
            f"RAG query failed: {trace.query[:100]} | error={trace.error}"
        )
    else:
        logger.info(
            f"RAG query: {trace.query[:100]} "
            f"| {trace.retrieval_count} docs "
            f"| {trace.total_latency_ms:.0f}ms total"
        )


def log_pipeline_event(event: str, details: dict[str, Any] | None = None):
    if _TELEMETRY_ENABLED and _tracer:
        with _tracer.start_as_current_span(
            f"pipeline.{event}",
            attributes={"pipeline.event": event, **(details or {})},
        ):
            pass
    logger.info(f"Pipeline: {event} {details or ''}")
