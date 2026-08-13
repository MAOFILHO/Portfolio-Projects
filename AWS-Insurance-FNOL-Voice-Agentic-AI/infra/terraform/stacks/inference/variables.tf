/*
 * Constraint 17: region is a variable, never a literal in application code, and a region migration must
 * be a tfvars change rather than a refactor.
 */

variable "region" {
  description = "AWS region. Constraint 17 fixes this at us-west-2 for every stack in this project."
  type        = string
  default     = "us-west-2"
}

variable "project_tag" {
  description = "Value of the Project cost allocation tag. Must match the budget alarm's filter exactly."
  type        = string
  default     = "AWS-Insurance-FNOL-Voice-Agentic-AI"
}
