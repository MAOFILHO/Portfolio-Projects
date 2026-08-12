from collections.abc import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SpanExportResult


class TerseConsoleSpanExporter(ConsoleSpanExporter):
    """Prints one compact line per finished span instead of the default full dump,
    so traces stay readable in the terminal during `make run`."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            duration_ms = 0.0
            if span.end_time is not None and span.start_time is not None:
                duration_ms = (span.end_time - span.start_time) / 1_000_000
            status = span.status.status_code.name
            print(f"[trace] {span.name} ({duration_ms:.1f}ms) status={status}")
        return SpanExportResult.SUCCESS
