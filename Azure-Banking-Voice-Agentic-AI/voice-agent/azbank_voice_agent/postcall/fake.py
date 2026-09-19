"""Deterministic stand-ins for the post-call pipeline's three collaborators.

Same shape as the other pair-with-a-fake modules: real modules rather than test helpers, no network,
ever. Each can fail or hang on demand, which is what the fail-closed tests are driven through.

`FakeTranscriptStore` registers every instance in `WRITTEN`, so `tests/test_zz_b2_leak_scan.py` can
sweep everything a run persisted without each test having to hand its store over.
"""
import asyncio
from typing import ClassVar

from .pipeline import Summary

_UNSET = object()


class FakeRedactor:
    """Replaces each of `terms` with "[REDACTED]". `leak=True` returns the text unchanged -- the
    deliberately broken redactor the tests use to prove their own detectors work."""

    def __init__(self, terms=(), fail_with=None, hang=False, leak=False, returns=_UNSET):
        self.terms = tuple(terms)
        self.fail_with = fail_with
        self.hang = hang
        self.leak = leak
        self.returns = returns
        self.inputs = []

    async def redact(self, turns):
        self.inputs.append(list(turns))
        if self.hang:
            await asyncio.sleep(3600)
        if self.fail_with is not None:
            raise self.fail_with
        if self.returns is not _UNSET:
            return self.returns
        if self.leak:
            return list(turns)
        out = []
        for turn in turns:
            for term in self.terms:
                turn = turn.replace(term, "[REDACTED]")
            out.append(turn)
        return out


class FakeSummarizer:
    SUMMARY = "The agent answered the caller's question."
    INTENT = "general_enquiry"

    def __init__(self, fail_with=None, hang=False):
        self.fail_with = fail_with
        self.hang = hang
        self.inputs = []

    async def summarize(self, turns):
        self.inputs.append(list(turns))
        if self.hang:
            await asyncio.sleep(3600)
        if self.fail_with is not None:
            raise self.fail_with
        return Summary(summary=self.SUMMARY, intent=self.INTENT)


class FakeTranscriptStore:
    #: Every store built during this process, for the B2 sweep. Never read by production code.
    WRITTEN: ClassVar[list] = []

    def __init__(self, fail_with=None):
        FakeTranscriptStore.WRITTEN.append(self)
        self.fail_with = fail_with
        self.writes = []

    @staticmethod
    def name_for(correlation_id):
        return f"{correlation_id}.json"

    async def write(self, correlation_id, turns):
        if self.fail_with is not None:
            raise self.fail_with
        self.writes.append((correlation_id, list(turns)))
        return self.name_for(correlation_id)
