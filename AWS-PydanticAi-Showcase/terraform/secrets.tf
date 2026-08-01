resource "aws_secretsmanager_secret" "openai_api_key" {
  name                    = "${var.project_name}/openai-api-key"
  recovery_window_in_days = 0 # demo project — allow immediate deletion on destroy, no 7/30-day hold cost
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "demo_password" {
  name                    = "${var.project_name}/demo-password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "demo_password" {
  secret_id     = aws_secretsmanager_secret.demo_password.id
  secret_string = var.demo_password
}
