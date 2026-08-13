/*
 * `make bootstrap` -- the Terraform state backend. Phase 8 Stage 0.
 *
 * THE CHICKEN AND EGG, STATED RATHER THAN GLOSSED
 *   This stack creates the bucket that every other stack stores its state in, so it cannot itself use
 *   that bucket. It runs on local state, permanently, and that is the standard resolution rather than a
 *   shortcut. The residual risk is the same one the guardrail stack carried in Phase 7 and it is small
 *   for the same reason: lose this local state and the bucket is orphaned, not lost -- it is findable by
 *   its deterministic name and re-importable with `terraform import`. `scripts/verify_billable.py` knows
 *   the name.
 *
 * WHY NO DYNAMODB LOCK TABLE
 *   Terraform >= 1.10 locks S3-backed state natively with `use_lockfile = true`, writing a `.tflock`
 *   object beside the state object. The DynamoDB lock table it replaces is a billable resource that
 *   this project -- one operator, one machine -- has no use for. We are on 1.15.8; the floor below is
 *   1.10 rather than the project-wide 1.9 precisely because this file depends on that feature.
 *
 * COST
 *   S3 Standard. The state objects are kilobytes; the account's 5 GB S3 free-tier allowance is
 *   account-age-independent and covers this many times over. $0.00/mo, and $0.00/mo if teardown is
 *   forgotten -- which matters, because `make destroy` deliberately does NOT destroy this stack. A
 *   backend that deletes itself takes every other stack's state with it.
 */

terraform {
  # 1.10, not the project-wide 1.9 floor: `use_lockfile` does not exist before it, and silently
  # running unlocked would be worse than failing to init.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Local state, permanently and by construction. See the header.
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

# Deterministic name, no random suffix. A random suffix would make the bucket unfindable after a lost
# local state file, which is the exact failure this stack has to survive. S3 bucket names are globally
# unique, so the account ID is the disambiguator; it is already recorded in CLAUDE.md's environment
# table and is not a secret.
locals {
  bucket_name = "fnol-voice-agent-tfstate-${data.aws_caller_identity.current.account_id}-${var.region}"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "tfstate" {
  bucket = local.bucket_name

  # The one resource in this project that `make destroy` must never reach. Without this, a stray
  # `terraform destroy -auto-approve` in this directory would take the state of every other stack with
  # it -- including stacks/telephony, whose state points at a number that cannot be re-claimed for 180
  # days. prevent_destroy turns that from a bad afternoon into a failed plan.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  # SSE-S3 (AES256), not SSE-KMS. A customer-managed KMS key is $1/mo plus per-request charges -- 4% of
  # the monthly ceiling to encrypt a file that contains no secret this project does not already have in
  # plaintext elsewhere. SSE-S3 is free and is applied to every object without the caller asking.
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# State files accumulate a version per apply. Without this they accumulate forever. 90 days is long
# enough to recover from any mistake this project could plausibly make and short enough that the object
# count stays in the free tier indefinitely.
resource "aws_s3_bucket_lifecycle_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    id     = "expire-noncurrent-state-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.tfstate]
}

# Deny any request that did not arrive over TLS. S3 is HTTPS by default from every modern SDK, so this
# changes nothing in practice and costs nothing -- it closes the case where something old or hand-rolled
# talks to the bucket in the clear.
resource "aws_s3_bucket_policy" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  policy = data.aws_iam_policy_document.tfstate.json

  depends_on = [aws_s3_bucket_public_access_block.tfstate]
}

data "aws_iam_policy_document" "tfstate" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.tfstate.arn,
      "${aws_s3_bucket.tfstate.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
