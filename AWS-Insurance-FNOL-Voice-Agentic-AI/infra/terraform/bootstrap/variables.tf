/*
 * Constraint 17: region is a variable, never a literal in application code, and a region migration must
 * be a tfvars change rather than a refactor.
 */

variable "region" {
  description = "AWS region. Constraint 17 fixes this at us-west-2 for every stack in this project."
  type        = string
  default     = "us-west-2"
}

# The value the budget alarm filters on. It is a variable rather than a literal because the alarm, the
# provider default_tags in every stack, and this bucket all have to agree on one string -- and a
# tag-filtered alarm whose filter does not match the tag it is filtering for reports $0 forever and is
# indistinguishable from being under budget. Phase 8 criterion 9.
variable "project_tag" {
  description = "Value of the Project cost allocation tag. Must match the budget alarm's filter exactly."
  type        = string
  default     = "AWS-Insurance-FNOL-Voice-Agentic-AI"
}
