# ADR-010: L1 safety pre-node runs before any Bedrock Guardrails input evaluation — implemented by never attaching `guardrailIdentifier` to a model-invocation call, driving `ApplyGuardrail` explicitly instead

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

Promoted from Q8 at Marco's explicit instruction during Phase 1 sign-off: *"safety-detection ordering is
architecture, not an implementation note."* The concern is concrete and was stated plainly in Phase 1: **an
input filter that blocks a graphic injury description before the L1 safety pre-node ever sees it would
defeat the detector.** Phase 1 committed to "L1 runs before Guardrails input filtering" as a design
intention. This ADR had to answer a question Phase 1 left open: **is that even something Bedrock's own
Guardrails mechanism allows, or does attaching a guardrail to a model call force it to run first,
unconditionally, with no hook for an application to interpose its own check?**

### What was verified today

Bedrock Guardrails has **two distinct integration modes**, confirmed from current AWS documentation:

1. **Inline/bolted-on mode** — passing `guardrailIdentifier`/`guardrailVersion` directly to
   `Converse`/`ConverseStream`/`InvokeModel`. In this mode, AWS's own docs state the input is evaluated
   automatically, "in parallel for each configured policy," and if blocked, "the foundation model inference
   is discarded" — **entirely inside that one API call, with no hook for an application to run its own logic
   between the guardrail check and the model seeing the prompt.** If this project attached a guardrail this
   way, Phase 1's stated concern would be real and unavoidable: the input filter would run first,
   unconditionally, before L1 ever got a chance.
   (<https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html>)
2. **Standalone/decoupled mode — `ApplyGuardrail`** (and the newer, 2026 `InvokeGuardrailChecks`). AWS's own
   language: *"You can use the `ApplyGuardrail` API to assess any text using your pre-configured Amazon
   Bedrock Guardrails, **without invoking the foundation models**... decoupled from foundation models...
   integrate the `ApplyGuardrail` API anywhere in your application flow."*
   (<https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html>) The 2026
   `InvokeGuardrailChecks` API goes further, explicitly targeting agentic control flows — resourceless,
   detect-only, checkable "at any point"/"any turn in the agentic loop," with prompt-attack detection split
   into its own checkable unit separate from content filters.
   (<https://aws.amazon.com/blogs/machine-learning/safeguard-your-agentic-ai-applications-with-the-amazon-bedrock-guardrails-invokeguardrailchecks-api/>)

**This resolves the open question decisively: the ordering this project needs is not a request to AWS for
special behavior — it is the standard, AWS-documented pattern for exactly this use case**, as long as this
project does not use mode 1.

## Decision

**Bedrock model invocations in this project never carry a `guardrailIdentifier`/`guardrailVersion`
parameter.** Guardrails input evaluation is driven explicitly, as its own graph node, called via
`ApplyGuardrail` (or `InvokeGuardrailChecks` if its capabilities — separated prompt-attack detection in
particular — prove useful once implemented in Phase 5), and it is **sequenced after L1 in the LangGraph
state graph, not before it.**

**Concrete graph ordering, every turn:**

1. **L1 — deterministic injury/fatality pre-node** runs first, on the raw turn input, before anything else
   touches it. Union semantics with L2/L3 per `D15`; this ADR only fixes L1's position relative to
   Guardrails, not the layered-detection design itself, which `D15`/`AI-USE-CASE-CARD.md` already cover.
2. **Guardrails input evaluation (`ApplyGuardrail`, `source: INPUT`)** runs second, as an explicit graph node
   — not automatically, not bolted onto the model call that follows.
3. **The model invocation itself** (`Converse`, no `guardrailIdentifier` attached) runs third, only if steps
   1–2 did not already terminate the turn (L1 escalating, or Guardrails blocking).
4. **Guardrails output evaluation (`ApplyGuardrail`, `source: OUTPUT`)** runs on the model's response before
   it is handed to Polly/Lex for speech synthesis.

**Why this specific ordering and not "Guardrails first, L1 second":** a Guardrails content filter has no
concept of this project's specific escalation requirement — it might legitimately flag a graphic injury
description as violent/distressing content and block it, which is exactly Phase 1's named failure mode (F1
in `AI-USE-CASE-CARD.md`). L1 is deterministic and injury-specific; it must see the caller's actual words
before any general-purpose content filter has a chance to intercept them. Running Guardrails second means a
blocked-content result on the *same turn* is still informative (this project's L1 has already made its
escalation decision by that point, so a Guardrails block afterward affects only whether the model gets to
respond normally — it cannot suppress an escalation that already happened).

## Consequences

**Positive:**
- The ordering Phase 1 required is now a verified-implementable architecture decision, not an aspiration
  resting on an unconfirmed assumption about how Guardrails works.
- Because `ApplyGuardrail` is explicitly designed for this kind of decoupled use, this project is not fighting
  the platform to get the ordering it needs — it is using the documented, intended integration pattern.
- The newer `InvokeGuardrailChecks` API's separated prompt-attack detection is a candidate to strengthen F5
  (prompt injection via retrieved documents/tool responses) in a later phase, without needing to restructure
  this ordering decision.

**Negative / accepted residual risk:**
- Bypassing the bolted-on mode means this project owns the sequencing logic itself — a bug in the graph that
  skips or reorders the `ApplyGuardrail` node is now an application defect, not something Bedrock enforces
  automatically. This is accepted because it's the only way to get the required ordering at all, and it is
  exactly the kind of ordering-as-code decision `ADR-006`/`ADR-011` already commit this project to elsewhere.
- `ApplyGuardrail`'s exact pricing was confirmed for content/denied-topics ($0.15/1k units) and PII/contextual
  grounding ($0.10/1k units), but **Automated Reasoning checks pricing (~$0.17, exact unit unconfirmed) and
  `InvokeGuardrailChecks` pricing were not found in this research pass** — flagged for the Phase 2 cost model
  rather than asserted.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Attach `guardrailIdentifier` directly to `Converse`/`InvokeModel` (inline mode) | Rejected | Confirmed to run unconditionally, in parallel, with no hook to run L1 first — would directly reproduce Phase 1's named failure mode (F1) |
| No Guardrails input check at all, rely on L1+L2+L3 alone | Rejected | `CLAUDE.md` requires Guardrails on input **and** output; L1/L2/L3 are safety-specific, not a substitute for general content/PII/injection filtering |
| **`ApplyGuardrail`/`InvokeGuardrailChecks` as an explicit graph node, sequenced after L1** | **Chosen** | The AWS-documented pattern for exactly this decoupled-ordering requirement; verified today, not assumed |

## Sources

- <https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html>
- <https://aws.amazon.com/blogs/machine-learning/implement-model-independent-safety-measures-with-amazon-bedrock-guardrails/>
- <https://aws.amazon.com/blogs/machine-learning/safeguard-your-agentic-ai-applications-with-the-amazon-bedrock-guardrails-invokeguardrailchecks-api/>
- <https://aws.amazon.com/about-aws/whats-new/2024/12/amazon-bedrock-guardrails-reduces-pricing-85-percent/>

All facts fetched live on 2026-08-11 via a background research agent, per the project's standing rule to
verify against current sources rather than memory.
