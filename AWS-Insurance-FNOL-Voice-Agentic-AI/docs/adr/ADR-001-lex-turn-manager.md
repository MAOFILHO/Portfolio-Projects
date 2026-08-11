# ADR-001: Lex V2 as turn-manager, Bedrock invoked from a codehook/LangGraph — not Nova Sonic speech-to-speech, not Connect Customer's managed agentic bundle, not a hand-rolled streaming pipeline

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`CLAUDE.md`'s "What this project is" already names the stack — "Amazon Connect + Lex V2 + Bedrock +
LangGraph" — but that phrasing predates two live AWS capabilities that must be assessed on their merits
before this ADR can honestly claim Lex-as-turn-manager was chosen rather than assumed. Both were verified
today, 2026-08-11, against current AWS documentation and pricing, not memory:

1. **Amazon Nova Sonic Speech-to-Speech**, configurable directly as the voice model for a Connect
   "Conversational AI" bot locale — a real, GA, documented integration path
   (<https://docs.aws.amazon.com/connect/latest/adminguide/nova-sonic-speech-to-speech.html>), not a
   hypothetical.
2. **"Connect Customer"** — a newer, broader AWS product bundle that is **enabled by default on all new
   Connect instances**, including this project's own instance (created 2026-08-11, so it is a Connect
   Customer instance today whether or not this project uses its AI features). It offers a no-code "agentic
   customer experience designer," fully autonomous "agentic voice" AI agents, and AI-powered case
   summarization/analytics as a managed product, at what documentation states is the *same* base voice rate
   this project already uses in its cost model ($0.038/min).
   (<https://docs.aws.amazon.com/connect/latest/adminguide/enable-nextgeneration-amazonconnect.html>,
   <https://aws.amazon.com/connect/pricing/>)

Both are legitimate rejected alternatives and are assessed here rather than dismissed by assumption.

## Decision

**Lex V2 remains the turn-manager** — ASR, TTS voice selection, barge-in, DTMF, slot-elicitation state
machine, and the `sessionState`/`interpretedValue` contract already designed around in Phase 1. **Bedrock is
invoked from a Lambda codehook driving a LangGraph state graph**, not from a vendor-managed conversational
loop. This project's Connect instance remains a Connect Customer instance (it has no other option — that is
now the default), but this project **does not enable or configure any of its bundled agentic-AI
capabilities**; it uses the instance purely for the classic Connect primitives (contact flows, queues, Lex
association, Lambda invocation) this architecture already depends on.

### Alternative 1 — Nova Sonic Speech-to-Speech (rejected, for now, on a scoped and reversible basis)

AWS's own documentation states the deciding fact plainly: when a Connect bot locale is configured for
Speech-to-Speech, **"Amazon Connect continues to manage orchestration, intents, and flows."** Nova Sonic
replaces the ASR/TTS layer with a single bidirectional speech model; it does not remove the underlying bot
construct, and per the same documentation set, that construct still requires a locale, intents, and a build
step consistent with the bot/orchestration layer this project has already designed around (and already
built `ADR-007`'s IaC decision for).

**Rejected because:**
- It would not eliminate the Lex-based turn-management dependency this project's slot-filling design (Phase
  1's 11-slot `FileAutoClaim`), IaC decision (`ADR-007`), and safety-ordering decision (`ADR-010`, below) are
  all built around — so adopting it buys a different ASR/TTS engine, not a simpler architecture.
- It introduces a new integration surface (a bidirectional speech-model event contract, not the
  `ElicitSlot`/`interpretedValue` contract this project's design already assumes) with **zero prior art
  anywhere in this project's Phase 0 corpus**, and unverified interaction with the L1-before-Guardrails
  ordering constraint that `ADR-010` formalizes — the safety pre-node's placement was designed against Lex's
  turn boundary, not a continuous speech stream.
- The launch voice set is currently 4 voices (Matthew, Amy, Olivia, Lupe) — a real, if minor, constraint on
  the demo persona.

**Why this is scoped and reversible, not a closed door:** because orchestration stays with Connect either
way, swapping the ASR/TTS layer later — if voice-quality/prosody polish becomes a priority for the Phase 12
demo — would not require reopening the slot-filling, safety-ordering, or IaC decisions already made. That
follow-on work, if ever pursued, is a candidate for its own future ADR, not a Phase 2 commitment now.

### Alternative 2 — Connect Customer's managed agentic bundle (rejected on portfolio-intent grounds, not primarily cost)

Connect Customer offers a no-code "agentic customer experience designer" (ACXD) with "blended AI logic —
agentic AI reasoning and deterministic AI," fully autonomous agentic voice, and built-in AI agent
observability with LLM-as-judge evaluation — a managed product that would substitute for a meaningful share
of this project's own hand-built work: the LangGraph state graph, the custom RAG/groundedness pipeline, the
custom Bedrock Guardrails wiring, and the custom deterministic safety pre-node.

**Rejected because adopting it would defeat the project's stated purpose.** `AI-USE-CASE-CARD.md` states the
system's actual purpose plainly: *"an end-to-end agentic voice system on AWS... architecturally honest at
small scale."* `CLAUDE.md` is more direct still: *"Nothing may be stubbed out and labelled 'production would
do X here.' If it's in the README, it runs."* Building on Connect Customer's managed agentic layer instead of
LangGraph would not stub anything out dishonestly, but it would replace the engineering this portfolio exists
to demonstrate with AWS's own already-built solution to the same problem — which is a legitimate product
choice for an actual insurer, and the wrong choice for a project whose purpose is showing the work.

**This is not primarily a cost rejection**, and the ADR says so rather than reaching for a cost argument
that doesn't hold up: the fetched pricing page shows the same $0.038/voice-minute rate this project's cost
model already uses, without a confirmed separate flat fee layered on top for leaving the AI bundle
unconfigured. (Customer Basic's exact pricing was not independently located in this pass — the fetched page
did not surface it — so this ADR does not claim a cost delta either way; it rejects the bundle on engineering
scope and portfolio intent, which is dispositive regardless of the cost question.)

### Alternative 3 — hand-rolled streaming pipeline bypassing Lex entirely (rejected)

The "traditional" direct-Bedrock-streaming alternative: use Connect's media-streaming APIs to get raw audio,
run Amazon Transcribe streaming for ASR, invoke Bedrock directly, and drive Polly for TTS — all orchestrated
by hand in Lambda/LangGraph with no Lex layer at all.

**Rejected because** it would require rebuilding, from nothing, the turn-management primitives Lex V2
already provides and that this project's design already leans on: barge-in, DTMF, no-input/no-match retry
policy, and ASR confidence scoring. Phase 0 archaeology found **zero prior art** for any of these across all
eight source repos. Lex's own per-request cost ($0.004/speech request) is already the smallest line item in
the per-conversation cost model — Connect voice-minutes dominate regardless of which ASR path is used — so
there is no cost incentive to bypass it, only a large, unrewarded engineering cost.

## Consequences

**Positive:**
- The Phase 1 slot-filling design (11-slot `FileAutoClaim`), the accepted IaC decision (`ADR-007`, built
  specifically around Lex V2's `sessionState` contract), and the safety-ordering decision (`ADR-010`) all
  remain valid without rework.
- Keeping the instance as a (default) Connect Customer instance while not configuring its AI bundle costs
  nothing extra per the verified pricing and preserves the option to adopt specific Connect Customer
  capabilities later (e.g., its AI agent observability tooling) as an additive enhancement, without having
  built the core agent on top of it.

**Negative / accepted residual risk:**
- Forgoes Nova Sonic's more natural conversational prosody and interruption handling — a real, if modest,
  demo-polish cost of this decision, recorded honestly rather than implied away.
- Forgoes the faster time-to-first-working-bot that a no-code managed agentic layer would offer — deliberately,
  since the point of this portfolio is the custom engineering, not the fastest path to a working demo.
- If a future phase revisits ASR/TTS quality, Nova Sonic remains a live, low-switching-cost option precisely
  because this ADR did not entangle it with the orchestration layer.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Nova Sonic Speech-to-Speech (Connect bot locale) | Rejected, reversible | Only replaces ASR/TTS — orchestration stays Connect/Lex-managed either way; new event contract with zero prior art and unverified safety-ordering interaction |
| Connect Customer managed agentic bundle (ACXD, agentic voice) | Rejected | Would substitute AWS's managed solution for the hand-built engineering this portfolio exists to demonstrate — a portfolio-intent rejection, not primarily a cost one |
| Hand-rolled Transcribe+Bedrock+Polly streaming, no Lex | Rejected | Rebuilds mature Lex turn-management primitives from zero prior art, for no cost benefit (Lex is already the smallest cost line item) |
| **Lex V2 turn-manager + Bedrock via LangGraph codehook** | **Chosen** | Preserves all prior Phase 1/ADR-007/ADR-010 design work; matches the project's stated purpose of demonstrating the engineering, not buying a managed replacement for it |

## Sources

- <https://docs.aws.amazon.com/connect/latest/adminguide/nova-sonic-speech-to-speech.html>
- <https://docs.aws.amazon.com/connect/latest/adminguide/enable-nextgeneration-amazonconnect.html>
- <https://aws.amazon.com/connect/pricing/>
- <https://aws.amazon.com/about-aws/whats-new/2025/04/amazon-nova-sonic-speech-to-speech-conversations-bedrock/>
- <https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-nova-2-sonic-real-time-conversational-ai>

All facts above were fetched live on 2026-08-11. Connect Customer Basic's exact pricing was not located in
this pass and is not asserted; the rejection of Alternative 2 does not depend on it.
