# ADR-016: Bedrock is invoked through application inference profiles wrapping the `us.*` system profiles

**Status:** Accepted (Phase 8, Stage 0.5). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-12
**Amends:** the *literal wording* of `CLAUDE.md` constraint 17. It does not supersede `ADR-004` (model
selection) or `ADR-002` (embeddings); the models chosen there are unchanged, and so is the routing.

---

## Context

Phase 8's criterion 9 requires a budget alarm that includes this project's spend and excludes the sibling
fine-tuning project's, on a shared AWS account. Stage 0's cost attribution audit
(`docs/phase8/COST-ATTRIBUTION-AUDIT.md`) established that this is not currently possible for Bedrock:

- **System-defined cross-region inference profiles (`us.*`) carry no tags.** There is no resource on the
  invocation path that a cost allocation tag can attach to, so no Bedrock billing record produced by this
  project can be filtered by `Project`.
- The stakes are measured, not assumed. August Bedrock gross on this account is **$0.84935** for the
  sibling's `USW2-Llama3-3-70B-Customization-Training` against **$0.00124** for our usage types in Cost
  Explorer — the sibling is **99.86%** of the account's Bedrock spend. An unfiltered alarm fires on their
  work; a filter that cannot see our Bedrock spend at all omits what CloudWatch shows is really
  **≈$0.525** of ours.

AWS documents exactly one mechanism for attributing on-demand Bedrock spend: an **application inference
profile**, a user-created resource that wraps either a foundation model or a system-defined cross-region
profile, carries cost allocation tags, and is passed as `modelId` in place of the model string.

> The profile's tags are attached to the billing record for each request.

## The tension with constraint 17

Constraint 17 says, verbatim:

> Bedrock is invoked via **US cross-region inference profiles (`us.*`)**, never a hardcoded regional model
> ID — this is *mandatory*, not stylistic: `amazon.nova-micro-v1:0` supports only `INFERENCE_PROFILE`.

Passing `arn:aws:bedrock:us-west-2:759316130780:application-inference-profile/e55shbc6xaks` is not what
that sentence literally describes. A future reader comparing the constraint to `settings.py` would
reasonably read a violation. This ADR exists so they read a decision instead.

**The constraint has two clauses, and they are not equally load-bearing.**

| Clause | What it protects | Under this ADR |
|---|---|---|
| "never a hardcoded regional model ID" | The hard requirement. `amazon.nova-micro-v1:0` supports only `INFERENCE_PROFILE`; a bare regional model ID does not work at all | **Preserved.** An application profile ARN is not a regional model ID, and the underlying model is still reached through an inference profile |
| "via `us.*` cross-region inference profiles" | The routing property — capacity spread across three US regions rather than pinned to one | **Preserved, and now checked.** `model_source.copy_from` is the `us.*` profile, so the region set is inherited |

The substance of 17 is *cross-region US routing with no regional pinning*. Both survive. What changes is
the identifier passed at call time, which is a deployment-time fact rather than a routing one.

## Decision

1. `infra/terraform/stacks/inference` creates four application inference profiles — `router`,
   `generation`, `judge`, `embedding` — each tagged `Project` (from provider `default_tags`) and `Role`.
2. Three of them wrap the corresponding `us.*` system profile via `model_source.copy_from`. `embedding`
   wraps `amazon.titan-embed-text-v2:0` directly, because **no `us.*` profile exists for that model**;
   its single-region wrap is therefore not a loss of a property it never had.
3. `settings.py` reads each model ID from an environment variable with **the `us.*` literal as the
   default**. Deployment sets the ARN; local runs, the simulator, every test and every Tier A eval keep
   working with no AWS state at all, and `make destroy` degrades cleanly back to the untagged-but-working
   path.
4. `make verify-inference` asserts the routing property against the live API.

## Marco's condition, and why it was the right one

Approval came with a requirement rather than a blessing:

> Verify the wrapped profile actually routes cross-region rather than pinning to one region. That is the
> property 17 exists to protect, and "application profile wrapping a system profile" is exactly the shape
> where an assumption could hold in the docs and not in the response metadata.

This names a specific, plausible failure: `copy_from` could have been read by the service as *"take this
profile's current model"* rather than *"inherit its region set"*, producing a profile that satisfies every
document quoted above and silently pins to `us-west-2`. Nothing in the documentation rules it out, and
nothing in a successful apply would reveal it.

**Measured, not assumed.** `GetInferenceProfile`, read from the API rather than from Terraform state:

| Profile | Type | Status | Regions |
|---|---|---|---|
| `router` | APPLICATION | ACTIVE | us-east-1, us-east-2, **us-west-2** |
| `generation` | APPLICATION | ACTIVE | us-east-1, us-east-2, us-west-2 |
| `judge` | APPLICATION | ACTIVE | us-east-1, us-east-2, us-west-2 |
| `embedding` | APPLICATION | ACTIVE | us-west-2 (expected — see decision 2) |

Identical to the `us.*` system profile's own three-region set. The region set is inherited, not replaced.
A real `Converse` call through the `router` ARN returned correctly at 7 in / 2 out, $0.00000053 — so the
ARN is a working invocation path and not merely a well-formed resource.

`make verify-inference` encodes this as an executable assertion with a **per-profile** expected count, and
was **proven by negative control**: setting `embedding`'s expectation to 3 makes it fail with the intended
message. A real single-region profile stood in for a collapsed one, so the control tested the check
against the failure it exists to catch rather than against a mock.

## Consequences

**Gained.** Bedrock spend becomes attributable by `Project` and, via the `Role` tag, by *which part of the
agent* spent it — router vs generation vs judge vs embedding. No instrument in this project could
previously answer that. Criterion 9 becomes dischargeable for the Bedrock line.

**Not gained, and stated so it is not assumed.** Per-request cost. AWS is explicit:

> Application inference profiles deliver aggregated billed dollars to AWS Cost Explorer and CUR. The
> finest grain is **per usage type per day**; they do not produce per-request cost.

`COSTS.md`'s per-run figures remain computed estimates. Their independent check is **CloudWatch
`AWS/Bedrock` token metrics**, which Stage 0 established are free, immediate, and counted by AWS rather
than by us — and which showed this log under-reporting by 22%.

**Cost.** $0.00 at rest; a profile is a routing/tagging record, not capacity. Requests bill at ordinary
on-demand rates and AWS documents no surcharge for cross-region inference.

**A new operational failure mode, worth naming.** Four resources now sit between the code and the model.
If `make destroy` removes them while `FNOL_ROUTER_MODEL_ID` still points at a deleted ARN, calls fail.
The default-to-`us.*` design in decision 3 means the *code* is safe; the *deployment environment* is
where a stale ARN could persist, and that belongs to Stage 3's Lambda configuration.

## Alternatives rejected

**Leave Bedrock unattributed and filter the alarm on everything else.** Rejected: it silently under-reports
the project's cost, and the alarm would read low by exactly the amount of the fastest-growing line. An
attribution scheme with a hole in it reports a smaller number, not a missing one — which is the same
failure shape as the tag filter that matches nothing.

**Separate AWS accounts for the two projects.** The correct answer at any real scale, and out of scope
here: the Connect instance and the protected DID live in this account and cannot be moved without
releasing the number, which risks a 180-day claim block (constraint 16).

**Per-request metadata tagging with model invocation logs.** Gives finer grain than application profiles,
but requires enabling invocation logging to S3 or CloudWatch and parsing it. That is a billable log
pipeline built to answer a question a $0 resource already answers well enough for a budget alarm.
