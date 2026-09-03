# ADR-018: Application tracing — ADOT collector exporting to AWS X-Ray, not Langfuse; span boundary set at the LangGraph node, not the Lambda handler

**Status:** Accepted (Phase 14). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-21

---

## Context

Two facts, on record before this ADR, that made this a decision rather than a default:

1. `docs/phase8/EXISTING-INSTRUMENTS.md` instrument #10 named the gap explicitly at Phase 8: *"AWS X-Ray,
   OTel node tracing, planned — defer to Phase 11 on its merits."*
2. Phase 11 ("Observability and operations," ✅ closed) built **cost observability only** — a budget alarm,
   an SNS topic, a Cost-Explorer-pull dashboard (`infra/terraform/stacks/observability/`). It never picked
   the deferred tracing item back up. There is currently no way to see *inside* a turn: which LangGraph node
   ran, how long the Bedrock call took, whether an MCP tool call was on the critical path. The only latency
   number this project has ever published (`docs/phase9`'s p95 measurement) comes from wrapping the whole
   Lambda invocation in a timer, not from a trace — it can say a turn was slow, never where the time went.

Marco asked (2026-08-21) whether this project has observability "from the start." The honest answer was:
one kind, and not this kind.

Marco's direction, binding on this ADR: **AWS-native — ADOT collector exporting to X-Ray, not Langfuse. If
AWS doesn't have a free/lowest-cost SKU fit, Langfuse is the fallback (API keys provided).**

## Decision

**ADOT (AWS Distro for OpenTelemetry) Lambda layer, exporting to X-Ray. Langfuse is not used.**

### Why AWS has a fit, so the Langfuse fallback is not triggered

Per `PROJECT_STATE.md`'s Phase 14 cost table (verified against the current AWS CloudWatch pricing page,
2026-08-21): the first 100,000 traces recorded/month and first 1,000,000 traces retrieved/month are free;
beyond that, $0.000005/trace recorded and $0.0000005/trace retrieved. At this project's demo volume
(~100 calls/month), every SKU in this phase prices at $0.00. A free/lowest-cost fit exists, so the
Langfuse fallback condition never fires.

### Why AWS-native over Langfuse, stated as a trade the project accepts

- **Keeps trace data inside the account boundary.** Every other sink this project has (structured logs,
  transcripts, the Phase 11 dashboards) already lives inside the AWS account. X-Ray extends that boundary
  instead of opening a new one, which means `ADR-011`'s redaction rule ("Application logs / traces /
  metrics: Redacted") already covers this sink by name — it does not need to be re-litigated for a new
  destination the way a third-party sink would require.
- **No new secret.** Langfuse needs an API key provisioned and rotated under this project's "no secrets in
  code" rule. X-Ray needs only IAM permissions the Lambda execution role already has a natural home for.
- **The trade, named rather than hidden**: X-Ray gives span-level latency (this phase's actual target — the
  constraint-14 1,800ms turn budget) but not LLM-native concepts — prompt/completion pairs, per-generation
  token cost, eval-linked traces — the way Langfuse would. Accepted as a scope limitation of this phase, not
  rediscovered later as a gap. A future phase that wants LLM-native tracing is a new decision, not a silent
  extension of this one.

### Span boundary: per LangGraph node, not one opaque Lambda span

A trace that wraps the whole handler in one span answers "did it run," not "where did the 1,800ms go" — the
question this phase exists to answer (`docs/phase9`'s p95 gap, restated in the Phase 14 exit criteria).
Spans are set at:

- the Lex codehook invocation (the trace root),
- each LangGraph node (so a slow node is individually attributable),
- each Bedrock `Converse` call (router classification and generation, separately — they run on different
  models with different latency profiles, `ADR-004`),
- each MCP tool call (per `ADR-012`, these are in-process Python function calls, not a wire round-trip — the
  span wraps the function call itself, not a network hop; nothing about `ADR-012`'s transport decision
  changes here, tracing an in-process call the same way tracing an RPC would just makes the function
  boundary visible in the same tool).

### Span attributes carry IDs and metrics, never raw content

Per `ADR-011`'s existing redaction boundary, restated here for the new sink rather than assumed to apply
automatically (`D124`/`OI46`'s lesson: an unenumerated sink is exactly where a PII leak hides): span
attributes are `contactId`, node name, model ID, latency, token counts, guardrail action. No span attribute
ever carries caller utterance text, generated response text, or slot values.

## Consequences

- Turn latency can finally be measured from real trace data against the 1,800ms budget, closing a gap named
  twice (Phase 8, Phase 9) and deferred both times.
- A future regression in instrumentation coverage is a failing `make verify-*` check, not a silently
  incomplete trace discovered later — same convention as every other `scripts/verify_*.py` gate in this
  project.
- LLM-native tracing (prompt/completion pairs, per-generation cost, eval-linked traces) remains unbuilt.
  Named here as the reason a future phase might reconsider Langfuse — not a defect in this one.
- The ADOT Lambda layer is AWS-managed and billed only as ordinary Lambda invocation/duration already inside
  this project's existing Lambda cost — no new always-on resource, no idle charge, nothing that can accrue
  cost silently if teardown is forgotten (the `D64` budget-alarm failure mode this project's own dashboard
  exists to catch does not apply to a pure pay-per-trace SKU with no minimum).

## Alternatives considered

**Langfuse** (the named fallback). Rejected because the fallback's own trigger condition — no AWS
free/lowest-cost fit — does not hold. Kept on record as the documented fallback if X-Ray pricing or scope
ever stops fitting this project's demo volume.

**One opaque span per Lambda invocation.** Rejected: it would satisfy "a trace exists" but not this phase's
actual purpose, which is finding where inside the 1,800ms budget the time goes. Explicitly named in the
Phase 14 exit criteria (criterion 3) as not meeting the bar.

**OTel SDK direct to a self-hosted or third-party OTLP collector.** Not considered seriously: it reopens the
same account-boundary and secret-management questions as Langfuse, for a destination with no offsetting
LLM-native benefit over Langfuse itself.
