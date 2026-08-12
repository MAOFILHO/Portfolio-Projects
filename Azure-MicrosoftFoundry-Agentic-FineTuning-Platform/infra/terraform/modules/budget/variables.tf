variable "resource_group_id" {
  description = "ID of the resource group the budget watches."
  type        = string
}

variable "budget_name" {
  type = string
}

variable "amount_usd" {
  description = "Monthly budget ceiling in USD."
  type        = number
}

variable "contact_emails" {
  description = "Emails notified at each threshold. Empty list is valid — the budget still exists and is visible in the portal, it just has no email action group."
  type        = list(string)
  default     = []
}

variable "start_date" {
  description = "Budget period start, RFC3339, must be the first of a month."
  type        = string
}
