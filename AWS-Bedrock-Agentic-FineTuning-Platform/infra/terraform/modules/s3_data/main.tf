# Deliberate deviation from the lab guide (PLAN.md §1.9, C2): the guide's steps 5-6
# say to enable ACLs and allow public access to this bucket. That is unnecessary and
# unsafe — Bedrock reads training data via the IAM role in ../iam_bedrock_role, not
# over the public internet. This bucket is fully private: Block Public Access on all
# four settings, ACLs disabled via BucketOwnerEnforced, SSE-S3 encryption, and a
# bucket policy denying any non-TLS request.

# Region is part of the name because S3 bucket names are globally unique while
# buckets themselves are regional. Bedrock customization requires the training data
# bucket to be in the same Region as the job, and the supported Region differs per
# base model (Nova: us-east-1, Llama 3.3: us-west-2) — so the project must be able to
# hold a bucket per Region. Without the suffix, moving Regions means deleting and
# re-creating the same name, which blocks on S3's global name-release delay.
resource "aws_s3_bucket" "data" {
  bucket = "bedrock-platform-${var.project_suffix}-data-${var.aws_region}"
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-output-after-30-days"
    status = "Enabled"

    filter {
      prefix = "output/"
    }

    expiration {
      days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "deny_non_tls" {
  statement {
    sid    = "DenyNonTLS"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket = aws_s3_bucket.data.id
  policy = data.aws_iam_policy_document.deny_non_tls.json
}
