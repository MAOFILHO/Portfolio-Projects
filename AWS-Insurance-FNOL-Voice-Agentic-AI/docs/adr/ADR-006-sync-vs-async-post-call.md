# ADR-006: Post-call processing runs asynchronously off an EventBridge contact-lifecycle event, not synchronously on the call path

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

Everything that happens *after* a call ends — full-transcript PII redaction (beyond what already happened
turn-by-turn), persistence of the redacted transcript and structured claim record, the turn-by-turn reasoning
trace, tool-call log, cost/latency rollup, soft fraud/consistency flags, and eval-sample selection — has to
run somewhere. The question is whether any of it runs on the call path (blocking call teardown) or entirely
after the call has already ended, triggered by an event.

Verified today: Amazon Connect publishes contact lifecycle events — `DISCONNECTED` and `COMPLETED` among
them — to Amazon EventBridge as `"detail-type": "Amazon Connect Contact Event"`, `"source": "aws.connect"`,
independently of any analytics feature.
(<https://docs.aws.amazon.com/connect/latest/adminguide/contact-events.html>) This is **not** Contact Lens:
Contact Lens conversational analytics is a separate, explicitly-configured block
(`contactLens.conversationalAnalytics`, off unless a flow sets it) that this project never enables, per
constraint 18's ban on `AnalyticsBehavior`/`ContactLens`/`RealTimeContactAnalysis`. The plain lifecycle-event
stream used here carries none of that and requires no analytics feature to be turned on.

One honest caveat surfaced by the same source: **these events are delivered "on a best-effort basis"** — no
delivery guarantee. That fact directly shapes the reliability posture below.

## Decision

**Fully asynchronous.** No post-call processing runs on the call path. A single Lambda function, subscribed
via an EventBridge rule matching `source: aws.connect`, `detail-type: "Amazon Connect Contact Event"`,
`detail.eventType: "DISCONNECTED"` (or `"COMPLETED"` where After Contact Work applies), performs the full
post-call pipeline: redact → persist → emit metrics/trace → compute soft flags → select for eval sampling.
An SQS dead-letter queue captures failures for retry, rather than a multi-step Step Functions workflow.

**Nothing about call teardown waits on this pipeline.** The call has already fully disconnected before this
Lambda is even invoked — by construction, since the trigger *is* the disconnect event, not something the
call itself calls out to before hanging up. This means post-call processing latency has **zero relationship**
to the 1,800 ms p95 per-turn budget: the two are already fully decoupled by the mechanism itself, not by a
design promise that could be violated.

### Why not synchronous (rejected)

Running redaction/persistence in the Set Disconnect Flow before Connect is allowed to fully release the
contact would gain nothing for the caller — they've already hung up or been transferred — while adding a
new latency-sensitive dependency to contact teardown itself, and duplicating work Connect's own event
mechanism already exists to decouple. There is no requirement anywhere in `PROBLEM-FRAMING.md` or
`SUCCESS-METRICS.md` that post-call artifacts exist within any bounded time of call end; the closest
requirement is that a redacted transcript and reasoning trace exist and are reviewable, which an async
pipeline satisfies just as well, on a "shortly after" basis instead of "at the instant of."

### Why a single Lambda, not Step Functions (scope decision within "async")

The pipeline is currently five sequential, non-branching steps (redact, persist, emit, flag, sample) with no
distinct retry semantics per step at this project's scale — a handful of demo/simulator calls, not a
production volume. Step Functions Standard would add a second IaC construct and a per-transition cost
(trivial at this volume, but non-zero complexity) for a benefit — per-step observability and independent
retry — that a single Lambda with structured exception handling and an SQS DLQ already provides adequately.
**This is a scope threshold, not a permanent position:** if the pipeline grows past roughly three or four
steps with genuinely different retry/branching needs (e.g., a step that must wait on an external system, or
one that fans out), that is the trigger to revisit this ADR with a new one — recorded here so the threshold
is explicit rather than left to be rediscovered under pressure later.

### The best-effort delivery caveat, and what does and doesn't get done about it

AWS's own documentation states contact events are delivered best-effort, not guaranteed. **This project
accepts that risk rather than eliminating it**, for a stated reason: post-call artifacts (redacted
transcript, trace, soft flags) are operationally useful and reviewable, but nothing in this system's safety
model depends on them existing for every call. The safety-critical path — injury escalation — is a
deterministic **in-call** pre-node (`D12`, formalized in `ADR-010` below) that does not depend on post-call
processing at all; a dropped post-call event cannot cause a missed escalation, only a missing dashboard
entry for an otherwise-completed call.

**What is done about it:** the Lambda's processing is idempotent, keyed on `contactId` — reprocessing the
same event twice (which best-effort delivery can also cause, via duplicate delivery) produces the same
stored artifacts, not duplicates. **What is explicitly not built in Phase 2:** a durable secondary path via
Contact Trace Records (CTR) over a Kinesis Data Stream, which would catch anything the best-effort
EventBridge event drops. This is recorded as a candidate follow-up if the observability dashboard (Phase 11)
ever shows a material gap between calls made and post-call artifacts produced — not built preemptively for a
demo-scale prototype where that gap, if it exists at all, is expected to be a rounding error.

## Consequences

**Positive:**
- Post-call latency is structurally decoupled from the 1,800 ms per-turn budget — not by a promise, but
  because the trigger only fires after the call has already ended.
- No analytics feature banned by constraint 18 needs to be enabled to get this event stream.
- Single Lambda + EventBridge rule + SQS DLQ is the minimum IaC footprint that satisfies the requirement,
  consistent with the project's cost-and-complexity minimalism at demo scale.

**Negative / accepted residual risk:**
- Best-effort event delivery means a small, unquantified fraction of calls may not get post-call artifacts
  persisted. Accepted because nothing safety-critical depends on this path, and mitigated only by
  idempotency, not by a guaranteed-delivery fallback — that fallback (CTR/Kinesis) is deferred, not omitted
  by oversight.
- If eval-sample selection depends on this pipeline running for *every* call to have a representative
  sample, a systematic (rather than random) best-effort drop pattern could bias the eval set. This is a
  real, if currently unquantified, risk — flagged for Phase 6 (eval harness) to check for, not assumed away.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Synchronous processing before call teardown completes | Rejected | No benefit to the caller (already disconnected); adds a new latency-sensitive dependency to teardown for no requirement that demands it |
| Step Functions Standard workflow | Rejected for now | Pipeline is five non-branching steps at demo scale — a single Lambda + DLQ is adequate; revisit if branching/step-specific retry needs grow |
| **Single async Lambda via EventBridge contact-event rule** | **Chosen** | Minimum footprint satisfying the actual requirement; fully decoupled from the per-turn latency budget by construction |
| Durable CTR/Kinesis secondary path for guaranteed delivery | Deferred, not rejected | No evidence yet that best-effort delivery loses a material fraction of calls at this project's scale; revisit if Phase 11 dashboards show a gap |

## Sources

- <https://docs.aws.amazon.com/connect/latest/adminguide/contact-events.html>

Fetched live on 2026-08-11. The best-effort delivery caveat and the exact `DISCONNECTED`/`COMPLETED` event
semantics are quoted from this source rather than assumed from memory.
