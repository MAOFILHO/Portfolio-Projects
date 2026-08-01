resource "aws_ecs_cluster" "this" {
  name = var.project_name
  # No Container Insights, no capacity providers to reserve — Fargate is billed
  # per-task, so an empty cluster costs nothing between deploys.
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "this" {
  family                   = var.project_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.fargate_cpu
  memory                   = var.fargate_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  # Graviton (ARM64) Fargate pricing is ~20% cheaper than X86_64 for the same
  # cpu/memory, and it's what this image is built for.
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = var.project_name
      image     = "${aws_ecr_repository.this.repository_url}:latest"
      essential = true
      portMappings = [
        { containerPort = var.container_port, protocol = "tcp" }
      ]
      environment = [
        { name = "SHOWCASE_RESEARCH_MODEL", value = var.research_model },
        { name = "SHOWCASE_FAST_MODEL", value = var.fast_model },
        { name = "SHOWCASE_MAX_REVISIONS", value = tostring(var.max_revisions) },
        { name = "SHOWCASE_DEMO_USER", value = var.demo_username }
      ]
      secrets = [
        { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key.arn },
        { name = "SHOWCASE_DEMO_PASSWORD", valueFrom = aws_secretsmanager_secret.demo_password.arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }
    }
  ])

  # The `deploy` workflow only rolls a new *image* onto the existing
  # `:latest` tag and force-deploys — it never registers its own task
  # definition revision, so Terraform can fully own container_definitions
  # (cpu/memory/env/secrets) without the two fighting each other.
}

resource "aws_ecs_service" "this" {
  name            = var.project_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = var.project_name
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]
}
