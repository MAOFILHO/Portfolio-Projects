output "data_bucket_name" {
  value = module.s3_data.bucket_name
}

output "bedrock_role_arn" {
  value = module.iam_bedrock_role.role_arn
}

output "budget_name" {
  value = module.budget_alerts.budget_name
}

output "log_group_name" {
  value = module.observability.log_group_name
}

output "github_actions_plan_role_arn" {
  description = "Set as the GitHub repository variable AWS_PLAN_ROLE_ARN. Null unless enable_github_oidc is true."
  value       = try(module.github_oidc[0].plan_role_arn, null)
}
