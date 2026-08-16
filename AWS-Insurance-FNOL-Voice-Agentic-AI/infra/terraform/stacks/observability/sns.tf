/*
 * SNS topic for budget notifications. Standard topic -- 1M requests/mo and 1,000 email deliveries/mo
 * free, permanently, per the free-tier check in docs/RESULTS.md §17.2. A handful of publishes total
 * (firing-proof test + real alerts) is nowhere near either ceiling.
 */

resource "aws_sns_topic" "budget_alerts" {
  name = "fnol-voice-agent-budget-alerts"
}

/*
 * AWS Budgets requires an explicit resource policy on the topic granting the budgets service principal
 * publish rights, scoped to this account -- it does not use the caller's own IAM identity to publish.
 * Without this statement, notifications are configured but silently never delivered.
 */
data "aws_iam_policy_document" "budget_alerts_publish" {
  statement {
    sid    = "AllowBudgetsPublish"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }

    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.budget_alerts.arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "budget_alerts" {
  arn    = aws_sns_topic.budget_alerts.arn
  policy = data.aws_iam_policy_document.budget_alerts_publish.json
}

/*
 * Email subscription. Starts PendingConfirmation -- docs/RESULTS.md §17.3: no notification of any kind,
 * test or real, delivers until Marco clicks the confirmation link AWS sends on create.
 */
resource "aws_sns_topic_subscription" "alert_email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
