output "budget_name" {
  description = "Name of the project budget, for `aws budgets describe-budget` verification."
  value       = aws_budgets_budget.project.name
}

output "sns_topic_arn" {
  description = "Budget-alert SNS topic ARN."
  value       = aws_sns_topic.budget_alerts.arn
}

output "sns_subscription_arn" {
  description = "Email subscription ARN. Reads \"PendingConfirmation\" until Marco clicks the confirmation link."
  value       = aws_sns_topic_subscription.alert_email.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name, criterion 2."
  value       = aws_cloudwatch_dashboard.cost.dashboard_name
}

output "operational_dashboard_name" {
  description = "CloudWatch dashboard name, criterion 3 (Stage B1 -- Lambda/Lex native panels + the guardrail-usage log widget; B2's turn-latency panel is not in this dashboard yet)."
  value       = aws_cloudwatch_dashboard.operational.dashboard_name
}

output "ce_pull_lambda_arn" {
  value = aws_lambda_function.ce_pull.arn
}

output "ce_pull_schedule_arn" {
  value = aws_scheduler_schedule.ce_pull_weekly.arn
}

output "cost_metric_namespace" {
  value = var.cost_metric_namespace
}

output "cost_metric_name" {
  value = var.cost_metric_name
}
