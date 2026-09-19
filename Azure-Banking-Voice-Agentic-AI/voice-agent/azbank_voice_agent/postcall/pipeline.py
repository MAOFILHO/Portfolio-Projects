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
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ..call_records import CallSummaryRecord
from . import outcome

log = logging.getLogger("postcall")

#: How long any single step may take. Generous: this is off the call path, and Language's
#: conversation PII API is asynchronous-only (docs/phase8/research-language-pii-quota.md).
STEP_DEADLINE_SECONDS = 60.0

#: Bounds on the two model-written fields, so a runaway completion cannot bloat a Table row.
MAX_SUMMARY_CHARS = 2000
MAX_INTENT_CHARS = 200

TRANSCRIPT_STORED = "stored"
TRANSCRIPT_NONE = "none"
NOT_CONFIGURED = "not_configured"
TRANSCRIPT_REDACTION_FAILED = "redaction_failed"
TRANSCRIPT_WRITE_FAILED = "write_failed"
SUMMARY_DONE = "done"
SUMMARY_SKIPPED = "skipped"
SUMMARY_FAILED = "failed"


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


async def _bounded(awaitable):
    return await asyncio.wait_for(awaitable, timeout=STEP_DEADLINE_SECONDS)


def _valid_redaction(redacted, turns):
    return (
        isinstance(redacted, list)
        and len(redacted) == len(turns)
        and all(isinstance(turn, str) for turn in redacted)
    )


async def run_postcall(capture, *, call_records, redactor=None, summarizer=None, transcripts=None):
    """Turn one finished call into a redacted transcript and one summary row. Never raises."""
    if capture.end_reason is None:
        log.warning("post-call skipped: the call never finished")
        return
    try:
        await _run(capture, call_records, redactor, summarizer, transcripts)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 -- the process must never see a post-call failure
        log.error("post-call failed unexpectedly (%s)", type(e).__name__)


async def _run(capture, call_records, redactor, summarizer, transcripts):
    correlation_id = capture.correlation_id or uuid.uuid4().hex
    turns = list(capture.agent_turns)

    transcript_status = TRANSCRIPT_NONE
    blob = ""
    redacted = None
    if turns:
        if redactor is None:
            transcript_status = NOT_CONFIGURED
        else:
            try:
                candidate = await _bounded(redactor.redact(turns))
                if not _valid_redaction(candidate, turns):
                    raise ValueError("redactor returned a malformed result")
                redacted = candidate
            except Exception as e:  # noqa: BLE001 -- any redaction failure fails closed
                # ADR-007 Decision 2: no fallback to the raw text, ever.
                log.warning("redaction failed (%s), no transcript for this call", type(e).__name__)
                transcript_status = TRANSCRIPT_REDACTION_FAILED
        if redacted is not None:
            if transcripts is None:
                transcript_status = NOT_CONFIGURED
            else:
                try:
                    blob = await _bounded(transcripts.write(correlation_id, redacted))
                    transcript_status = TRANSCRIPT_STORED
                except Exception as e:  # noqa: BLE001 -- any adapter failure is one field of one row
                    log.warning("transcript write failed (%s)", type(e).__name__)
                    transcript_status = TRANSCRIPT_WRITE_FAILED

    summary_status = SUMMARY_SKIPPED
    summary = intent = ""
    if redacted is not None:
        if summarizer is None:
            summary_status = NOT_CONFIGURED
        else:
            try:
                result = await _bounded(summarizer.summarize(redacted))
                if not (isinstance(result, Summary)
                        and isinstance(result.summary, str) and isinstance(result.intent, str)):
                    raise ValueError("summarizer returned a malformed result")
                summary = result.summary[:MAX_SUMMARY_CHARS]
                intent = result.intent[:MAX_INTENT_CHARS]
                summary_status = SUMMARY_DONE
            except Exception as e:  # noqa: BLE001 -- any adapter failure is one field of one row
                log.warning("summary failed (%s)", type(e).__name__)
                summary_status = SUMMARY_FAILED

    record = CallSummaryRecord(
        correlation_id=correlation_id,
        call_outcome=outcome.call_outcome(capture.end_reason, capture.auth_state),
        end_reason=capture.end_reason,
        auth_state=capture.auth_state,
        turn_count=capture.turn_count,
        duration_ms=capture.duration_ms,
        occurred_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        transcript_status=transcript_status,
        transcript_blob=blob,
        summary_status=summary_status,
        summary=summary,
        intent=intent,
    )
    try:
        await _bounded(call_records.record_call(record))
    except Exception as e:  # noqa: BLE001 -- nothing about a finished call can be made worse
        log.error("could not record the call summary (%s)", type(e).__name__)
        return
    log.info(
        "post-call done correlationId=%s outcome=%s transcript=%s summary=%s",
        correlation_id, record.call_outcome, transcript_status, summary_status,
    )
