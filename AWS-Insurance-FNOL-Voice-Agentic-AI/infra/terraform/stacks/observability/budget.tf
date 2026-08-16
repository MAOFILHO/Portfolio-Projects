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

  # TEMPORARY -- firing-proof for criterion 1, docs/RESULTS.md §17.3/§19. ABSOLUTE_VALUE, not a percent
  # of budget_limit_usd, so it stays fixed at test_breach_threshold_usd regardless of the budget ceiling.
  # Set comfortably below the real re-verified MTD gross usage ($3.7828941608, 2026-08-15) so it is
  # already breached at the first Budgets evaluation after apply.
  #
  # REMOVE ONCE MARCO CONFIRMS RECEIPT OF THE BREACH EMAIL -- tracked as an open item in
  # PROJECT_STATE.md. Left live, this is a permanent $2.00 hair-trigger alert.
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = var.test_breach_threshold_usd
    threshold_type            = "ABSOLUTE_VALUE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  depends_on = [aws_sns_topic_policy.budget_alerts]
}
