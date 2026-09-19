"""The call-record seam: one protocol, one real client, one fake.

Same shape as core_banking/, transport/ and realtime/ -- an external system, its protocol, and a
stand-in that satisfies the same protocol without a network. What is different about this one is
whose facts it holds: these are facts about *calls*, which the system of record has never heard of.
"""
from .store import (
    REASONS,
    CallRecordStore,
    CallRecordStoreUnavailable,
    CallSummaryRecord,
    EscalationRecord,
    EscalationRequested,
    TableStorageCallRecordStore,
)

__all__ = [
    "REASONS",
    "CallRecordStore",
    "CallRecordStoreUnavailable",
    "CallSummaryRecord",
    "EscalationRecord",
    "EscalationRequested",
    "TableStorageCallRecordStore",
]
