/*
 * stacks/main -- everything destroyable. Phase 8 Stage 3.
 *
 * The Lex bot, its version and alias, the Connect contact flow, queue and hours of operation, the Lambda
 * codehook, the DynamoDB tables and the artifacts bucket. `make destroy` removes all of it and returns
 * the project to its floor cost of $1.83/month, which is the Canadian DID in `stacks/telephony` and
 * nothing else.
 *
 * CONSTRAINT 16 -- WHAT THIS STACK MAY NOT DO
 *   The Connect instance is consumed through a DATA SOURCE. There is no `aws_connect_instance` resource
 *   in this directory and there must never be one: an accidental create would produce a second instance,
 *   and an accidental destroy would take the first one's configuration with it. The DID lives in
 *   `stacks/telephony`, in separate state, and is not referenced here at all -- see `connect.tf` on why
 *   the number is deliberately NOT pointed at a contact flow until Stage 4.
 *
 * WHAT STAGE 2 CHANGED ABOUT HOW THIS STACK IS BUILT
 *   `docs/phase8/LEXPOC-GATE.md` finding 4.1: CloudFormation reported `CREATE_COMPLETE` on an
 *   `AWS::Lex::Bot` 16 seconds before the locale finished building, on all three applies. Anything that
 *   depends on a BUILT locale can therefore race a green apply. `lex.tf` waits on the build state rather
 *   than on the create call -- `RESULTS.md` §3.5.1 rule 3, applied at the first opportunity rather than
 *   rediscovered.
 *
 * COST
 *   Everything here is pay-per-use or always-free at this scale. At rest, with no calls placed, this
 *   stack costs **$0.00/month**: Lambda has no idle charge, DynamoDB on-demand has no idle charge and
 *   holds kilobytes against a 25 GB allowance, S3 holds kilobytes against 5 GB, and Connect flows,
 *   queues and hours of operation are not billed. Lex bills per REQUEST and not for storing a bot -- a
 *   fact this project measured in Stage 2 rather than assumed. The cost table is in
 *   `docs/phase8/BUILD-PLAN.md` §3 and the deltas are logged in `COSTS.md`.
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
    key          = "stacks/main/terraform.tfstate"
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

/*
 * The pre-existing Connect instance. A DATA SOURCE, which is the whole of constraint 16's first clause.
 *
 * The postcondition is not decoration. `aws_connect_instance` as a data source resolves by
 * `instance_id`, and a typo would fail loudly -- but a correct id pointing at an instance that has been
 * re-created behind our backs would not, and the alias is the human-readable thing that would have
 * changed. Criterion 2 requires evidence that the instance was never re-created; `created_time` is
 * where that evidence lives, and asserting the alias here is the cheap half of it.
 */
data "aws_connect_instance" "this" {
  instance_id = var.connect_instance_id

  lifecycle {
    postcondition {
      condition     = self.instance_alias == var.connect_instance_alias
      error_message = <<-EOT
        The Connect instance ${var.connect_instance_id} reports alias "${self.instance_alias}",
        not "${var.connect_instance_alias}".

        This stack is pointed at an instance that is not the one this project was built against. Do not
        proceed: applying would create contact flows, a queue and a Lex association inside someone
        else's contact centre. Constraint 16 -- the instance is consumed, never created, and never
        substituted.
      EOT
    }
  }
}

/*
 * The two stacks this one consumes, read from the backend rather than restated as variables.
 *
 * `stacks/telephony` is DELIBERATELY ABSENT from this list. Stage 3 does not point the DID at anything
 * -- see `connect.tf` -- so it does not read the protected stack's state either. A read is harmless in
 * itself, but a data source is a dependency, and the stack that must never be reachable from a routine
 * apply is best left with no edge into it at all until there is a reason for one.
 *
 * ORDERING. `make deploy` applies inference and guardrails before main, because a remote state read of
 * an unapplied stack fails with an empty-outputs error rather than a helpful one.
 */
data "terraform_remote_state" "inference" {
  backend = "s3"

  config = {
    bucket = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key    = "stacks/inference/terraform.tfstate"
    region = "us-west-2"
  }
}

data "terraform_remote_state" "guardrails" {
  backend = "s3"

  config = {
    bucket = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key    = "stacks/guardrails/terraform.tfstate"
    region = "us-west-2"
  }
}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  instance_id  = data.aws_connect_instance.this.id
  instance_arn = data.aws_connect_instance.this.arn

  model_ids = data.terraform_remote_state.inference.outputs.model_ids

  # Prefix for every named resource in this stack, so a `make destroy` leaves nothing behind that has to
  # be recognised by eye.
  name_prefix = "fnol"
}
