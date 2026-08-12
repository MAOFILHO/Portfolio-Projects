variable "project_suffix" {
  description = "Stable project namespace, e.g. marco-demo01."
  type        = string
}

variable "github_owner" {
  description = "GitHub user or organisation that owns the repository."
  type        = string
}

variable "github_repo" {
  description = "Repository name, without the owner prefix."
  type        = string
}

variable "aws_region" {
  description = "Region whose resources the plan role may read."
  type        = string
}

variable "state_bucket" {
  description = "Terraform remote state bucket. Read-only access is granted to it."
  type        = string
}

variable "lock_table" {
  description = "DynamoDB lock table. Read-only access is granted to it."
  type        = string
}

variable "create_oidc_provider" {
  description = <<-EOT
    Whether to create the GitHub OIDC provider.

    An AWS account may hold only ONE OIDC provider per issuer URL. If another stack in
    this account already registered token.actions.githubusercontent.com, set this to
    false and pass the existing ARN via existing_oidc_provider_arn — creating a second
    one fails with EntityAlreadyExists.
  EOT
  type        = bool
  default     = true
}

variable "existing_oidc_provider_arn" {
  description = "ARN of an already-registered GitHub OIDC provider. Required when create_oidc_provider is false."
  type        = string
  default     = null

  validation {
    condition     = var.create_oidc_provider || var.existing_oidc_provider_arn != null
    error_message = "existing_oidc_provider_arn must be set when create_oidc_provider is false."
  }
}

variable "allowed_branches" {
  description = <<-EOT
    Git refs whose workflow runs may assume the role. Pull requests from forks never
    receive these credentials — GitHub does not expose secrets or OIDC to forked PRs —
    so the plan job skips itself there rather than failing.
  EOT
  type        = list(string)
  default     = ["refs/heads/main"]
}
