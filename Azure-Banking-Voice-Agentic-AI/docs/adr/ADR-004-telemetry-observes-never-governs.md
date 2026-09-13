# ADR-004 — Telemetry observes this system; it never governs it

Status: **Accepted** — settled in the Phase 6 design session, 2026-09-11
(`docs/phase6/exit-criteria.md` D9, D11), implemented by issue #61.
Date: 2026-09-13

## Context

Phase 6 gives this project its first telemetry surface: one OpenTelemetry trace per call, with
child spans for turns, tool calls and core-banking requests, plus two metrics for B4 and B5. Two
questions came up in the same design session and turned out to be one question asked twice.

**D9 — what stops a future attribute from carrying something B2 forbids?** The obvious answer is a
scrubber: inspect every value on its way out and redact anything that looks like a credential. That
answer was rejected. A pattern-matching scrubber has to be right about every attribute every future
instrumentation ever adds, and a regex can silently half-work — it looks like protection and is not,
which is a worse failure than an honestly absent one. The alternative is a **deny-by-default
allowlist**: a fixed, written table of permitted attribute keys (`docs/phase6/exit-criteria.md`
D15), enforced by one `SpanProcessor` that drops anything not on it, without ever looking at a
value. Widening the surface means editing the table first, which is a reviewable diff rather than a
runtime decision a regex made on its own.

**D11 — what happens when the exporter is slow, unreachable, or wrong?** B4 fails closed, and it is
adversarially tested for it: a call that cannot confirm its budget does not get served. Telemetry
was designed to do the opposite on purpose. An exporter that blocked a turn while an ingestion
endpoint was slow would be observability actively damaging the thing it exists to observe, and in
the worst case — an exporter whose failure took the call down with it — would mean a call dropped
*in order to record that a call happened*.

Both questions cash out the same way: **nothing this phase adds is allowed to become load-bearing
for anything the project already promises.** The allowlist is defence in depth around a promise
(B2) that is enforced elsewhere (D8: the caller's phone number is protected by never reading it off
the `IncomingCall` event at all — the scan, and the allowlist behind it, are the net, not the
control). The fail-open exporter is what keeps a brand-new, still-unproven code path from being able
to touch B4, B1, or any other named constraint. Recording them as two ADRs would describe the same
decision twice from two entry points; recorded as one, the underlying rule is visible: **telemetry
observes this system, and it never governs it.**

## Decision

Telemetry never decides anything, and nothing in this codebase may ever make it decide something,
even by accident, even later:

1. **The auth gate is still the only control.** `dispatch/gate.py`'s `is_allowed` is unchanged by
   this phase. The "tool call" span records the gate's decision (`gate_decision`: allowed/denied)
   *after* the gate has already decided — a span is a record of what happened, never an input to
   what happens next.
2. **The allowlist filter (`AllowlistSpanProcessor`) is a net, not the control**, exactly as D9
   states for the parallel case in the glossary (the auth gate decides; everything else is defence
   in depth). It drops keys, never inspects values, and its default for anything it does not
   recognise — an unlisted attribute key, or a span name outside D15's four — is to keep nothing at
   all.
3. **The exporter fails open, unconditionally.** `build_tracer_provider` wires every real exporter
   behind a `BatchSpanProcessor`, never a synchronous one — the same choice that makes "never
   raises" and "never delays a turn" one property instead of two, because the actual network call
   happens on a background thread the request-handling coroutine never waits on. An unreachable
   endpoint, a refused connection, or an exporter that raises on every call all degrade to
   "nothing got exported this time," never to "the call behaved differently."
4. **`telemetry.configure()`'s default is a no-op provider**, not a stub that silently drops calls
   into a queue somewhere. Before it is ever called — and in every test that never calls it — every
   function in `observability/telemetry.py` is a true no-op: zero allocation beyond an SDK no-op
   span/instrument, and no path back into the call at all.
5. **Metrics carry no per-call attributes.** B4's daily-minutes counter and B5's turn-latency
   histogram are recorded with no dimensions, deliberately, so there is no metrics-side allowlist
   question to get wrong later and no per-call value to reconstruct from an aggregate.

## Consequences

- **A blocking CI test proves it, not just this document.** `tests/test_telemetry.py`'s
  `NoConstraintIsEnforcedByTelemetry` re-runs a gate refusal and a B4 turn-cap trip with telemetry
  configured and with it absent, and asserts the two runs are identical. Every other B1/B2/B4 suite
  in this project (`test_gate.py`, `test_zz_b2_leak_scan.py`, `test_whole_call.py`'s cap tests)
  proves the same thing by never calling `telemetry.configure()` at all — this project's default
  posture is telemetry-absent, not telemetry-present-but-quiet.
- **A future ticket that wants telemetry to gate something is proposing a different architecture,
  not an extension of this one.** Anything resembling "refuse the call if the exporter reports X",
  "read the trace to decide the next turn", or "let a metric threshold trip a cap" is out of scope
  by this decision and needs its own sign-off, the same way B1/B2/B4's own wording does not move
  without Marco's explicit approval (`CLAUDE.md`).
- **The allowlist table is the only place a new fact gets added to a span**, and every widening is
  visible in a diff (`docs/phase6/exit-criteria.md` D15's own closing line: "Any future addition is
  an explicit edit to this table, which is the entire point of deny-by-default"). A `set_attribute`
  call on a key not yet in the table is silently discarded, not silently exported — the failure mode
  of forgetting the edit is invisible telemetry, never a leak.
- **Provisioning a real exporter (issue #62) inherits this ADR rather than revisiting it.** Whatever
  Application Insights instance #62 points at, and whichever of the identity/connection-string
  paths it actually uses, arrives already behind the fail-open `BatchSpanProcessor` and the
  allowlist filter this ADR is about — #62's job is choosing where the (already-safe) data goes, not
  deciding whether it is allowed to affect the call.
