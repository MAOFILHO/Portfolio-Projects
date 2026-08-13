/*
 * Everything here describes a resource that ALREADY EXISTS. No default in this file may be treated as a
 * request to create something -- if a value is wrong, the correct outcome is a failed guard, not a new
 * phone number.
 */

variable "region" {
  description = "AWS region. Constraint 17 fixes this at us-west-2 for every stack in this project."
  type        = string
  default     = "us-west-2"
}

variable "account_id" {
  description = "Account holding the pre-existing Connect instance and DID."
  type        = string
  default     = "759316130780"
}

variable "phone_number_id" {
  description = "ID of the ALREADY-CLAIMED DID. Imported, never created. Releasing it risks a 180-day claim block."
  type        = string
  default     = "55cba0a6-3f67-4982-b3d8-6943d3b07054"
}

variable "phone_number_country_code" {
  description = "CA, not US. The DID is Canadian -- a fact that has surprised this project more than once."
  type        = string
  default     = "CA"

  validation {
    # country_code is ForceNew on aws_connect_phone_number: changing it plans a replace, which means
    # release-and-reclaim. `prevent_destroy` would catch that, but failing here says why.
    condition     = var.phone_number_country_code == "CA"
    error_message = "The claimed number is Canadian. Changing country_code forces replacement, which releases the DID."
  }
}

variable "phone_number_description" {
  description = "Must match the live description or the plan shows a spurious change."
  type        = string
  default     = "AI IVR FNOL prototype"
}

variable "connect_instance_arn" {
  description = "ARN of the PRE-EXISTING Connect instance. Never created by this project."
  type        = string
  default     = "arn:aws:connect:us-west-2:759316130780:instance/eba56246-0368-4f1c-8b97-e2ab3b0e8246"
}

variable "project_tag" {
  description = "Value of the Project cost allocation tag. Must match the budget alarm's filter exactly."
  type        = string
  default     = "AWS-Insurance-FNOL-Voice-Agentic-AI"
}
