"""Every credential this suite keys, in one place, so B2's scan cannot fall behind the suite.

Not a test module -- imported by `tests/test_zz_b2_leak_scan.py`, `tests/redteam_harness.py` and
`tests/test_whole_call.py`, the same way `redteam_harness` is imported rather than discovered.

**Why this file exists.** B2's run-wide scan used to carry its own hand-written tuple of values to
look for. Nothing connected that tuple to what the suite actually keys, so a test added later that
submitted a fourth wrong credential would have sat outside the detector silently, and nothing would
have gone red to say so (/code-review, 2026-09-10). One list, imported by everything that keys and
by the thing that scans, plus the static guard in the scanner that reads the suite's own source, is
what makes "0 occurrences" mean "none found" rather than "none looked for".

**Submitted credentials, not fragments.** `SECRETS` holds four-digit values -- the things that
actually reach `verify_pin` and are therefore credentials in CONTEXT.md's sense. `PARTIALS` holds
entries the suite keys and then clears, which never reach the system of record at all. The two are
kept apart deliberately and only the first is scanned run-wide: a two-digit needle matches any
timestamp, byte count or port number the suite happens to log, so a run-wide rule built on
fragments would either drown in false positives or be silently narrowed until it caught nothing.
Fragments are asserted precisely instead, in the one call that keys them, by
`tests/test_whole_call.py::test_no_digit_reaches_the_model_a_log_line_or_an_injected_item`.
"""
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN

#: The credential the fake accepts. Defined by the fake, not restated here, so the two cannot drift.
ACCEPTED = DEFAULT_PIN

#: Credentials the suite submits and the fake refuses. A rejected credential is no less
#: confidential than an accepted one -- a log line that recorded everything a caller tried would be
#: just as bad a leak -- so these are scanned exactly as hard as the right one.
REJECTED = ("9999", "8888", "7777")

#: Entries keyed and then cleared, which never complete and never reach the system of record. Held
#: here so they are named somewhere rather than written inline at their one call site, but see the
#: module docstring: these are deliberately *not* part of the run-wide scan.
PARTIALS = ("12", "123")

#: What the run-wide scan looks for.
SECRETS = (ACCEPTED, *REJECTED)
