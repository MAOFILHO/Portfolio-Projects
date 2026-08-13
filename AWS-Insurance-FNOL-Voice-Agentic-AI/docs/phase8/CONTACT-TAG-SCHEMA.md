# Contact tag schema — decided before Stage 3, not at it

**Phase 8. 2026-08-12.** Marco, on reading Stage 0's audit:

> Contact tags as a Stage 3 dependency: the no-PII rule is the one to design for, not the 6-tag limit.
> Claim and policy numbers are the natural things to tag a contact with and both are forbidden. Decide the
> tag schema before Stage 3 rather than at it.

Correct on both counts. The 6-tag limit is a budget and budgets get met. The no-PII rule removes the tags
you would actually reach for, and discovering that while writing a contact flow means discovering it under
pressure to ship the flow.

## The constraint, verbatim

AWS, on contact tags:

> **Important:** Do not store personally identifiable information (PII) or other confidential or sensitive
> information in tags. We use contact tags to provide you with billing services. Tags are not intended to
> be used for private or sensitive data.

Three properties of contact tags make this stricter than it first reads:

1. **Tags land in the billing system**, which sits entirely outside `ADR-011`'s PII redaction boundary.
   Everything this project has built for PII — the redaction pipeline, the guardrail's seven PII entities,
   the transcript scrubbing — applies to transcripts and logs. **None of it applies to a tag.** A tag is
   the one path out of this system that our own PII controls do not cover.
2. **Tags are joined to the contact record**, which carries the caller's phone number. A tag value need
   not itself identify anyone to become identifying once joined.
3. **Tags are effectively immutable after 3 hours.** Corrections after that update the contact record and
   never reach billing. There is no redaction-after-the-fact.

## What is forbidden, and it is most of the interesting fields

| Tempting tag | Why not |
|---|---|
| `ClaimNumber=CLM-2608-00042-4` | Direct claim identifier. Forbidden outright |
| `PolicyNumber=PY4821` | Same |
| `CallerName`, `Phone`, `VIN`, `Plate`, `Location` | PII, and several are in the guardrail's own entity list |
| `LossDate` | `DOMAIN-ARTIFACTS.md` already flags loss date/time as the single most important captured field; joined to a phone number it is claim-identifying |

The claim number is the one that hurts, because it is the natural join key between a contact and
everything else this project stores, and joining spend to a claim is a genuinely useful thing to want. It
stays forbidden. The join is available to us **offline**, inside the redaction boundary, keyed on
`contactId` — which is Connect's own identifier, already in the contact record, and not something we have
to put in a tag to obtain.

## The decided schema — three tags, of six available

| Tag | Value | Why |
|---|---|---|
| `Project` | `AWS-Insurance-FNOL-Voice-Agentic-AI` | **The reason contact tagging exists in this project.** Constant. The budget alarm's filter |
| `Env` | `demo` \| `dev` | Separates the 20 approved real calls from any later throwaway testing, in the one report where they otherwise merge |
| `FlowVersion` | content hash of the deployed flow | Stage 3 already gives flows a content-hash suffix so a bad flow never overwrites a known-good one. Reusing that hash makes "did the new flow change cost per call" answerable, and it is a build artifact with no relationship to any caller |

Three of six used. The remaining three are left deliberately empty rather than filled to capacity — a tag
added later is cheap, and a tag that turns out to be sensitive is not removable from billing history.

## The two rejected tags, and the sharper reason for rejecting them

`Intent` and `Outcome` are the obvious high-value additions. Cost-per-intent and cost-per-outcome are
exactly the numbers a portfolio project wants, and neither value contains an identifier. **They are
rejected anyway.**

The reason is specific to this domain. One of the six in-scope intents is **injury or fatality mentioned**.
A contact tagged `Intent=InjuryEscalation`, joined to a contact record carrying the caller's phone number,
is **a health-adjacent inference about an identifiable person, sitting in a billing system, outside every
PII control this project has built, and unredactable after three hours.**

The tag value contains no PII. The tag, in context, is health information about a person. That distinction
— value versus value-plus-join — is the whole content of AWS's "or other confidential or sensitive
information" clause, and reading the rule as "no identifiers in the string" would pass every mechanical
check while doing precisely the thing the rule forbids.

`Outcome` fails for the same reason with an extra step: any outcome vocabulary rich enough to be worth
recording distinguishes the injury escalation from the others, so it reconstructs `Intent` for the one
case where it matters most.

**A coarsened `Intent` was considered and also rejected.** Bucketing the six intents so injury is
indistinguishable would be safe, but the buckets that achieve that also destroy the cost signal the tag was
for — and a tag that is safe because it says nothing is not a tag worth spending a slot on.

**What replaces them.** Cost per intent is still obtainable, and better: join `contactId` to this project's
own transcripts and eval records offline, where `ADR-011`'s redaction boundary already governs and where
the join can be as detailed as we like. The billing system gets a project name; the analysis happens where
the controls are. That is the correct place for the split, and it is the same reasoning as `ADR-011`
itself.

## Consequences for Stage 3

1. The contact flow contains **one `Contact tags` block**, setting the three tags above, placed **before**
   any branch that can escalate or disconnect — a tag set on only some paths produces a cost report that
   silently under-counts, which is the failure shape Stage 0 spent its whole audit on.
2. `FlowVersion` is wired from the same content hash Stage 3 already computes for the flow name. One
   source, two uses.
3. **A CI check belongs with the recording check**: fail the build if a flow's `Contact tags` block
   contains any key outside `{Project, Env, FlowVersion}`. The recording check exists because "we know not
   to enable it" is not a control; the same argument applies to a tag added in a hurry six months from now,
   and this one is unredactable after three hours.
4. The `Project` contact tag is **belt** only. The **braces** is the system-defined
   `aws:connect:instanceId`, activated after the first real call — it attributes all Connect spend without
   depending on our flow being correct. Both, not either.
