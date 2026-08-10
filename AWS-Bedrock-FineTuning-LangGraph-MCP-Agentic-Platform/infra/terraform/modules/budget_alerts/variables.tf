variable "project_suffix" {
  type = string
}

variable "budget_limit_usd" {
  description = "Monthly budget ceiling in USD."
  type        = number
}

variable "alert_email" {
  description = "Email address to notify on budget threshold breaches."
  type        = string
}
