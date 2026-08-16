/*
 * stacks/observability -- Phase 11, Stage A. Budget alarm + the cost dashboard's data pipeline.
 *
 * SCOPE OF THIS STAGE (criteria 1 and 2 of Phase 11's approved breakdown)
 *   1. An `aws_budgets_budget` scoped to this project's cost-allocation tag, IncludeCredit:false /
 *      IncludeRefund:false (CLAUDE.md's own warning -- see `docs/RESULTS.md` §18 for a live instance of
 *      the failure this stack is built to not repeat), notifying an SNS topic at 80%/100% of a $20
 *      threshold (under the $25 ceiling), plus one temporary synthetic-breach notification for the
 *      firing-proof (`docs/RESULTS.md` §19 -- removed once Marco confirms receipt, tracked as an open
 *      item so it does not become permanent).
 *   2. A CloudWatch custom dashboard (criterion 2) fed by a weekly Lambda that pulls MTD gross Cost
 *      Explorer usage (`RECORD_TYPE=Usage`) and writes it as a custom metric. Cost Explorer's
 *      `GetCostAndUsage` is $0.01/request with no free tier at all (`CLAUDE.md`) -- the schedule is
 *      weekly, not more frequent, specifically to keep this bounded.
 *
 * COST EXPLORER IS us-east-1 ONLY -- A STATED EXCEPTION TO CONSTRAINT 17, NOT A VIOLATION OF IT
 *   Constraint 17 fixes Connect/Lex/Lambda/DynamoDB/S3/Step Functions at us-west-2. Cost Explorer's API
 *   has no us-west-2 endpoint; AWS only serves `ce:*` from `us-east-1`, platform-wide, for every
 *   customer. `lambda_src/ce_pull.py` pins `region_name="us-east-1"` on the `ce` client ONLY, with a
 *   comment saying so -- every other client in this stack (`cloudwatch`) stays in `var.region`. This is
 *   the same shape as Bedrock's `us.*` inference-profile literal: a platform-forced exception named
 *   explicitly, not a silent regional drift.
 *
 * STAGE B1 (built here, this file's dashboard.tf)
 *   Criterion 3's operational dashboard, three of its four required panel categories: Lambda
 *   errors/duration and Lex recognition (native `AWS/Lambda`/`AWS/Lex` metrics, no new code) and
 *   guardrail usage units, via a real emitter wired into `agents/nodes/guardrails_nodes.py`
 *   (`observability/guardrail_metrics.py`) -- per Marco's explicit instruction (`docs/RESULTS.md`
 *   §17.5), that panel does not ship without a live source, and now has one.
 *
 * STAGE B2 (explicitly not built here)
 *   The fourth panel category, turn-latency sub-components, needs live latency instrumentation that does
 *   not exist yet -- Phase 9's profiling was one-off scripts, not a continuous source. Scoped jointly
 *   with Stage D's C14 signal (Marco, 2026-08-16), as its own proposal, so the two don't build two
 *   separate instrumentation paths or each assume the other covers it.
 */

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6"
    }
  }

  backend "s3" {
    bucket       = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key          = "stacks/observability/terraform.tfstate"
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
      Phase   = "11"
      Managed = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
