/*
 * stacks/telephony -- the protected stack. Phase 8 Stage 1. Constraint 16.
 *
 * READ THIS BEFORE CHANGING ANYTHING IN THIS DIRECTORY.
 *
 * The DID `+14169871547` already exists and was claimed on 2026-08-11. Releasing a claimed number risks a
 * **180-day claim block**: the number cannot be re-claimed, by us or anyone, for six months. That is not
 * recoverable by re-running anything, by opening a ticket, or by paying more. It is the single
 * irreversible action available in this entire project.
 *
 * Everything about this stack follows from that one fact:
 *
 *   1. The number is IMPORTED, never created. There is no code path here that claims a number.
 *   2. `prevent_destroy = true`. A destroy plan fails rather than executing.
 *   3. SEPARATE STATE (`stacks/telephony/terraform.tfstate` in the backend). `make destroy` does not name
 *      this directory, and `make verify-destroy-scope` fails the build if it ever does -- because "we know
 *      not to" is not a control.
 *   4. The import guard below asserts `Protected=true` on the number's own tags and FAILS the run if it is
 *      absent. Not a warning. A `check` block would warn and continue, which is why this is a
 *      `postcondition` instead.
 *
 * WHY THE GUARD IS SHAPED THIS WAY
 *   The tag was applied in Phase 0 for exactly this purpose (`PROJECT_STATE.md`). The guard exists so that
 *   pointing this stack at the WRONG phone number fails loudly instead of importing a stranger's DID and
 *   then managing it. It reads the tag from the Resource Groups Tagging API rather than trusting a
 *   variable, because a variable is something we assert and a tag is something the resource reports.
 *
 *   It is fail-CLOSED by construction: the condition requires POSITIVE evidence that the tag equals
 *   "true". An absent tag, an absent resource, an empty result set, or an API shape we do not recognise
 *   all evaluate to something that is not "true", and all of them stop the run. This is the same
 *   asymmetry as Phase 7's mask-vs-block parser, and for the same reason -- the expensive failure is
 *   proceeding when we should not have.
 *
 * WHY THERE IS NO `default_tags` BLOCK HERE
 *   Deliberate, and the one stack where it is omitted. Provider `default_tags` would add `Phase` and
 *   `Managed` to the protected number, which is a modification -- harmless in itself, but it would mean
 *   the first apply of this stack CHANGES the resource it exists to protect. The tags below are exactly
 *   what the number already carries, so a correct apply is a **no-op**, and "no changes" becomes the
 *   proof that the import was clean.
 *
 * COST
 *   $0.00 to import. The number itself bills at **$0.06/day = $1.83/month** (`USW2-CA-did-numbers`,
 *   measured 2026-08-12) and has been billing since 2026-08-11. It survives `make destroy` by design and
 *   is the project's only always-on cost.
 */

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # SEPARATE STATE KEY. This is point 3 above and it is load-bearing: sharing a state file with a
  # destroyable stack would put the protected number one `terraform destroy` away from a code path that
  # is supposed to be routine.
  backend "s3" {
    bucket       = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key          = "stacks/telephony/terraform.tfstate"
    region       = "us-west-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  # No default_tags. See the header.
}

locals {
  did_arn = "arn:aws:connect:${var.region}:${var.account_id}:phone-number/${var.phone_number_id}"

  # The tag map the number reports, or an empty map if it reports nothing at all. `try` collapses every
  # failure shape -- no such resource, empty list, unexpected response -- into the same "no evidence"
  # answer, which the guard then treats as failure.
  observed_tags = try(
    one([
      for m in data.aws_resourcegroupstaggingapi_resources.did.resource_tag_mapping_list :
      m.tags if m.resource_arn == local.did_arn
    ]),
    {}
  )

  protected_tag = try(local.observed_tags["Protected"], "")
}

# Reads the live tags on the number. This is the guard's evidence, and it is read from the API rather
# than declared in a variable.
data "aws_resourcegroupstaggingapi_resources" "did" {
  resource_arn_list = [local.did_arn]
}

# The number. IMPORTED -- see the `import` block in imports.tf. Nothing here claims a number.
resource "aws_connect_phone_number" "did" {
  target_arn   = var.connect_instance_arn
  country_code = var.phone_number_country_code
  type         = "DID"
  description  = var.phone_number_description

  # Exactly the tags the number already carries. Any addition here turns a no-op apply into a change to
  # the protected resource -- see the header.
  tags = {
    Project   = var.project_tag
    Owner     = "marcos"
    Protected = "true"
  }

  lifecycle {
    # Point 2. A destroy plan FAILS. This is the last line of defence, not the first.
    prevent_destroy = true

    # Point 4, the import guard. Fails the run -- plan and apply both -- when the number does not carry
    # `Protected=true`. Phase 8 criterion 3 requires this to be DEMONSTRATED by removing the tag in a
    # scratch copy, not asserted here in a comment.
    precondition {
      condition     = local.protected_tag == "true"
      error_message = <<-EOT
        IMPORT GUARD FAILED: ${local.did_arn} does not carry Protected=true.

        Observed value: "${local.protected_tag}" (empty means the tag, or the resource, was not found).

        This stack manages a phone number that CANNOT BE SAFELY RE-CLAIMED -- releasing a claimed DID
        risks a 180-day block during which nobody can claim it back. The Protected=true tag is how this
        stack confirms it is pointed at OUR number and not someone else's.

        Do NOT remove this guard to get past it. Either the wrong phone_number_id is configured, or the
        tag was removed from a number that should have it. Fix the cause.
      EOT
    }
  }
}
