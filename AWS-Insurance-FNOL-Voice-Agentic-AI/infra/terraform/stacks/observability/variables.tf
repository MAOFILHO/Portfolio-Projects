variable "region" {
  description = "AWS region. Constraint 17 fixes this at us-west-2 for every stack in this project. Cost Explorer is the one stated, named exception -- see main.tf."
  type        = string
  default     = "us-west-2"
}

variable "project_tag" {
  description = "Value of the Project cost allocation tag. Must match the budget's cost filter exactly."
  type        = string
  default     = "AWS-Insurance-FNOL-Voice-Agentic-AI"
}

variable "alert_email" {
  description = "Address subscribed to the SNS topic. Requires a one-time click on the SNS subscription-confirmation email before any notification -- test or real -- can deliver."
  type        = string
  default     = "djmau1974@gmail.com"
}

variable "budget_limit_usd" {
  description = <<-EOT
    Monthly budget ceiling this alarm watches. $20, deliberately under CLAUDE.md's hard $25 ceiling so the
    80%/100% notifications ($16/$20) fire before the project's own stated limit, not at it.
  EOT
  type        = number
  default     = 20
}

# test_breach_threshold_usd (temporary synthetic-breach notification, docs/RESULTS.md §19/§39) removed
# 2026-08-16, OI1 -- it fired, Marco confirmed the breach email, its job is done. See budget.tf's comment
# and PROJECT_STATE.md's OI1 row for the full chain.

variable "cost_metric_namespace" {
  description = "CloudWatch namespace the CE-pull Lambda writes to and the dashboard reads from."
  type        = string
  default     = "FNOL/Observability"
}

variable "cost_metric_name" {
  description = "Custom metric name for MTD gross usage (RECORD_TYPE=Usage), written weekly."
  type        = string
  default     = "MTDGrossUsageUSD"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for the CE-pull Lambda. Matches stacks/main's 14-day convention."
  type        = number
  default     = 14
}
