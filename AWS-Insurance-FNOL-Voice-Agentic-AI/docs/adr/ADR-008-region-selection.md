# ADR-008: Region selection — `us-west-2`, with a documented residency caveat on Bedrock cross-Region inference

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

Constraint 17 in `CLAUDE.md` already mandates a single region: Connect, Lex V2, Lambda, DynamoDB, S3 and
Step Functions all live in `us-west-2`; Bedrock is invoked via US cross-region inference profiles (`us.*`),
never a hardcoded regional model ID, because `amazon.nova-micro-v1:0` supports only `INFERENCE_PROFILE`.
This ADR exists to make that decision an artifact — with the alternatives actually assessed on the merits,
current sources cited, and one real gap in the "single region" framing written down rather than glossed
over — per PROJECT_STATE.md's stated purpose for ADR-008: *"Exists to prevent a repeat of a prior project's
full teardown."*

Three things needed live verification before this could be written honestly, per the project's standing
rule to verify AWS capability/pricing claims against current sources rather than memory:

1. Whether Bedrock AgentCore's region-count limits are as narrow as commonly stated, since AgentCore is a
   rejected alternative to LangGraph and region fragmentation is part of that rejection's evidence.
2. Whether a Bedrock `us.*` cross-region inference profile invoked *from* `us-west-2` can actually be
   processed in a different physical AWS region — and if so, what that means for a "single region" claim.
3. Whether `ca-central-1` — relevant only because the pre-existing DID is a Canadian number — has any
   technical gap that would make it a live alternative, or whether the DID's country code is a red herring.

## Decision

**`us-west-2` remains the single region for Connect, Lex V2, Lambda, DynamoDB, S3 and Step Functions.**
Bedrock continues to be invoked exclusively via `us.*` geographic cross-region inference profiles, per
constraint 17 — unchanged. What this ADR adds is a precise, sourced statement of what that guarantees and
what it does not, plus the formal rejection of `ca-central-1` and Bedrock AgentCore as alternatives.

### 1. The `us.*` profile does not guarantee processing stays inside `us-west-2`

AWS's own documentation is explicit: a geographic cross-Region inference profile keeps a request inside its
named geography (here, the US), but **"your input prompts and output results might move outside of your
source Region during cross-Region inference."** The documented example is our exact case: calling a `us.*`
profile *from* US West (Oregon) — `us-west-2` — can route the request to **either `us-east-1` or
`us-west-2`**, at AWS's discretion, not ours.
(<https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html>,
<https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html>)

Cross-region inference can also route to regions **not manually opted into the account**, and if
abuse-detection storage applies to a given model, prompts/outputs may be persisted transiently in the
destination region, not just processed there.
(<https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html>)

**This is accepted, not treated as a defect.** The project's actual residency requirement, as constraint 17
is written, is *"Bedrock is invoked via US cross-region inference profiles... never a hardcoded regional
model ID — this is mandatory."* That sentence is a statement about **which model IDs to use**, not a claim
that every byte physically stays inside the `us-west-2` data center boundary. Read literally as "stays in
`us-west-2`," constraint 17 and the `us.*` mandate are in tension, because `amazon.nova-micro-v1:0` *only*
supports `INFERENCE_PROFILE` — there is no non-cross-region way to call it. Read correctly — "stays within
US jurisdiction, audited" — the two are consistent, and that is the reading this ADR adopts.

**Mitigation, not elimination:** CloudTrail logs the actual processing region for every cross-region
inference call in the source region's trail, in the `additionalEventData.inferenceRegion` field. This
project's observability stack (Phase 9/11) will surface that field rather than assume it away, so that if
this system ever needed to answer "which physical region processed caller data," the answer is auditable,
not asserted.

**This system has no real residency obligation to violate.** All policyholders and policies are synthetic;
the only real callers are the author and invited reviewers (per `AI-USE-CASE-CARD.md`). This caveat is
recorded because the project holds itself to architectural honesty regardless of whether today's data makes
it consequential — the same standard already applied to the loss-location quasi-identifier analysis in
Phase 1.

### 2. `ca-central-1` is rejected — not because of a technical gap, but because none exists to justify moving

Every service this stack needs is present in `ca-central-1`: Amazon Connect, Lex V2 (since May 2021), and
Bedrock on-demand foundation models — 28 models as of the source checked, including cross-region access to
Claude Sonnet 4.5 / Haiku 4.5 for calls originating in `ca-central-1` (announced 2025-11-24). DynamoDB, S3,
Lambda and Step Functions are foundational services present in effectively every commercial region and are
treated as available there with high confidence, though no single authoritative fetched table itemized all
four in this research pass — flagged here as the one item in this ADR resting on indirect rather than
directly-quoted evidence.
(<https://aws.amazon.com/about-aws/whats-new/2021/05/amazon-lex-available-aws-canada-central-region/>,
<https://modelavailability.com/platforms/aws/regions/ca-central-1>,
<https://aws.amazon.com/blogs/machine-learning/accelerate-generative-ai-innovation-in-canada-with-amazon-bedrock-cross-region-inference/>)

Two specific models this project actually uses — `amazon.titan-embed-text-v2:0` and `amazon.nova-micro-v1:0`
— were **not individually confirmed** in `ca-central-1` and this ADR does not assert their availability
there; if a future ADR revisits region, that must be checked directly against
<https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html> rather than inferred from the
28-model count above.

**The deciding fact is not technical capability — it's that the premise is wrong.** The DID's
`PhoneNumberCountryCode: CA` is a **telephony numbering attribute**, not a data-residency signal. Amazon
Connect instances routinely host phone numbers from countries other than the instance's own region; this is
standard, documented practice, not a workaround. No AWS documentation found asserts that holding a Canadian
DID creates an obligation to process or store the associated call data in Canada. Absent an actual legal or
contractual requirement (e.g., a PIPEDA-driven clause this project does not have, being a synthetic-data
portfolio prototype with no real Canadian policyholders), the CA DID is not a driver for region selection.
**`ca-central-1` is rejected for the concrete reason that no requirement exists to justify the migration
cost and risk, not for any capability gap** — and the ADR says so explicitly to avoid manufacturing a
technical-sounding justification for what is actually "no reason to move."

### 3. Bedrock AgentCore's region fragmentation — supporting evidence for ADR-003, not a region decision on its own

AgentCore has no single "4-region" ceiling; its footprint is tiered. Full feature parity (Runtime,
Evaluations, Policy, etc.) exists in exactly **4 regions**: US East (N. Virginia), US West (Oregon), Europe
(Frankfurt), Asia Pacific (Sydney). A wider partial tier (no Evaluations/Policy) covers several more, and a
narrower tier (Gateway/Identity/Memory only) includes `ca-central-1` — meaning even AgentCore's own Canadian
presence would be feature-reduced.
(<https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html>)

This project chose LangGraph over AgentCore (ADR-003, drafted separately) partly on these grounds: LangGraph
running on Lambda in `us-west-2` has no equivalent region-tiered feature fragmentation. This fact is recorded
here as verified input to that ADR, not as an independent region decision — AgentCore was never a live
region alternative for this project since it wasn't the chosen agent framework.

## Consequences

**Positive:**
- `us-west-2` is retained with no migration cost or risk, consistent with the pre-existing Connect instance,
  DID association, and all Phase 0/1 work.
- The residency caveat is now documented and auditable (via CloudTrail `inferenceRegion`) rather than
  silently assumed away — consistent with the project's "no invented metrics or capabilities" rule applied
  to infrastructure claims, not just eval numbers.
- `ca-central-1` and AgentCore are formally, sourcedly rejected, closing Q-items that would otherwise
  resurface as unresolved ambiguity in a later phase.

**Negative / accepted residual risk:**
- A caller's speech, once transcribed and sent to a `us.*` Bedrock profile, may be processed transiently in
  `us-east-1` rather than `us-west-2`. This is accepted because (a) it is disclosed and cited here, (b) the
  data is synthetic, and (c) the alternative — on-demand, non-cross-region model IDs — is foreclosed by
  `amazon.nova-micro-v1:0` supporting only `INFERENCE_PROFILE`, per constraint 17 itself.
- If this project ever needed genuine Canadian data residency for real policyholder data, this ADR's
  conclusion would need to be revisited from scratch, not amended — the same posture the project already
  takes toward any real (non-synthetic) data entering the system at all (see `AI-USE-CASE-CARD.md` review
  triggers).

## Alternatives considered

| Alternative | Verdict | Why |
|---|---|---|
| `ca-central-1` (full stack) | Rejected | No technical gap, but no requirement exists to justify the migration; CA DID is a telephony attribute, not a residency signal |
| Split region (Connect/Lex in `us-west-2`, Bedrock forced non-cross-region) | Rejected | Not possible — `amazon.nova-micro-v1:0` requires `INFERENCE_PROFILE`; no non-cross-region call path exists |
| Bedrock AgentCore multi-region | Not a live alternative | AgentCore was already rejected in favor of LangGraph (ADR-003); its regional fragmentation is corroborating evidence, not an independent driver here |

## Sources

- <https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html>
- <https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html>
- <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html>
- <https://aws.amazon.com/bedrock/agentcore/faqs/>
- <https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-bedrock-agentcore-four-additional-regions/>
- <https://www.aws-services.info/connect.html>
- <https://docs.aws.amazon.com/connect/latest/adminguide/regions.html>
- <https://aws.amazon.com/about-aws/whats-new/2021/05/amazon-lex-available-aws-canada-central-region/>
- <https://modelavailability.com/platforms/aws/regions/ca-central-1>
- <https://aws.amazon.com/blogs/machine-learning/accelerate-generative-ai-innovation-in-canada-with-amazon-bedrock-cross-region-inference/>
- <https://aws.amazon.com/about-aws/whats-new/2026/04/lambda-durable-functions-16-new-regions/>

All facts above were fetched live on 2026-08-11 via a background research agent, per the project rule to
verify AWS capability and pricing claims against current sources rather than relying on memory. Two items
are explicitly flagged as unconfirmed within the ADR body rather than asserted: Titan Embed v2 / Nova Micro
availability specifically in `ca-central-1`, and a single directly-quoted source for DynamoDB/S3/Lambda/Step
Functions in `ca-central-1` (high-confidence but indirect).
