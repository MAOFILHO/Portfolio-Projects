/*
 * `stacks/main` consumes `phone_number_arn` to attach a contact flow. It reads it from the backend via a
 * `terraform_remote_state` data source rather than hardcoding it, so there is exactly one place in the
 * repository that says which number this project owns.
 *
 * `guard_observed_protected_tag` exists so the guard's evidence is visible in `terraform output`, not
 * only inside a precondition that is silent when it passes. A control you cannot see succeed is one you
 * find out about only when it fails.
 */

output "phone_number" {
  description = "The E.164 number. Canadian."
  value       = aws_connect_phone_number.did.phone_number
}

output "phone_number_arn" {
  description = "ARN of the protected DID. Consumed by stacks/main to attach a contact flow."
  value       = aws_connect_phone_number.did.arn
}

output "phone_number_id" {
  description = "ID of the protected DID."
  value       = aws_connect_phone_number.did.id
}

output "guard_observed_protected_tag" {
  description = "What the import guard actually read from the live resource. Must be \"true\"."
  value       = local.protected_tag
}
