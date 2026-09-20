"""The post-call pipeline (Phase 8): redact, store, summarise, record -- after the call is over.

**Never on the live-call path** (ADR-006 Decision 4, exit criterion 4). `app.py` schedules this as a
background task once `run_call` has returned; nothing here can add latency or cost to a call, and
nothing here can raise into the process.

**ADR-007 is the spine.** The transcript is redacted in memory before it reaches anything persistent.
Redaction gates everything downstream of it: the blob write *and* the summary both take only the
redacted text, because a summary of a raw transcript is a persisted record that can carry what the
redaction exists to remove. A transcript that cannot be redacted -- the call fails, times out,
returns nonsense, or no redactor is configured -- is never written unredacted as a fallback. That
call gets a row saying so, and no transcript and no summary.

Every step has its own deadline and its own failure, so one degraded dependency costs one field of
one row and nothing else. **Only outcomes are logged, never words, and never an exception's message**
(B2): a redactor's error can echo the text it was given, so a failure is logged as its type alone.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ..call_records import (
    NOT_CONFIGURED,
    SUMMARY_DONE,
    SUMMARY_FAILED,
    SUMMARY_SKIPPED,
    TRANSCRIPT_NONE,
    TRANSCRIPT_REDACTION_FAILED,
    TRANSCRIPT_STORED,
    TRANSCRIPT_WRITE_FAILED,
    CallRecordStore,
    CallSummaryRecord,
    storable_or_generated_id,
)
from . import outcome
from .scrub import scrub_numbers

log = logging.getLogger("postcall")

#: How long any single step may take. Generous: this is off the call path, and Language's
#: conversation PII API is asynchronous-only (docs/phase8/research-language-pii-quota.md).
STEP_DEADLINE_SECONDS = 60.0

#: Bounds on the two model-written fields, so a runaway completion cannot bloat a Table row.
MAX_SUMMARY_CHARS = 2000
MAX_INTENT_CHARS = 200


@dataclass(frozen=True)
class Summary:
    summary: str
    intent: str


class Redactor(Protocol):
    async def redact(self, turns: list[str]) -> list[str]:
        """Return the same turns with PII removed: same count, same order. Raises on any failure."""
        ...


class Summarizer(Protocol):
    async def summarize(self, turns: list[str]) -> Summary:
        """Summarise already-redacted turns. Raises on any failure."""
        ...


class TranscriptStore(Protocol):
    async def write(self, correlation_id: str, turns: list[str]) -> str:
        """Persist already-redacted turns; return the name written. Raises on any failure."""
        ...


@dataclass(frozen=True)
class PostcallServices:
    """What the pipeline works with, handed around as one thing. Each adapter is None when its
    configuration is absent; `call_records` is the only one the pipeline cannot do without."""

    call_records: CallRecordStore
    redactor: Redactor | None = None
    summarizer: Summarizer | None = None
    transcripts: TranscriptStore | None = None


async def _bounded(awaitable):
    return await asyncio.wait_for(awaitable, timeout=STEP_DEADLINE_SECONDS)


async def _step(name, adapter, call, failed, valid=lambda _result: True):
    """Run one adapter call under its deadline. Returns `(result, problem)`.

    `problem` is None when the answer was used. Otherwise it is the record status to write:
    `NOT_CONFIGURED` when there is no adapter, or `failed` -- the step's own failure status -- when
    the adapter raised, timed out or gave an answer `valid` rejects, and `result` is None. Every
    failure is one field of one row, logged as its type alone (B2: an adapter's error can echo the
    text it was given).
    """
    if adapter is None:
        return None, NOT_CONFIGURED
    try:
        result = await _bounded(call(adapter))
        if not valid(result):
            raise ValueError(f"{name} returned a malformed result")
        return result, None
    except Exception as e:  # noqa: BLE001 -- any adapter failure is one field of one row
        log.warning("%s failed (%s)", name, type(e).__name__)
        return None, failed


def _valid_redaction(redacted, turns):
    return (
        isinstance(redacted, list)
        and len(redacted) == len(turns)
        and all(isinstance(turn, str) for turn in redacted)
    )


async def run_postcall(capture, services):
    """Turn one finished call into a redacted transcript and one summary row. Never raises."""
    if capture.end_reason is None:
        log.warning("post-call skipped: the call never finished")
        return
    try:
        await _run(capture, services)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 -- the process must never see a post-call failure
        log.error("post-call failed unexpectedly (%s)", type(e).__name__)


async def _run(capture, services):
    # No id, or one neither store can key on (`app.media_stream` already replaces a bad header, so
    # this is the pipeline's own guard): the call loses its ACS id, never its row.
    correlation_id = storable_or_generated_id(capture.correlation_id)
    if capture.correlation_id and correlation_id != capture.correlation_id:
        log.warning("post-call: the correlation id is not a storage key, using a generated one")
    turns = list(capture.agent_turns)

    transcript_status = TRANSCRIPT_NONE
    blob_name = ""
    redacted = None
    if turns:
        # ADR-007 Decision 2: a failed redaction is no transcript, never a fallback to the raw text.
        redacted, problem = await _step(
            "redaction", services.redactor, lambda r: r.redact(turns), TRANSCRIPT_REDACTION_FAILED,
            lambda result: _valid_redaction(result, turns),
        )
        if problem:
            transcript_status = problem
        else:
            name, problem = await _step(
                "transcript write", services.transcripts,
                lambda t: t.write(correlation_id, redacted), TRANSCRIPT_WRITE_FAILED,
            )
            transcript_status = problem or TRANSCRIPT_STORED
            blob_name = name or ""

    summary_status = SUMMARY_SKIPPED
    summary = intent = ""
    if redacted is not None:
        result, problem = await _step(
            "summary", services.summarizer, lambda s: s.summarize(redacted), SUMMARY_FAILED,
            lambda r: isinstance(r, Summary) and isinstance(r.summary, str) and isinstance(r.intent, str),
        )
        summary_status = problem or SUMMARY_DONE
        if not problem:
            # The redactor's output is number-scrubbed; the model's account of it is too (B2).
            summary = scrub_numbers(result.summary)[:MAX_SUMMARY_CHARS]
            intent = scrub_numbers(result.intent)[:MAX_INTENT_CHARS]

    record = CallSummaryRecord(
        correlation_id=correlation_id,
        call_outcome=outcome.call_outcome(capture.end_reason, capture.auth_state),
        end_reason=capture.end_reason,
        auth_state=capture.auth_state,
        turn_count=capture.turn_count,
        duration_ms=capture.duration_ms,
        occurred_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        transcript_status=transcript_status,
        transcript_blob=blob_name,
        summary_status=summary_status,
        summary=summary,
        intent=intent,
    )
    try:
        await _bounded(services.call_records.record_call(record))
    except Exception as e:  # noqa: BLE001 -- nothing about a finished call can be made worse
        log.error("could not record the call summary (%s)", type(e).__name__)
        return
    log.info(
        "post-call done correlationId=%s outcome=%s transcript=%s summary=%s",
        correlation_id, record.call_outcome, transcript_status, summary_status,
    )
