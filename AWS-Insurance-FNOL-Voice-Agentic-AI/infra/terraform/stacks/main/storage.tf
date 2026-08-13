/*
 * DynamoDB tables and the artifacts bucket.
 *
 * BILLING MODE IS A COST DECISION, NOT A DEFAULT
 *   Both tables are `PAY_PER_REQUEST`. `CLAUDE.md`'s free-tier note is explicit that DynamoDB's
 *   always-free layer covers **25 GB of storage only** and NOT free RCU/WCU in on-demand mode -- so
 *   on-demand is not chosen because it is free, it is chosen because provisioned capacity bills for
 *   idle hours and this system is idle almost all of the time. At demo volume the request charge is
 *   fractions of a cent; at idle it is zero, which provisioned capacity cannot say.
 */

resource "aws_dynamodb_table" "checkpoints" {
  name         = var.checkpoint_table_name
  billing_mode = "PAY_PER_REQUEST"

  # Fixed by langgraph-checkpoint-aws's own repository layer, confirmed by reading it rather than
  # inferred -- see `src/fnol_voice_agent/aws/checkpointer.py`. Changing either name here silently breaks
  # every checkpoint write with a validation error at runtime, on a live call.
  hash_key  = "PK"
  range_key = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # Conversation state for a call that ended is dead weight and, per `ADR-011`, is state about a person.
  # The checkpointer writes no TTL attribute today, so this expires nothing yet; it is declared now so
  # that the day something writes `expires_at`, the sweep already exists rather than being remembered.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    # Off. PITR bills per GB of continuous backup and this table holds transient conversation state whose
    # loss costs one caller one repeated question. Recovering it is not worth a standing charge.
    enabled = false
  }

  server_side_encryption {
    # AWS-owned key. `enabled = false` here does not mean unencrypted -- DynamoDB encrypts every table at
    # rest unconditionally; this selects the AWS-owned key over a customer-managed KMS key, which would
    # add a $1/month key charge and per-request KMS calls for no threat this project faces.
    enabled = false
  }
}

resource "aws_dynamodb_table" "knowledge_chunks" {
  name         = var.vector_table_name
  billing_mode = "PAY_PER_REQUEST"

  # Single partition key, no sort key -- `ingest.py`'s `DynamoVectorStore`, which stores both `CHUNK#...`
  # and `STATE#...` items under one `pk`.
  hash_key = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  point_in_time_recovery {
    # Off, and for a stronger reason than the checkpoint table's: this table is fully reproducible from
    # `data/synthetic/` by `make ingest`. A backup of derived data is a backup of a build step.
    enabled = false
  }

  server_side_encryption {
    enabled = false
  }
}

# ---------------------------------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  # Account-scoped rather than globally guessable. S3 bucket names are a global namespace, so an
  # unsuffixed `fnol-artifacts` would either collide or be squattable.
  bucket        = "${local.name_prefix}-artifacts-${local.account_id}-${var.region}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    # Off, deliberately, and this is the one place in the project where versioning is declined.
    #
    # The state bucket is versioned because a lost state file orphans the protected DID. This bucket
    # holds post-call artifacts, which are `ADR-011` material: versioning would keep a pre-redaction
    # object recoverable after the redacted one replaced it, which is the opposite of what the retention
    # rule below is for. A delete that does not delete is not a retention control.
    status = "Disabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  # The provider requires versioning to be settled before a lifecycle rule references expiry semantics.
  depends_on = [aws_s3_bucket_versioning.artifacts]

  rule {
    id     = "expire-artifacts"
    status = "Enabled"

    filter {}

    expiration {
      days = var.artifact_retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}
