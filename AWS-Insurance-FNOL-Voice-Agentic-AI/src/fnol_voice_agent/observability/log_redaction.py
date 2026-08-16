"""Phase 11 Stage C -- the sink-level PII filter at the CloudWatch Logs boundary.

**Why this module exists, stated plainly rather than left implicit.** `ADR-011` already fixed the boundary
(`guardrails/pii.py`'s docstring: "Application logs / traces / metrics: **Yes, always**") and already built
the redactor (`redact_for_transcript`). What did not exist, before this module, was anything that actually
*applies* that redactor at the point a log record leaves the process. `api/lex_codehook.py` has exactly
three `logger` calls in the whole codebase, and by inspection none of them log raw PII today -- but that is
an absence of violations enforced by a docstring's assertion, not a mechanism. Nothing stopped a future
`logger.info(f"turn_input={turn_input}")` from reaching CloudWatch unredacted, and nothing would have caught
it if it had. This module is that mechanism: a `logging.Filter` installed on the root logger's handler(s),
so every record that reaches the sink -- regardless of which module's logger emitted it, present or future
-- is redacted before it leaves the process.

**Placement: handler-level, not logger-level, and the difference matters.** A `Filter` attached to a
`Logger` object only runs for records originating at *that specific logger* -- Python's logging module does
not re-run an ancestor logger's filters during propagation, only its handlers. AWS Lambda's Python runtime
attaches exactly one handler (a `StreamHandler` to stdout, which the platform captures into CloudWatch Logs)
to the root logger before any user code runs -- this is documented Lambda behaviour, not an assumption made
here. `install_pii_log_filter()` therefore attaches the filter to every handler already present on the root
logger (that Lambda-provided handler, in the deployed function), which fires for every record that
propagates to it -- from any logger name, current or future -- not just to the root logger's own `.info()`
calls.

**What this filter covers, and what it does not -- read honestly, per this project's "no invented
capabilities" discipline (`CLAUDE.md`):**
- Covers: `record.msg` (the format string / already-formatted message) and every string-typed entry in
  `record.args` (the values substituted into a `%s`-style call), run through `redact_for_transcript`.
- Does NOT cover: `record.exc_info` / the rendered traceback text from `logger.exception(...)`. A
  traceback's own text is generated at format time from the exception object, not from `record.msg`/`args`,
  and this filter does not attempt to redact it. **This is flagged as the higher-risk gap of the two, not
  the lesser one** (Marco, 2026-08-15) -- a stack frame can carry an entire local-variable payload
  (`turn_input`, a filled-slot dict, a raw event) in its repr, which is a strictly bigger surface than one
  careless `logger.info(f"...")` call, and Python's default traceback formatting has no redaction hook at
  all. Presently low risk in this codebase specifically: `logger.exception` is used exactly once
  (`lex_codehook.py`'s top-level handler), logging only the fixed string `"codehook failed"` plus the
  traceback, at a call site with no locals holding raw PII in scope at that point. **Revisit this the
  moment exception logging expands past that one site** -- the gap does not scale safely with more
  `logger.exception` call sites the way the covered `record.msg`/`args` path does.
- Non-string args (e.g. `route`, an `int`) pass through unchanged rather than being stringified -- this
  preserves the log's structured/diagnostic shape rather than coercing every field to text.

**Self-reporting install, added 2026-08-15 (Marco, "option (c)") -- proving this filter is actually attached
in the deployed runtime should not require a diagnostic branch in `handler()` or a full `C1` re-verification
cycle just to look.** `install_pii_log_filter()` logs one line every time it runs --
`pii_log_filter_installed handlers=<N>`, where `N` is the number of handlers it attached to *this call* --
which a real CloudWatch Logs read after any real invoke answers directly, without inspecting or triggering
any classification-path code at all:
- `handlers=0` on a call where the filter was already present (idempotent no-op) or, more importantly, on a
  cold start where the target logger had **no handlers at all to attach to** -- the silent-no-op failure
  mode this module's own local-proof script (`scripts/verify_log_redaction.py`) already named as its weak
  point. That failure mode is now visible in the deployed system's own logs, not just theorized about.
- `handlers=N>0` on a genuine first attachment -- the expected cold-start case in real Lambda, where the
  platform's own handler is already present on the root logger before this line runs.

This line is permanent, not a one-time probe -- it fires on every cold start, in every future deploy, for
as long as `install_pii_log_filter()` is called at import time. No unreachable-event-shape diagnostic
branch was added to `handler()` for this; the signal comes from the filter's own installation, which needs
no help distinguishing real traffic from a probe because it never looks at traffic at all.
"""

from __future__ import annotations

import logging

from fnol_voice_agent.guardrails.pii import redact_for_transcript

_install_logger = logging.getLogger(__name__)


class PIIRedactionLogFilter(logging.Filter):
    """Runs a log record's message and string args through `redact_for_transcript`.

    Always returns `True` -- this filter redacts, it never suppresses. A filter that dropped records
    outright would fail differently but still fail: it would hide the fact that something needed
    redacting, which is the opposite of an auditable log.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_for_transcript(str(record.msg))
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_for_transcript(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                # %-style logging with a mapping arg (`logger.info("%(x)s", {"x": ...})`) -- not used
                # anywhere in this codebase today, but redacted for consistency rather than left as an
                # unguarded second calling convention.
                record.args = {
                    key: redact_for_transcript(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
        return True


def install_pii_log_filter(logger: logging.Logger | None = None) -> PIIRedactionLogFilter:
    """Attaches a `PIIRedactionLogFilter` to every handler on `logger` (the root logger by default).

    Idempotent: calling this more than once (e.g. on a warm Lambda container re-importing the module, or
    in a test that imports `lex_codehook` more than once) does not stack duplicate filters on the same
    handler -- each handler is checked for an existing `PIIRedactionLogFilter` instance before one is
    added.

    Returns the filter instance, mainly so tests can install it onto a handler they constructed themselves
    rather than relying on process-global logging state.

    Self-reports every call -- see the module docstring's "Self-reporting install" section for why this
    exists and what `handlers=0` means. Logged through this module's OWN logger (`fnol_voice_agent.
    observability.log_redaction`), which propagates to the same handler(s) just attached above, so the
    report line itself passes through the filter it announces -- harmless, since it contains no PII, and a
    small confirmation in its own right that the just-installed filter doesn't crash on its own output.
    """
    target = logger if logger is not None else logging.getLogger()
    installed = PIIRedactionLogFilter()

    attached_count = 0
    for handler in target.handlers:
        if not any(isinstance(f, PIIRedactionLogFilter) for f in handler.filters):
            handler.addFilter(installed)
            attached_count += 1

    _install_logger.info("pii_log_filter_installed handlers=%d", attached_count)

    return installed


__all__ = ["PIIRedactionLogFilter", "install_pii_log_filter"]
