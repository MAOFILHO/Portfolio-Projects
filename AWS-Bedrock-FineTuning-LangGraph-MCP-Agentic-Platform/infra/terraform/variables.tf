variable "project_suffix" {
  description = "Stable, unique suffix for resource naming. Required — no default. Never random; a random suffix orphans billable resources on every re-apply."
  type        = string
}

variable "aws_region" {
  description = <<-EOT
    AWS region. Must be us-east-1 or us-west-2 — the only two regions where Bedrock supports
    Custom Model on-Demand deployment, which this project depends on to avoid Provisioned
    Throughput's hourly billing (see COSTS.md §2).

    Which region you need is determined by the base model, since customization is single-region
    per model family:
      us-east-1  Amazon Nova (Micro / Lite / 2 Lite / Pro)
      us-west-2  Meta Llama 3.3 70B Instruct
  EOT
  type        = string
  default     = "us-east-1"

  validation {
    condition     = contains(["us-east-1", "us-west-2"], var.aws_region)
    error_message = "aws_region must be us-east-1 or us-west-2 — the only regions supporting Custom Model on-Demand."
  }
}

variable "aws_profile" {
  description = "AWS CLI profile to use."
  type        = string
  default     = null
}

variable "budget_limit_usd" {
  description = "Monthly AWS Budgets ceiling in USD."
  type        = number
  default     = 25
}

variable "budget_alert_email" {
  description = "Email address for budget threshold notifications. Required — never invented."
  type        = string
}

# --- GitHub Actions OIDC (optional) -----------------------------------------------
# Disabled by default: creating it makes real IAM resources, and a repository that has
# not been pushed to GitHub yet has nothing to trust. Enable deliberately.

variable "enable_github_oidc" {
  description = "Create the read-only GitHub Actions plan role. Requires github_owner and github_repo."
  type        = bool
  default     = false

  validation {
    condition     = !var.enable_github_oidc || (var.github_owner != "" && var.github_repo != "")
    error_message = "github_owner and github_repo must be set when enable_github_oidc is true."
  }
}

variable "github_owner" {
  description = "GitHub user or organisation that owns the repository."
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "Repository name, without the owner prefix."
  type        = string
  default     = ""
}

variable "create_oidc_provider" {
  description = "Set false if this account already has a token.actions.githubusercontent.com provider."
  type        = bool
  default     = true
}

variable "existing_oidc_provider_arn" {
  description = "ARN of an existing GitHub OIDC provider, when create_oidc_provider is false."
  type        = string
  default     = null
}
