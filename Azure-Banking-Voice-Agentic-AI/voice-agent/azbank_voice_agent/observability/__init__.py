"""Phase 6 (Observability, issue #61): one OpenTelemetry seam, wired once at boot.

Same shape as `core_banking/`, `call_records/`, `transport/` and `realtime/` in one respect and
different in another: it is one module wide (`telemetry.py`) because there is no real/fake split to
make here -- the seam *is* the TracerProvider/MeterProvider boundary itself (`docs/phase6/exit-
criteria.md` D17, issue #61's own "Implementation Decisions"). Production attaches a real exporter
behind it; tests attach an in-memory one at the exact same point. No new test double is needed, and
none is added -- the four existing fakes (`transport/fake.py`, `realtime/fake.py`,
`core_banking/fake.py`, `call_records/fake.py`) already drive every fake-call path this rides on.

**Telemetry observes this system; it never governs it** (ADR-004, D11+D9). Every named constraint
(B1, B2, B4) holds identically with this package's exporter unreachable, or with `telemetry.configure()`
never called at all.
"""
