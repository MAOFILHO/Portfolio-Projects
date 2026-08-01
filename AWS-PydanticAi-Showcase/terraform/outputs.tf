output "alb_dns_name" {
  description = "Public URL of the app once desired_count > 0"
  value       = "http://${aws_lb.this.dns_name}"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.this.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.this.name
}

output "github_deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN GitHub Actions secret. Empty until github_repository is set."
  value       = var.github_repository == "" ? null : aws_iam_role.github_deploy[0].arn
}
