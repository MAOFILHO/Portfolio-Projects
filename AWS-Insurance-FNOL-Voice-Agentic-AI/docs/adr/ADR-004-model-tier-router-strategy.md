# ADR-004: Model tier and router strategy — fixed cheap tier for routing/L2 safety (merged into one call), feature-flagged tier for generation only; L2 is architecturally non-optional

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`PROJECT_STATE.md`'s Phase 2 ADR list attaches a specific requirement to this decision: *"Must account for
L2's per-turn safety classifier as non-optional (Q10)"* — Q10 itself reads: *"L2's per-turn classifier must
not be switchable off by the model-tier feature flag. A config change meant to alter the generation tier
must not be able to disable a safety detector."* Any router design that uses one flag or one dial to control
"which model runs this turn" would violate that requirement by construction. This ADR has to produce a
router architecture where that is structurally impossible, not merely policed by convention.

Pricing was re-verified today rather than trusted from `CLAUDE.md`'s existing table (itself now corrected —
see the same-day edit to that file):

| Model | Input $/1M tok | Output $/1M tok |
|---|---|---|
| `us.amazon.nova-micro-v1:0` | $0.035 | $0.14 |
| `us.amazon.nova-lite-v1:0` | $0.06 | $0.24 |
| `us.anthropic.claude-3-haiku-20240307-v1:0` | $0.25 | $1.25 |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | $1.00 | $5.00 |

Cross-region inference profiles (the `us.*` prefix, mandatory per constraint 17) carry **no price
surcharge** — confirmed against current AWS documentation, not assumed.

**The one thing this pricing table settles immediately: cost cannot be the deciding factor here.** At this
project's per-conversation token volume (roughly 6k input / 1k output tokens, per the Phase 0 cost model),
even the most expensive candidate — Claude Haiku 4.5 — costs a fraction of a cent per conversation. The
existing project finding that "Bedrock is noise" next to telephony cost holds regardless of which tier wins.
This ADR is therefore a **capability-fit decision**, not a cost decision, and says so rather than reaching
for a cost justification that wouldn't actually bind.

## Decision

**Two structurally separate call paths, not one router with a single tier dial:**

### 1. Routing + L2 safety classification — fixed tier, merged into one call, never flag-controlled

Every turn, after L1's deterministic pre-node (which is not a model call at all, per `D12`) has run and not
already escalated, **one** `us.amazon.nova-micro-v1:0` call performs both intent/slot-routing classification
and L2's recall-biased safety classification, via **forced tool-use with a required `safety_flag` field** —
not lenient JSON-by-prompting. This merges what would otherwise be two sequential round-trips into one,
which matters directly against the 1,800 ms turn budget once L1, this call, `ApplyGuardrail` input
evaluation (`ADR-010`), the generation call, and `ApplyGuardrail` output evaluation are all counted as
sequential steps on the same turn.

**Why forced tool-use specifically, and why it matters more here than elsewhere:** Phase 0 archaeology
already identified forced tool-use (`toolChoice`) as superior to prompting for structured output in general.
Merging two responsibilities into one call raises a *specific* risk this ADR names directly: if the safety
flag were just another field the model might mention in prose, a model distracted by the intent-classification
half of the same prompt could silently omit it. A schema-required tool-call field cannot be silently omitted
without the call itself failing validation — which is the mechanism, not just the intention, behind Q10's
"non-optional" requirement holding for the merged call specifically.

**This call path is fixed to Nova Micro, permanently, not exposed to the generation-tier feature flag at
all.** There is no shared config key between "which model classifies this turn" and "which model generates
the response" — they are different flags in different namespaces, so a change to one cannot, by
construction, affect the other. Nova Micro is chosen for this path because it is the cheapest and fastest
tier, appropriate for a narrow classification task that must not add material latency to a budget that also
has to fit a generation call afterward.

### 2. Generation — feature-flagged tier, Phase 6 decides the winner, this ADR fixes the mechanism only

The dialogue-response/RAG-synthesis node (empathetic phrasing, coverage-answer synthesis, the
`RentalTowingEntitlement` compound-reasoning response) runs behind an OpenFeature flag defaulting to
`us.amazon.nova-lite-v1:0`. `PROJECT_STATE.md`'s Q2 already states this correctly: *"Does
`us.anthropic.claude-haiku-4-5` earn its cost over `us.amazon.nova-lite` on the generation node? Decided by
Phase 6 evals, not preference."* This ADR does not pre-empt that — it fixes that the mechanism for switching
is a feature flag scoped only to this node, takes effect on the next turn (per the existing kill-switch
design in `AI-USE-CASE-CARD.md`), and cannot reach the routing/L2 call path above.

**Claude 3 Haiku is pruned from the Phase 6 eval matrix, with reasoning stated rather than silently
dropped.** At $0.25/$1.25 per 1M tokens, it costs roughly 4× Nova Lite while being an older, less capable
model than Claude Haiku 4.5, which itself costs only ~4× Claude 3 Haiku. It is strictly dominated in this
project's specific comparison: nothing it could win on (quality) beats Haiku 4.5, and nothing it could win on
(cost) beats Nova Lite. Phase 6 evaluates **{Nova Lite, Claude Haiku 4.5}** on the generation node, not all
four models — unless a specific reason to include Claude 3 Haiku emerges before Phase 6 begins, which this
ADR does not anticipate.

## Consequences

**Positive:**
- Q10's requirement is satisfied structurally — the generation-tier flag has no code path to the
  routing/L2 call, not merely a convention not to wire them together.
- Merging routing and L2 into one call removes a full round-trip from the per-turn latency budget, which
  matters more once Guardrails' now-explicit `ApplyGuardrail` calls (`ADR-010`) are also counted as
  sequential steps on the same turn.
- The Phase 6 eval matrix is scoped to two real candidates instead of four, with the pruning reasoned rather
  than silently assumed.

**Negative / accepted residual risk:**
- A single merged call means a failure in that call (throttling, malformed tool response) affects both
  routing and safety classification simultaneously, rather than being independent failure modes. This is
  accepted because L1's deterministic pre-node and L3's caller-barge-in remain independent, union-combined
  detection layers (`D15`) — a merged-call failure does not remove all safety coverage for that turn, only
  L2's contribution to it.
- If Phase 6 ever needs the router and the safety classifier to run on different models (e.g., because one
  needs a larger model and the other doesn't), the merged-call design would need to be split apart — recorded
  as a design cost of the current optimization, to be paid only if evidence requires it.

## Alternatives considered

| Alternative | Verdict | Deciding factor |
|---|---|---|
| Single feature flag controlling "the model" for the whole turn | Rejected | Directly violates Q10 — a generation-tier change could disable L2 as a side effect |
| Separate sequential calls for routing and L2 | Rejected | Two round-trips against the same latency budget for no capability gain over one merged, schema-forced call |
| Evaluate all four models on the generation node | Rejected | Claude 3 Haiku is strictly dominated by Nova Lite (cost) and Claude Haiku 4.5 (quality) in this project's specific pricing |
| **Fixed Nova Micro for merged routing+L2; feature-flagged Nova Lite/Claude Haiku 4.5 for generation, decided by Phase 6 evals** | **Chosen** | Satisfies Q10 structurally; leaves the generation-tier decision to evidence, not preference |

## Sources

- <https://aws.amazon.com/bedrock/pricing/> and the AWS Price List API (`AmazonBedrock`, us-west-2), fetched live 2026-08-11
- <https://platform.claude.com/docs/en/about-claude/models/overview> (Claude Haiku 4.5 Bedrock pricing, exact model-ID match)
- <https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html> (no cross-region surcharge)
- <https://aws.amazon.com/blogs/machine-learning/getting-started-with-cross-region-inference-in-amazon-bedrock/>

Claude Haiku 4.5's exact price was not independently re-confirmed against the AWS Price List API itself
(which omitted all modern Anthropic models from its live us-west-2 dump on 2026-08-11) — sourced instead from
Anthropic's own documentation by exact Bedrock model-ID match. Flagged, not hidden.
