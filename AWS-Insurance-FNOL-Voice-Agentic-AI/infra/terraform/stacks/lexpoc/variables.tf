variable "region" {
  description = "Single-region rule, constraint 17. Never a literal in application code."
  type        = string
  default     = "us-west-2"
}

variable "project_tag" {
  description = "Cost allocation tag key the Phase 8 budget alarm filters on."
  type        = string
  default     = "AWS-Insurance-FNOL-Voice-Agentic-AI"
}

variable "bot_name" {
  description = "Name of the throwaway bot and of the CloudFormation stack that carries it."
  type        = string
  default     = "fnol-lexpoc"

  validation {
    # Lex enforces `^([0-9a-zA-Z][_-]?)+$` on bot names and rejects the request outright otherwise.
    condition     = can(regex("^([0-9a-zA-Z][_-]?)+$", var.bot_name))
    error_message = "bot_name must match Lex's ^([0-9a-zA-Z][_-]?)+$ — alphanumerics with single _ or - between them."
  }
}

# ---------------------------------------------------------------------------------------------------
# The two values the gate moves.
#
# Both are rendered into `bot.yaml.tftpl` and both are re-exported as outputs, so `scripts/lexpoc_gate.py`
# can compare what Terraform SENT against what the Lex service REPORTS without a second copy of either
# string existing anywhere. Changing a default here and re-applying is the "change a prompt and apply
# again" half of ADR-007's gate, and the git diff of this file is the record of what changed.
# ---------------------------------------------------------------------------------------------------

variable "policy_number_initial_prompt" {
  description = "First-attempt elicitation prompt for policy_number. Moved by the second apply."
  type        = string

  # SECOND APPLY, 2026-08-12. Was: "What's your policy number?" — recorded in
  # `docs/evidence/phase8/lexpoc-apply-1.json` and in this file's git history, which is the point: the
  # gate needs a before value that cannot be reconstructed after the fact from the deployed bot.
  default = "Okay. What is your policy number? It starts with P Y."
}

variable "dtmf_end_timeout_ms" {
  description = <<-EOT
    DTMF EndTimeoutMs on policy_number's retry attempts. Moved by the second apply.

    A string prompt and a nested integer are different enough to be worth testing both: #42147 is
    reported against prompt specifications, while #36845 was an "inconsistent result after apply" on
    prompt-attempt settings. A mechanism could plausibly get one right and the other wrong.
  EOT
  type        = number

  # SECOND APPLY, 2026-08-12. Was: 5000 — which is still the hardcoded value on the control slot, so
  # after this change the two slots disagree and only one of them was ever supposed to move.
  default = 3000
}
