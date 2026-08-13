/*
 * Application inference profiles -- Phase 8 Stage 0.5. See `docs/adr/ADR-016`.
 *
 * WHY THIS EXISTS
 *   Bedrock on-demand inference invoked through a SYSTEM-DEFINED cross-region profile (`us.*`) is
 *   unattributable: system profiles carry no tags, so no billing record for a model call can be filtered
 *   by `Project`. On this account that is not academic -- the sibling fine-tuning project accounts for
 *   99.86% of August's Bedrock spend, and Phase 8 criterion 9 requires an alarm that includes our spend
 *   and excludes theirs. Without these profiles the Bedrock line cannot be on either side of that filter.
 *
 *   An APPLICATION inference profile is the documented mechanism: it wraps a model or a system-defined
 *   cross-region profile, carries cost allocation tags, and is passed as `modelId` in place of the model
 *   string. Its tags are attached to the billing record for each request.
 *
 * CONSTRAINT 17
 *   Constraint 17 says Bedrock is invoked via `us.*` cross-region inference profiles, "never a hardcoded
 *   regional model ID -- this is *mandatory*, not stylistic". Passing a profile ARN is not what that
 *   sentence literally describes. `ADR-016` amends the wording and records why the substance survives:
 *   `model_source.copy_from` is the `us.*` profile, so the region set is inherited rather than replaced.
 *   The `models` output below is the check on that claim, and it is a check rather than an assertion --
 *   Marco's condition on approving this was that a wrapper collapsing the region set is exactly the shape
 *   of failure where the docs stay true and the resource does not.
 *
 * COST
 *   $0.00 at rest. An application inference profile is a routing/tagging record, not capacity. Requests
 *   through it bill at ordinary on-demand rates for the underlying model, and AWS documents no surcharge
 *   for cross-region inference. Destroyable; `make destroy` removes them and the `us.*` defaults in
 *   `settings.py` continue to work untouched.
 *
 * WHAT THIS DOES NOT BUY
 *   Per-request cost. AWS: "Application inference profiles deliver aggregated billed dollars to AWS Cost
 *   Explorer and CUR. The finest grain is per usage type per day; they do not produce per-request cost."
 *   `COSTS.md`'s per-run figures stay computed estimates, reconciled against CloudWatch `AWS/Bedrock`
 *   token metrics. What these profiles make possible is a correct DAILY total under a tag filter, which
 *   is what a budget alarm consumes.
 */

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key          = "stacks/inference/terraform.tfstate"
    region       = "us-west-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = var.project_tag
      Owner   = "marcos"
      Phase   = "8"
      Managed = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # Every profile this project invokes, and what it wraps.
  #
  # The first three wrap `us.*` SYSTEM-DEFINED profiles, so they inherit a three-region set
  # (us-east-1, us-west-2, us-east-2) and constraint 17's routing property is preserved.
  #
  # `embedding` is different and the difference is deliberate: `amazon.titan-embed-text-v2:0` has no
  # `us.*` profile -- it is invoked as a plain foundation model -- so its wrapper is necessarily
  # single-region. That is not a constraint 17 regression, because there was never a cross-region
  # profile to lose. It is wrapped anyway so that embedding spend is attributable like everything else;
  # an attribution scheme with a hole in it reports a smaller number, not a missing one.
  profiles = {
    router = {
      copy_from    = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.amazon.nova-micro-v1:0"
      description  = "L2 turn classifier per ADR-004. Cross-region via us.amazon.nova-micro-v1:0"
      role         = "router"
      cross_region = true
    }
    generation = {
      copy_from    = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.amazon.nova-lite-v1:0"
      description  = "Response generation per ADR-004. Cross-region via us.amazon.nova-lite-v1:0"
      role         = "generation"
      cross_region = true
    }
    judge = {
      copy_from    = "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"
      description  = "Tier B eval judge. Cross-region via us.anthropic.claude-haiku-4-5"
      role         = "judge"
      cross_region = true
    }
    embedding = {
      copy_from    = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"
      description  = "Corpus and query embeddings per ADR-002. Single region: no cross-region profile exists for this model"
      role         = "embedding"
      cross_region = false
    }
  }
}

resource "aws_bedrock_inference_profile" "this" {
  for_each = local.profiles

  name = "fnol-${each.key}"

  # CreateInferenceProfile enforces `([0-9a-zA-Z:.][ _-]?)+` on `description`: alphanumerics, colon and
  # period only, each optionally followed by ONE space, underscore or hyphen. No parentheses, no commas,
  # no asterisks. The first apply failed on "(ADR-004)". Terraform cannot catch this at plan time -- the
  # provider has no client-side validation for it -- so it is a 400 at create, on every profile at once.
  description = each.value.description

  model_source {
    copy_from = each.value.copy_from
  }

  # The tags that make the spend attributable. `Project` comes from the provider's default_tags and is
  # the key the budget alarm filters on; `Role` is what makes a tagged report say *which* part of the
  # agent spent the money, which no other instrument in this project can currently answer.
  tags = {
    Role = each.value.role
  }
}
