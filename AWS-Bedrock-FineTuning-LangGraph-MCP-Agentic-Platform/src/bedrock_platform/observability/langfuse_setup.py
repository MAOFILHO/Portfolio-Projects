"""Langfuse Cloud tracing for the agent graph.

## Why manual instrumentation rather than the LangChain CallbackHandler

Langfuse's own guidance is to prefer a framework integration over manual spans, and this
project runs LangGraph, which has one. It is deliberately not used here, for two reasons:

1. **It would miss the only real LLM calls.** This graph's model calls go to Bedrock
   through `bedrock-runtime.converse`, not through a LangChain `Runnable`. The
   `CallbackHandler` hooks LangChain callbacks, so those generations — the only place
   model name and token usage exist — would never be captured.
2. **It requires the `langchain` meta-package**, which is not a dependency of this project
   (only `langchain-core` and `langgraph` are). Adding it would buy untyped node spans we
   can type more precisely by hand.

Manual instrumentation lets each sub-agent be typed `agent` (which drives the Langfuse
Agent Graph), each MCP tool call `tool`, and each Bedrock call `generation` carrying model
and usage — the baseline Langfuse asks for.

Tracing is optional infrastructure: absent keys, a bad key, or an unreachable host degrade
to a no-op rather than breaking the pipeline. Credentials come from `.env` and are never
logged.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from bedrock_platform.config.settings import Settings

logger = logging.getLogger(__name__)

# Redacted before anything leaves the process. The pharma scenario carries
# adverse-event narratives and banking carries account questions; both are synthetic here,
# but the pipeline is a template for data that would not be.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_LONG_DIGITS = re.compile(r"\b\d{7,}\b")
_AWS_ACCOUNT = re.compile(r"\b\d{12}\b")


class TracingStatus:
    """Why tracing is or isn't active, so a silent no-op is diagnosable."""

    def __init__(self, enabled: bool, reason: str) -> None:
        self.enabled = enabled
        self.reason = reason

    def __str__(self) -> str:
        return f"{'enabled' if self.enabled else 'disabled'} ({self.reason})"


_client: Any | None = None
_status = TracingStatus(False, "not initialised")


def _mask(*, data: Any, **_kwargs: Any) -> Any:
    """Applied by the SDK to every input/output before export.

    `data` is keyword-only because that is the shape Langfuse's `MaskFunction` protocol
    requires; a positional signature type-checks as an ordinary callable but does not
    satisfy the protocol.
    """
    if isinstance(data, str):
        text = _EMAIL.sub("<email>", data)
        text = _AWS_ACCOUNT.sub("<account-id>", text)
        return _LONG_DIGITS.sub("<number>", text)
    if isinstance(data, dict):
        return {key: _mask(data=value) for key, value in data.items()}
    if isinstance(data, list):
        return [_mask(data=item) for item in data]
    return data


def init_tracing() -> TracingStatus:
    """Idempotent. Safe to call at import time and again per run."""
    global _client, _status
    if _client is not None:
        return _status

    settings = Settings()  # type: ignore[call-arg]  # values come from .env at runtime
    public_key = (settings.langfuse_public_key or "").strip()
    secret_key = (settings.langfuse_secret_key or "").strip()
    base_url = (settings.langfuse_host or "").strip() or "https://cloud.langfuse.com"

    if not public_key or not secret_key:
        _status = TracingStatus(False, "LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
        logger.info("Langfuse tracing disabled: %s", _status.reason)
        return _status

    try:
        # Imported here, not at module scope, so credentials are read from Settings after
        # .env has loaded — importing before env vars are available is the documented way
        # to end up with a client authenticated against nothing.
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url,
            mask=_mask,
            # Must be one of the conventional environment names so demo runs never
            # pollute production dashboards. The project namespace goes on tags instead —
            # it identifies a deployment, not a lifecycle stage.
            environment=settings.langfuse_environment,
        )
    except Exception as exc:  # noqa: BLE001 - observability must never break the pipeline
        _status = TracingStatus(False, f"client init failed: {type(exc).__name__}: {exc}")
        logger.warning("Langfuse tracing disabled: %s", _status.reason)
        return _status

    _status = TracingStatus(True, base_url)
    logger.info("Langfuse tracing enabled -> %s", base_url)
    return _status


def tracing_status() -> TracingStatus:
    return _status


@contextmanager
def trace_step(
    name: str,
    as_type: str = "span",
    *,
    input: Any = None,
    model: str | None = None,
    **metadata: Any,
) -> Iterator[Any]:
    """Wraps one unit of work as a Langfuse observation.

    `as_type` should be the most specific type available — `agent` for a sub-agent, `tool`
    for an MCP tool call, `generation` for a model call. Generic spans flatten the Agent
    Graph and lose per-type analytics.

    A tracing failure is logged and swallowed; the wrapped work still runs and its
    exceptions still propagate.
    """
    if _client is None:
        yield None
        return

    try:
        with _client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=input,
            model=model,
            metadata=metadata or None,
        ) as observation:
            yield observation
    except Exception:  # noqa: BLE001
        logger.debug("Langfuse observation %r failed to start; running untraced", name)
        yield None


@contextmanager
def trace_run(name: str, *, input: Any = None, tags: list[str] | None = None) -> Iterator[Any]:
    """Wraps an entire pipeline run as the single root observation of one trace.

    Without this, every node opens its own root observation and Langfuse records four
    unrelated traces instead of one tree — the "flat traces" failure mode, which loses the
    parent/child structure the Agent Graph and per-step debugging depend on.

    Trace-level attributes are set via `propagate_attributes` so they reach every child.
    """
    if _client is None:
        yield None
        return

    try:
        from langfuse import propagate_attributes

        with (
            _client.start_as_current_observation(name=name, as_type="chain", input=input) as root,
            propagate_attributes(trace_name=name, tags=tags or []),
        ):
            yield root
    except Exception:  # noqa: BLE001
        logger.debug("Langfuse root observation %r failed; running untraced", name)
        yield None


def set_output(observation: Any, output: Any) -> None:
    """Sets the output on an observation. On the root, this becomes the trace-level
    output shown in the tracing table and read by evaluators — a trace whose output is
    null is far harder to triage at a glance."""
    if observation is None:
        return
    try:
        observation.update(output=output)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Langfuse output update failed: %s", exc)


def record_generation_usage(
    observation: Any, *, output: Any, input_tokens: int, output_tokens: int
) -> None:
    """Attaches model output and token usage to an in-flight `generation` observation.

    Token counts are what let Langfuse compute cost, so a generation without them is
    half-instrumented.
    """
    if observation is None:
        return
    try:
        observation.update(
            output=output,
            usage_details={
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Langfuse usage update failed: %s", exc)


def update_current_trace(**kwargs: Any) -> None:
    if _client is None:
        return
    try:
        _client.update_current_span(**kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Langfuse trace update failed: %s", exc)


def flush() -> None:
    """Langfuse batches in a background thread; a short-lived CLI run loses its traces on
    exit without this."""
    if _client is None:
        return
    try:
        _client.flush()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Langfuse flush failed: %s", exc)
