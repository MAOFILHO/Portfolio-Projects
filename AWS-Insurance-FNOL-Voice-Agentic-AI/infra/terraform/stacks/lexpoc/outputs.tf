/*
 * These outputs are the "declared" half of the gate. `scripts/lexpoc_gate.py` reads them, then reads the
 * same three facts from the Lex service, and compares. Neither half is allowed to be the other's source.
 */

output "bot_id" {
  description = "Lex bot id, from the nested stack's own output."
  value       = aws_cloudformation_stack.bot.outputs["BotId"]
}

output "bot_arn" {
  description = "Lex bot ARN. Used to check that the stack's tags actually reached the bot."
  value       = aws_cloudformation_stack.bot.outputs["BotArn"]
}

output "declared_policy_number_initial_prompt" {
  description = "The prompt string Terraform rendered into the template on this apply."
  value       = var.policy_number_initial_prompt
}

output "declared_dtmf_end_timeout_ms" {
  description = "The DTMF EndTimeoutMs Terraform rendered into the template on this apply."
  value       = var.dtmf_end_timeout_ms
}

output "control_dtmf_end_timeout_ms" {
  description = <<-EOT
    The negative control: police_report_number's DTMF EndTimeoutMs is hardcoded in the template and must
    never move. Exported so the gate asserts an expected NON-change alongside the expected changes.
  EOT
  value       = 5000
}

output "template_sha256" {
  description = <<-EOT
    Hash of the rendered template body. Two applies that produce the same hash cannot have tested
    anything, and a gate that ran twice against an unchanged template would report a confident pass.
  EOT
  value       = sha256(local.template_body)
}
