variable "aws_region" {
  description = "AWS region for the Terraform state bucket and lock table. Must be us-east-1."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "aws_region must be us-east-1 — the only region where Amazon Nova custom models support on-demand inference."
  }
}

variable "aws_profile" {
  description = "AWS CLI profile to use."
  type        = string
  default     = null
}

variable "project_suffix" {
  description = "Stable, unique suffix for naming (never random — random suffixes orphan billable resources)."
  type        = string
}
