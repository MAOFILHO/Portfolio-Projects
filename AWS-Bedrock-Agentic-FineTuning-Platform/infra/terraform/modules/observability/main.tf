resource "aws_cloudwatch_log_group" "app" {
  name              = "/bedrock-platform/${var.project_suffix}"
  retention_in_days = 7
}
