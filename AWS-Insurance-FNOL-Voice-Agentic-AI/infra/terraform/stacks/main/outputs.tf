/*
 * Outputs are consumed by three things: `make verify-lex` (which reads the DECLARED values back and
 * compares them against what the service reports), Stage 4's DID association, and whoever is trying to
 * work out what a `make deploy` actually produced.
 *
 * The declared-value outputs exist for the same reason `stacks/lexpoc`'s did at Stage 2: a verifier that
 * compares the service against a second copy of the expected value is comparing two things that can
 * drift apart. These outputs and the CloudFormation template body are rendered from one `templatefile`
 * call, so there is one source.
 */

output "bot_id" {
  description = "Lex bot id."
  value       = aws_cloudformation_stack.bot.outputs["BotId"]
}

output "bot_arn" {
  description = "Lex bot ARN."
  value       = aws_cloudformation_stack.bot.outputs["BotArn"]
}

output "bot_alias_id" {
  description = "Alias id. Needed by RecognizeText probes."
  value       = aws_cloudformation_stack.release.outputs["BotAliasId"]
}

output "bot_alias_arn" {
  description = "Alias ARN, as associated with Connect and as referenced by the contact flow."
  value       = aws_cloudformation_stack.release.outputs["BotAliasArn"]
}

output "bot_version" {
  description = <<-EOT
    Published version the alias points at.

    This is the number `RESULTS.md` §3.5.1 rule 2 is about: the alias serving a stale version is
    indistinguishable from a correct deployment in every artifact except this one and the service's own
    read of it. `make verify-lex` compares the two.
  EOT
  value       = aws_cloudformation_stack.release.outputs["BotVersion"]
}

output "bot_definition_hash" {
  description = "Hash of the bot definition this version was published from. Drives the version's CFN logical ID."
  value       = local.bot_definition_hash
}

output "declared_policy_number_prompt" {
  description = "What Terraform sent as policy_number's first-attempt prompt. Compared against the deployed bot."
  value       = var.policy_number_prompt
}

output "declared_dtmf_end_timeout_ms" {
  description = "What Terraform sent as the DTMF end timeout. Compared against the deployed bot."
  value       = var.dtmf_end_timeout_ms
}

output "declared_obfuscated_slots" {
  description = <<-EOT
    Slots that must report `DefaultObfuscation` on the deployed bot, derived from the rendered template
    rather than restated.

    `D70` made obfuscation a decision rather than a default, and a decision nobody checks is a preference.
  EOT
  value       = local.obfuscated_slots
}

# ---------------------------------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------------------------------

output "contact_flow_id" {
  description = "Inbound flow id. Stage 4 associates the DID with this."
  value       = aws_connect_contact_flow.inbound.contact_flow_id
}

output "contact_flow_name" {
  description = "Flow name, carrying the content hash. A new content hash is a new flow, not an edit."
  value       = aws_connect_contact_flow.inbound.name
}

output "flow_version" {
  description = "Content hash of the deployed flow. Also the `FlowVersion` contact tag."
  value       = local.flow_version
}

output "queue_id" {
  description = "Escalation queue. Unused by the flow until Stage 6 wires D43."
  value       = aws_connect_queue.escalation.queue_id
}

output "connect_instance_created_time" {
  description = <<-EOT
    Criterion 2's evidence: the instance was never created or re-created by this project.

    Recorded as an output rather than checked by eye, so a re-creation shows up as a diff in the one
    place anyone reads after an apply.
  EOT
  value       = data.aws_connect_instance.this.created_time
}

# ---------------------------------------------------------------------------------------------------
# Compute and storage
# ---------------------------------------------------------------------------------------------------

output "codehook_function_name" {
  description = "Lex V2 codehook."
  value       = aws_lambda_function.codehook.function_name
}

output "codehook_function_arn" {
  description = "Codehook ARN, as granted to Lex and to Connect."
  value       = aws_lambda_function.codehook.arn
}

output "checkpoint_table_name" {
  description = "LangGraph checkpointer table."
  value       = aws_dynamodb_table.checkpoints.name
}

output "vector_table_name" {
  description = "Knowledge-chunk table. `make ingest` writes here."
  value       = aws_dynamodb_table.knowledge_chunks.name
}

output "artifact_bucket" {
  description = "Post-call artifacts. Lifecycle-expired, unversioned — see storage.tf."
  value       = aws_s3_bucket.artifacts.id
}
