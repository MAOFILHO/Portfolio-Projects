"""Phase 11 Stage C -- the formal positive-control proof for `PIIRedactionLogFilter`.

`tests/unit/test_log_redaction.py` proves the filter CLASS's logic, against synthetic per-test loggers.
This script proves the actual WIRING in `api/lex_codehook.py` -- the real root-logger attachment, at real
import time -- which the unit tests deliberately never touch (each builds its own isolated logger so tests
can't leak filter state into each other).

**What this proves, and what it does not -- read honestly, per `CLAUDE.md`'s "no invented capabilities":**

This is a LOCAL simulation of AWS Lambda's logging setup, not a live invoke of the deployed function. A
handler is attached to the real root logger here, standing in for the handler AWS Lambda's Python runtime
attaches before any user code runs (documented Lambda behaviour, not reproduced here). `lex_codehook` is
then imported for real, exercising its real `install_pii_log_filter()` call against that handler, and its
real `logger` object is used to emit the proof lines -- not a fixture logger built for a test.

**This is a materially weaker claim than proving the filter is installed in the deployed Lambda artifact's
own runtime, and that gap is real, not closed by this script.** The local root logger here is one this
process's own code attached; Lambda's runtime attaches its own. Proving installation in the actual deployed
artifact needs a real invoke of that artifact and an inspection of its actual handler chain -- separate,
tracked work (`PROJECT_STATE.md`), not something this script's local simulation can stand in for.

**Option (c), added 2026-08-15 (Marco), separate from and cheaper than closing the gap above**: this script
now also checks `install_pii_log_filter()`'s own self-report line (`pii_log_filter_installed handlers=N`)
-- proving the filter attached to something is now readable directly from CloudWatch Logs on the *deployed*
artifact too, with no diagnostic branch in `handler()` and no extra `C1` re-verification cycle, because the
report ships as part of the filter's own installation rather than as a one-off probe.

**Phone coverage, added 2026-08-19 (`D124`/`OI46`).** Every check above ever exercised was EMAIL-shaped only
-- zero phone references existed in this script before this pass, confirmed by grep before writing a line of
this change. `D124` found that `guardrails/pii.py`'s `PHONE_RE` is anchored to this project's own synthetic
`555`-exchange convention (`docs/phase0`), not to real phone-number shape, so a real caller's real phone
number was never redacted by this filter, in any layer, ever. The proof below reuses
`redteam/readback_probe.py`'s own real-shaped, non-555 fixture (`"416-987-1547"`, `ADR-017` Round 3's
"Free-text PII audit") rather than minting a fourth phone constant -- same value, same do-not-propagate
posture already accepted there. **This ran RED against the pre-fix `PHONE_RE` once, by design** -- the
failing run is `D124`'s executable proof, captured in `docs/RESULTS.md` rather than skipped past on the way
to green, per this project's test-first discipline.

Free: no AWS calls, no network. Aborts (non-zero exit) rather than silently reporting a pass on a failed
assertion, per `REVIEW-CRITERIA.md` §1.3.
"""

from __future__ import annotations

import logging
import sys

_SYNTHETIC_EMAIL = "marked-synthetic-pii@example.invalid"

# Reused from redteam/readback_probe.py's own `_PII_PHONE` -- real-shaped, NOT this project's 555-exchange
# convention (D124/D125's own root cause). Same value on purpose, not a fourth phone fixture.
_REAL_SHAPED_PHONE = "416-987-1547"


class _CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


def main() -> int:
    failures: list[str] = []

    # Simulate Lambda's pre-attached root handler -- BEFORE lex_codehook is imported, matching the real
    # ordering (Lambda attaches its handler before any user module import runs).
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    capture = _CapturingHandler()
    capture.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(capture)

    print("verify-log-redaction: local simulation of the real lex_codehook.py wiring\n")

    # Real import -- triggers the real `install_pii_log_filter()` call at module import time, against the
    # handler just attached above.
    from fnol_voice_agent.api import lex_codehook

    # -----------------------------------------------------------------------------------------------
    # 1. Pre-filter: toggle the real installed filter OFF on the real handler, log through the real
    #    lex_codehook.logger, confirm marked synthetic PII reaches the sink unredacted.
    # -----------------------------------------------------------------------------------------------
    from fnol_voice_agent.observability.log_redaction import (
        PIIRedactionLogFilter,
        install_pii_log_filter,
    )

    # Option (c), Marco 2026-08-15: the install call reports on itself. Its own log line propagates
    # from `observability.log_redaction`'s logger up to root's handler -- the same `capture` handler --
    # so it should already be present from the import above, with no separate probe needed.
    report_lines = [line for line in capture.lines if line.startswith("pii_log_filter_installed")]
    ok = report_lines and report_lines[-1] == "pii_log_filter_installed handlers=1"
    print(f"  {'ok  ' if ok else 'FAIL'} self-report: install logged 'handlers=1' at import time")
    if not ok:
        failures.append(
            f"expected a 'pii_log_filter_installed handlers=1' line, found: {report_lines!r}"
        )

    installed = [f for f in capture.filters if isinstance(f, PIIRedactionLogFilter)]
    if len(installed) != 1:
        failures.append(
            f"expected exactly 1 PIIRedactionLogFilter on the root handler after importing "
            f"lex_codehook, found {len(installed)}"
        )
    else:
        capture.removeFilter(installed[0])
        lex_codehook.logger.info("diagnostic proof line, email %s", _SYNTHETIC_EMAIL)
        pre_line = capture.lines[-1]
        ok = _SYNTHETIC_EMAIL in pre_line
        print(f"  {'ok  ' if ok else 'FAIL'} pre-filter: synthetic PII reaches the sink unredacted")
        if not ok:
            failures.append(f"pre-filter line did not contain the synthetic PII: {pre_line!r}")

        lex_codehook.logger.info("diagnostic proof line, phone %s", _REAL_SHAPED_PHONE)
        pre_phone_line = capture.lines[-1]
        ok = _REAL_SHAPED_PHONE in pre_phone_line
        print(
            f"  {'ok  ' if ok else 'FAIL'} pre-filter: real-shaped phone reaches the sink unredacted"
        )
        if not ok:
            failures.append(f"pre-filter line did not contain the phone PII: {pre_phone_line!r}")

        # Re-attach (idempotent install would also work; re-attaching the SAME instance we removed is
        # the more direct proof that toggling the SAME filter is what changes the outcome below).
        capture.addFilter(installed[0])

    # -----------------------------------------------------------------------------------------------
    # 2. Post-filter: same real logger, same message shape, filter re-attached -- confirm redaction.
    # -----------------------------------------------------------------------------------------------
    lex_codehook.logger.info("diagnostic proof line, email %s", _SYNTHETIC_EMAIL)
    post_line = capture.lines[-1]
    ok = _SYNTHETIC_EMAIL not in post_line and "[REDACTED:EMAIL]" in post_line
    print(f"  {'ok  ' if ok else 'FAIL'} post-filter: same line, filter re-attached, PII redacted")
    if not ok:
        failures.append(f"post-filter line was not redacted: {post_line!r}")

    # D124/OI46: this is the check that ran RED before PHONE_RE was fixed -- a real-shaped, non-555
    # phone number reaching the same real filter, on the same real wiring the EMAIL check above already
    # covers. If this fails, PHONE_RE does not match real phone-number shape, full stop.
    lex_codehook.logger.info("diagnostic proof line, phone %s", _REAL_SHAPED_PHONE)
    post_phone_line = capture.lines[-1]
    ok = _REAL_SHAPED_PHONE not in post_phone_line and "[REDACTED:PHONE]" in post_phone_line
    print(
        f"  {'ok  ' if ok else 'FAIL'} post-filter: real-shaped phone, filter re-attached, PII redacted"
    )
    if not ok:
        failures.append(f"post-filter phone line was not redacted: {post_phone_line!r}")

    # -----------------------------------------------------------------------------------------------
    # 3. Negative case: the four real operational fields, through the real logger, filter installed.
    # -----------------------------------------------------------------------------------------------
    contact_id = "8f14e45f-ceea-4b57-9b5e-3c6c6c6c6c6c"
    triggering_layer = "L1"
    route = 1
    escalation_reason = "detection-pregraph"
    lex_codehook.logger.info(
        "escalating contact %s on layer %s route %s reason %s",
        contact_id,
        triggering_layer,
        route,
        escalation_reason,
    )
    neg_line = capture.lines[-1]
    ok = (
        contact_id in neg_line
        and triggering_layer in neg_line
        and str(route) in neg_line
        and escalation_reason in neg_line
        and "[REDACTED:" not in neg_line
    )
    print(f"  {'ok  ' if ok else 'FAIL'} negative case: operational fields pass through unchanged")
    if not ok:
        failures.append(f"operational-field line was altered: {neg_line!r}")

    # Idempotency, against the real wiring, not just the unit under test.
    install_pii_log_filter(root)
    count = sum(isinstance(f, PIIRedactionLogFilter) for f in capture.filters)
    ok = count == 1
    print(
        f"  {'ok  ' if ok else 'FAIL'} idempotent: re-installing does not stack duplicate filters"
    )
    if not ok:
        failures.append(f"expected 1 filter instance after re-install, found {count}")

    report_lines = [line for line in capture.lines if line.startswith("pii_log_filter_installed")]
    ok = bool(report_lines) and report_lines[-1] == "pii_log_filter_installed handlers=0"
    print(f"  {'ok  ' if ok else 'FAIL'} self-report: re-install logged 'handlers=0', not silent")
    if not ok:
        failures.append(
            f"expected the re-install's report to read 'handlers=0', found: {report_lines!r}"
        )

    if failures:
        print("\nverify-log-redaction: FAILED")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nverify-log-redaction: passed")
    print(
        "\nScope, stated plainly: this proves the filter's real installed wiring in a LOCAL simulation "
        "of Lambda's logging setup. It does not prove the filter is present in the deployed Lambda "
        "artifact's own runtime -- that needs a real invoke against deployed code, which is separate, "
        "tracked work (PROJECT_STATE.md)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
