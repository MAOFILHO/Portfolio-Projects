# ADR-007: IaC tool selection for the Lex V2 bot — nested CloudFormation `AWS::Lex::Bot` wrapped by Terraform, native `aws_lexv2models_*` rejected, CDK rejected

**Status:** Accepted (Phase 2). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-11

---

## Context

`CLAUDE.md` already fixes Terraform ≥1.9 as the project's IaC tool and states "Mixing Terraform and CDK is
forbidden." That leaves one open question, flagged as risk R1 in `PROJECT_STATE.md`: **how the Lex V2 bot
itself — the 11-slot `FileAutoClaim` intent, barge-in/DTMF configuration, and five other intents — gets
defined**, given that Terraform's native `aws_lexv2models_*` resources have documented defects in exactly
the areas this project needs (prompt specifications, retry/barge-in behavior, multi-slot intents).

PROJECT_STATE.md requires this be resolved as a genuine three-way comparison — native
`aws_lexv2models_*` · nested CloudFormation `AWS::Lex::Bot` wrapped by Terraform's `aws_cloudformation_stack`
· CDK (Python) — "all three assessed on merit; recommendation not pre-decided." A background research agent
verified current, live status of the three specific GitHub issues previously identified during Phase 0
archaeology (#42147, #36845, #39948), current provider version, CDK's actual Lex V2 construct support, and
whether CloudFormation's own `AWS::Lex::Bot` has a comparable documented defect — rather than relying on
memory, per the project's standing verification rule. Findings below are as of 2026-08-11.

## Decision

**Nested CloudFormation `AWS::Lex::Bot` (all locales, intents, slots and prompt specs in one resource),
wrapped by Terraform's `aws_cloudformation_stack`.** Everything else — Connect flows, queues, hours,
Lex/Lambda associations, Lambda, DynamoDB, S3 — remains native Terraform. One IaC tool (Terraform) authors
everything; CloudFormation is a nested implementation detail Terraform manages as a single opaque resource,
not a second parallel IaC tool, so the "no mixing Terraform and CDK" constraint is respected in spirit as
well as letter — the project still has exactly one top-level IaC surface.

### Option A — native `aws_lexv2models_*` (rejected)

Two of the three known issues are **confirmed still open** as of 2026-08-11, and they sit directly on this
project's showcase feature:

| Issue | Status | Relevance |
|---|---|---|
| [#42147](https://github.com/hashicorp/terraform-provider-aws/issues/42147) — `prompt_specification` changes on `aws_lexv2models_slot` silently produce no update request | **Open** (filed 2025-04-06, no fix, no milestone) | Prompt specs are exactly how retry prompts, barge-in messages and confirmation re-asks are authored. A silent no-op here means a Terraform apply reports success while the deployed bot's prompts are stale — a defect that would not surface in `terraform plan`/`apply` output, only in a live call |
| [#39948](https://github.com/hashicorp/terraform-provider-aws/issues/39948) — structural circular dependency between `aws_lexv2models_intent` and `aws_lexv2models_slot` via `slot_priority` | **Open** (filed 2024-10-30, still active as of 2025-11-21, unresolved). A related issue, [#36863](https://github.com/hashicorp/terraform-provider-aws/issues/36863) ("Lex Impossible workflow"), documents the same chicken-and-egg design gap | This is a structural graph-cycle problem in the resource design itself, not a one-off bug: `intent.slot_priority` needs slot IDs, `slot.intent_id` needs the intent — a genuine cycle Terraform's dependency graph cannot resolve without an out-of-band workaround (`null_resource` + AWS CLI, which the research found does not reliably preserve intent state) |
| [#36845](https://github.com/hashicorp/terraform-provider-aws/issues/36845) — `prompt_attempts_specification`/`message_selection_strategy` "inconsistent result after apply" | **Closed**, fixed in provider v5.66.0 (PR #39145) | The one issue of the three that *is* resolved — noted for completeness, not a reason to avoid this option on its own |

Additionally: the provider is at **v6.58.0** (2026-08-05; v6.57.0 was pulled from the registry for a
significant bug — never pin to it), and a direct check of the CHANGELOG from v6.43.0 through the unreleased
v6.59.0 window shows **zero `lexv2models` entries** — no fixes, no feature additions, in several months.
Other open `lexv2models` gaps (speech recognition settings #46504, generative-AI settings #41801, slot
capture settings #41591) corroborate that this resource family is not receiving active maintenance relative
to the rest of the provider.

**Rejected because:** one of the two open defects (#39948) is not a bug that a future patch fixes on its own
timeline — it is a structural graph-cycle in how the resource schema was designed, with no merged or proposed
fix, and the other (#42147) would let a stale prompt spec ship silently on exactly the resource type
(11-slot intent with retry prompts) that is this project's stated showcase. Accepting Option A would mean
building the hardest, most-tested part of the system on the two least-maintained corners of the provider.

### Option B — nested CloudFormation `AWS::Lex::Bot`, wrapped by `aws_cloudformation_stack` (chosen)

Defining the entire bot — every locale, intent, slot and prompt specification — as **one** `AWS::Lex::Bot`
resource is structurally immune to #39948: there is no separate `aws_lexv2models_intent` and
`aws_lexv2models_slot` resource pair for Terraform's graph to form a cycle over, because CloudFormation
resolves the intent↔slot relationship internally, inside a single resource body, the way the Lex service
itself expects it. Repo 1 (Phase 0 archaeology) already proved this shape works for a real bot.

**What was not found, and is stated as such rather than assumed:** no confirmed open GitHub issue or
documented AWS limitation for `PromptAttemptsSpecification` under multi-slot intents specifically in
`AWS::Lex::Bot`. A relevant re:Post thread exists ("Amazon Lex and CloudFormation Compatibility Problems")
but returned HTTP 403 to automated fetch and its content could not be verified — this is recorded as
**unconfirmed**, not as a clean bill of health.

**This is the honest gap in this decision, and the mitigation is empirical, not documentary.** Because CDK's
own `CfnBot` construct is auto-generated from the same CloudFormation schema as `AWS::Lex::Bot`, and both are
free of a *confirmed* defect but neither has been proven clean by direct citation, the plan going into
Phase 8 (telephony/Lex provisioning) is: **build a small proof-of-concept `AWS::Lex::Bot` stack exercising
multi-slot prompt-attempts/retry behavior before the real bot is authored on top of it**, and record the
result — pass or fail — in `PROJECT_STATE.md` rather than assume the schema-level absence-of-evidence means
evidence of absence. If the POC surfaces a real defect at that point, this ADR is superseded, not silently
patched around.

**Consequence accepted knowingly:** this ADR commits to an IaC approach whose primary claimed advantage over
Option A (a working `PromptAttemptsSpecification` for multi-slot intents) is verified only by the *absence*
of a confirmed defect, not by a positive confirmation — a materially weaker evidentiary basis than Option
A's rejection, which rests on two *confirmed* open, sourced, dated GitHub issues. This is disclosed here so
the decision's confidence level is not overstated, consistent with the project's "no invented metrics or
capabilities" rule extended to infrastructure claims, and the POC gate above exists specifically to close
that gap before real provisioning, not to have left it open indefinitely.

### Option C — CDK (Python) (rejected)

Two independent reasons, one of them dispositive on its own:

1. **`CLAUDE.md` already forbids mixing Terraform and CDK.** This alone rejects Option C regardless of
   technical merit — recorded here for completeness since PROJECT_STATE.md asked for all three assessed on
   the merits, not because the constraint was in doubt.
2. **On the merits, CDK offers no advantage over Option B for this resource anyway.** Verified directly
   against the live `aws_cdk.aws_lex` Python module docs (aws-cdk-lib v2.202.0): Lex V2 has **no hand-written
   L2 construct** — only `CfnBot`, `CfnBotAlias`, `CfnBotVersion`, `CfnResourcePolicy`, all `Cfn`-prefixed L1
   wrappers auto-generated from the identical CloudFormation schema `AWS::Lex::Bot` uses. The module's own
   README states this explicitly: *"There are no hand-written (L2) constructs for this service yet... use
   the automatically generated L1 constructs... exactly as you would using CloudFormation."* The CDK
   project's public roadmap has a general aspiration toward L2 coverage for all services but no tracked item
   or ETA specific to `aws_lex`. So even setting the mixing prohibition aside, CDK-authored Lex V2 is
   functionally the same CloudFormation schema as Option B, with Python type-checking as the only actual
   difference — not a reason to introduce a second IaC tool and violate an existing constraint for it.

## Consequences

**Positive:**
- Resolves risk R1 from `PROJECT_STATE.md` with a decision that is structurally immune to the one
  *confirmed structural* defect (#39948) and the one *confirmed silent-failure* defect (#42147) in the
  rejected native option.
- Keeps exactly one top-level IaC tool (Terraform), consistent with the existing "no mixing" constraint —
  CloudFormation is a nested resource body Terraform manages as a single opaque unit, not a parallel
  provisioning path.
- Repo 1 (Phase 0 archaeology) already demonstrates the `AWS::Lex::Bot` shape working end-to-end, so this is
  not unproven in this project's own source material, only unproven specifically for
  `PromptAttemptsSpecification` under multi-slot intents.

**Negative / accepted residual risk:**
- The claimed advantage over Option A rests on absence of a confirmed defect, not a positive confirmation —
  weaker evidence than the sourced, dated issues that sank Option A. **Mitigation is a mandatory Phase 8 POC
  before the real bot is built on this approach**, not a documentary assertion that the risk is zero.
- `aws_cloudformation_stack` is an update-in-place black box from Terraform's point of view: drift detection
  and per-field diffing that native resources would otherwise give `terraform plan` are lost inside the
  nested stack. This is the standard cost of the nested-CFN pattern and is accepted as the trade for
  avoiding #39948's structural cycle.
- If a future terraform-provider-aws release fixes #39948 (a structural fix, not a patch, would be required),
  this ADR should be revisited — but per the ADR discipline, that revisit is a new ADR that supersedes this
  one, not an edit to it.

## Alternatives considered

| Option | Verdict | Deciding factor |
|---|---|---|
| Native `aws_lexv2models_*` | Rejected | Two confirmed open defects (#42147 silent no-op, #39948 structural cycle) directly on this project's showcase feature; provider has seen zero `lexv2models` changes across the last several CHANGELOG-tracked releases |
| Nested CFN `AWS::Lex::Bot` via `aws_cloudformation_stack` | **Chosen** | Structurally avoids the confirmed cycle; the multi-slot/prompt-attempts risk is unconfirmed rather than clean, so a Phase 8 POC gate is mandatory before relying on it further |
| CDK (Python) | Rejected | Forbidden by existing constraint (dispositive on its own); also no L2 construct exists for Lex V2 — functionally identical authoring surface to Option B with no advantage |

## Sources

- <https://github.com/hashicorp/terraform-provider-aws/issues/42147>
- <https://github.com/hashicorp/terraform-provider-aws/issues/36845>
- <https://github.com/hashicorp/terraform-provider-aws/issues/39948>
- <https://github.com/hashicorp/terraform-provider-aws/issues/36863>
- <https://github.com/hashicorp/terraform-provider-aws/releases>
- <https://github.com/hashicorp/terraform-provider-aws/blob/main/CHANGELOG.md>
- <https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lex/README.html>
- <https://github.com/aws/aws-cdk/blob/main/ROADMAP.md>
- <https://repost.aws/questions/QUqjdJG1EkQ2aAI_Fvg1AOrA/amazon-lex-and-cloudformation-compatibility-problems> (fetch blocked by the site, content unconfirmed — cited to record what was *not* verifiable, not as supporting evidence)

All facts above were fetched live on 2026-08-11 via a background research agent, per the project rule to
verify against current sources rather than memory. The one item this ADR could not verify — real-world
update-drift behavior of `PromptAttemptsSpecification` under multi-slot intents in `AWS::Lex::Bot` — is
carried forward as a mandatory Phase 8 proof-of-concept, not asserted as resolved.
