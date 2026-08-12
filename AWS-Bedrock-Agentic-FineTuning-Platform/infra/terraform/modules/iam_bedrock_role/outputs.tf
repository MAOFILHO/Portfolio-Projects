output "role_arn" {
  value = aws_iam_role.bedrock_customization.arn
}

output "role_name" {
  value = aws_iam_role.bedrock_customization.name
}
