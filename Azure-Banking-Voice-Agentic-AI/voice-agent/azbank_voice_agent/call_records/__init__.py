"""The call-record seam: one protocol, one real client, one fake.

Same shape as core_banking/, transport/ and realtime/ -- an external system, its protocol, and a
stand-in that satisfies the same protocol without a network. What is different about this one is
whose facts it holds: these are facts about *calls*, which the system of record has never heard of.
"""
from .store import (
    NOT_CONFIGURED,
    REASONS,
    SUMMARY_DONE,
    SUMMARY_FAILED,
    SUMMARY_SKIPPED,
    TRANSCRIPT_NONE,
    TRANSCRIPT_REDACTION_FAILED,
    TRANSCRIPT_STORED,
    TRANSCRIPT_WRITE_FAILED,
    CallRecordStore,
    CallRecordStoreUnavailable,
    CallSummaryRecord,
    EscalationRecord,
    EscalationRequested,
    TableStorageCallRecordStore,
    is_storable_id,
    storable_or_generated_id,
)

__all__ = [
    "NOT_CONFIGURED",
    "REASONS",
    "SUMMARY_DONE",
    "SUMMARY_FAILED",
    "SUMMARY_SKIPPED",
    "TRANSCRIPT_NONE",
    "TRANSCRIPT_REDACTION_FAILED",
    "TRANSCRIPT_STORED",
    "TRANSCRIPT_WRITE_FAILED",
    "CallRecordStore",
    "CallRecordStoreUnavailable",
    "CallSummaryRecord",
    "EscalationRecord",
    "EscalationRequested",
    "TableStorageCallRecordStore",
    "is_storable_id",
    "storable_or_generated_id",
]
