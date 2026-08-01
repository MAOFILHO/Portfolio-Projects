resource "aws_ecr_repository" "this" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE" # simplicity for a demo; use IMMUTABLE + per-commit tags in prod

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the 5 most recent untagged images so storage cost doesn't creep up.
resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images beyond the 5 most recent"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = { type = "expire" }
      }
    ]
  })
}
