/*
 * The CE-pull Lambda + its weekly EventBridge Scheduler trigger. Criterion 2's data pipeline.
 *
 * No layer, no third-party deps -- `lambda_src/ce_pull.py` imports only `boto3` and the standard
 * library, and `boto3` ships inside every Lambda Python runtime. `archive_file` zips the one file
 * directly; there is no `stacks/main`-style deps layer to build here.
 */

locals {
  ce_pull_zip = "${path.module}/.terraform-build/ce-pull.zip"
}

data "archive_file" "ce_pull" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_src"
  output_path = local.ce_pull_zip
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ce_pull" {
  name               = "fnol-voice-agent-ce-pull"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "ce_pull" {
  # Cost Explorer has no resource-level permissions -- ce:GetCostAndUsage is account-scoped, "*" is the
  # only valid resource for this action.
  statement {
    effect    = "Allow"
    actions   = ["ce:GetCostAndUsage"]
    resources = ["*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # PutMetricData does not support resource-level permissions either.

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = [var.cost_metric_namespace]
    }
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.ce_pull.arn}:*"]
  }
}

resource "aws_iam_role_policy" "ce_pull" {
  name   = "ce-pull"
  role   = aws_iam_role.ce_pull.id
  policy = data.aws_iam_policy_document.ce_pull.json
}

resource "aws_cloudwatch_log_group" "ce_pull" {
  name              = "/aws/lambda/fnol-voice-agent-ce-pull"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "ce_pull" {
  function_name    = "fnol-voice-agent-ce-pull"
  role             = aws_iam_role.ce_pull.arn
  handler          = "ce_pull.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.ce_pull.output_path
  source_code_hash = data.archive_file.ce_pull.output_base64sha256

  environment {
    variables = {
      METRIC_NAMESPACE = var.cost_metric_namespace
      METRIC_NAME      = var.cost_metric_name
      METRIC_REGION    = var.region
    }
  }

  depends_on = [
    aws_iam_role_policy.ce_pull,
    aws_cloudwatch_log_group.ce_pull,
  ]
}

# ---------------------------------------------------------------------------------------------------
# Weekly schedule. EventBridge Scheduler, not a classic EventBridge rule -- 14,000,000 invocations/mo
# free, permanent, and it invokes via an IAM role rather than a resource-based Lambda permission, so no
# aws_lambda_permission is needed here.
# ---------------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ce_pull_scheduler" {
  name               = "fnol-voice-agent-ce-pull-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "ce_pull_scheduler" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.ce_pull.arn]
  }
}

resource "aws_iam_role_policy" "ce_pull_scheduler" {
  name   = "invoke-ce-pull"
  role   = aws_iam_role.ce_pull_scheduler.id
  policy = data.aws_iam_policy_document.ce_pull_scheduler.json
}

resource "aws_scheduler_schedule" "ce_pull_weekly" {
  name                = "fnol-voice-agent-ce-pull-weekly"
  schedule_expression = "rate(7 days)"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ce_pull.arn
    role_arn = aws_iam_role.ce_pull_scheduler.arn
  }
}
