output "plan_role_arn" {
  description = "Set this as the GitHub repository variable AWS_PLAN_ROLE_ARN."
  value       = aws_iam_role.plan.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider in use, whether created here or pre-existing."
  value       = local.provider_arn
}
