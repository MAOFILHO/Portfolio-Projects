/*
 * These outputs are what `BedrockGuardrailClient` needs. It takes both as required constructor
 * arguments and has no default resource ID -- so a misconfigured deploy fails loudly at construction
 * rather than silently evaluating against the wrong guardrail.
 */

output "guardrail_id" {
  description = "Guardrail identifier for ApplyGuardrail."
  value       = aws_bedrock_guardrail.fnol.guardrail_id
}

output "guardrail_arn" {
  description = "Guardrail ARN."
  value       = aws_bedrock_guardrail.fnol.guardrail_arn
}

output "guardrail_version" {
  description = "Published version. Pinned rather than DRAFT so a red-team result is attributable to one configuration."
  value       = aws_bedrock_guardrail_version.fnol.version
}
