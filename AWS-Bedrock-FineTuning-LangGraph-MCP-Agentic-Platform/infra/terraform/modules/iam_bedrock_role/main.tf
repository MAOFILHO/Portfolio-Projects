locals {
  role_name = "bedrock-platform-${var.project_suffix}-customization-role"
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.aws_account_id]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock:${var.aws_region}:${var.aws_account_id}:model-customization-job/*"]
    }
  }
}

resource "aws_iam_role" "bedrock_customization" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.trust.json
}

# Least privilege: read-only on training/validation prefixes, write-only on output/.
# No wildcards on resource ARNs.
data "aws_iam_policy_document" "bedrock_s3_access" {
  statement {
    sid       = "ListBucketDataPrefixes"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.data_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["training-data/*", "validation-data/*", "output/*"]
    }
  }

  statement {
    sid     = "GetTrainingAndValidationObjects"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    resources = [
      "${var.data_bucket_arn}/training-data/*",
      "${var.data_bucket_arn}/validation-data/*",
    ]
  }

  # Bedrock's own preflight writes a temp file to output/ to verify write
  # access, then reads/deletes it back — grant the full read-write-delete
  # cycle it needs on that prefix, not just PutObject.
  statement {
    sid       = "ReadWriteOutputObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${var.data_bucket_arn}/output/*"]
  }
}

resource "aws_iam_role_policy" "bedrock_s3_access" {
  name   = "bedrock-platform-${var.project_suffix}-s3-access"
  role   = aws_iam_role.bedrock_customization.id
  policy = data.aws_iam_policy_document.bedrock_s3_access.json
}
