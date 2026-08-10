variable "project_suffix" {
  type = string
}

variable "aws_region" {
  description = "Region this bucket lives in. Part of the bucket name — see main.tf."
  type        = string
}
