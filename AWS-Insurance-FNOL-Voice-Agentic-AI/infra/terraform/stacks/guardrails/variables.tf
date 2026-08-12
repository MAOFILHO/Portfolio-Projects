/*
 * Constraint 17: region is a variable, never a literal in application code, and a region migration must
 * be a tfvars change rather than a refactor.
 */

variable "region" {
  description = "AWS region. Constraint 17 fixes this at us-west-2 for every stack in this project."
  type        = string
  default     = "us-west-2"
}

variable "guardrail_name" {
  description = "Guardrail resource name. Findable by name if local state is ever lost."
  type        = string
  default     = "fnol-voice-agent-guardrail"
}
