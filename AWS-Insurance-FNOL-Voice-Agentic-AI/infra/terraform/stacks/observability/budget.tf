/*
 * The budget alarm. Criterion 1.
 *
 * IncludeCredit:false / IncludeRefund:false -- docs/RESULTS.md §18 documents a live, sibling-project
 * instance of what happens without this: `bedrock-platform-marco-demo01-monthly` reads
 * ActualSpend:$0.00 while its tagged workload has real usage, because this account's credits currently
 * offset ~100% of net cost. Net cost is what the API returns by default; these two flags are what force
 * the budget to watch gross usage instead, per CLAUDE.md's own verified-environment-facts table.
 *
 * No `notification` block here has an `automatic_action` -- this is a monitoring-only, non-action
 * budget. AWS Budgets' free tier ("monitor and receive notifications, free of charge") is unconditional
 * for exactly this shape; the $0.10/day charge is specific to action-enabled budgets, which this is not.
 */

resource "aws_budgets_budget" "project" {
  name         = "fnol-voice-agent-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name = "TagKeyValue"
    # "user:<TagKey>$<TagValue>" -- the legacy CostFilters format Budgets still expects for a tag filter.
    # format() rather than string interpolation: "$${var.project_tag}" is Terraform's escape sequence
    # for a literal "${", which would silently emit the variable REFERENCE as text instead of its value.
    values = [format("user:Project$%s", var.project_tag)]
  }

  cost_types {
    include_credit = false
    include_refund = false
  }

  # Real, permanent notification -- 80% of $20 = $16.
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Real, permanent notification -- 100% of $20 = $20, one dollar short of the project's own hard $25 ceiling.
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # The TEMPORARY synthetic-breach test notification (ABSOLUTE_VALUE, test_breach_threshold_usd) that
  # lived here has been removed -- OI1/D93/OI10, 2026-08-16. It did its job: threshold $0.25 against
  # $0.4795 tagged MTD spend, applied, NotificationState:ALARM confirmed live within a minute, real
  # breach email received and confirmed by Marco 18:45 local the same day (ACTUAL $0.71 at fire time).
  # Removing it now, per Marco's explicit instruction, so a hair-trigger alert set up for one proof
  # doesn't become a permanent fixture. See PROJECT_STATE.md's OI1 row for the full chain.

  depends_on = [aws_sns_topic_policy.budget_alerts]
}
