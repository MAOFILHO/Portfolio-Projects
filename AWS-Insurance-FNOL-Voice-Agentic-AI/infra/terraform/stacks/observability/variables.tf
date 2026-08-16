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

variable "test_breach_threshold_usd" {
  description = <<-EOT
    Temporary synthetic-breach notification, docs/RESULTS.md §19, corrected §39/§FIX-D93 2026-08-16. The
    original $2.00 figure was set against the account-WIDE untagged MTD gross usage ($3.78) -- but
    budget.tf's own cost_filter scopes this budget's evaluation to Project=AWS-Insurance-FNOL-Voice-
    Agentic-AI-tagged spend only, which was never past $2.00 (D93/OI10: confirmed $0.48 MTD, twice,
    against `aws budgets describe-budget`'s own CalculatedSpend.ActualSpend to the cent). $2.00 could
    never have fired under this budget's actual scope.

    Re-derived from a fresh `ce get-cost-and-usage` call, GroupBy Type=TAG,Key=Project, RECORD_TYPE=Usage
    (same methodology as D93's original diagnosis): this project's tagged MTD spend is $0.4795457178,
    unchanged to 10 decimal places from D93's own measurement (CE's known ~24h processing lag, not zero
    new spend). Set at $0.25 -- comfortably below that figure (47% margin, wider than the original
    design's own 53% margin against its now-corrected reference number), so it is certain to already be
    breached at the first Budgets evaluation cycle after apply, against the number this budget actually
    watches.

    REMOVE THIS after Marco confirms receipt of the breach email -- tracked as an open item in
    PROJECT_STATE.md so a hair-trigger alert does not become permanent.
  EOT
  type        = number
  default     = 0.25
}

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
