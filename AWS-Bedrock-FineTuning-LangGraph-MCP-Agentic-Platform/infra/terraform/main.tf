data "aws_caller_identity" "current" {}

# Budget alerts must exist before any billable resource — every other module
# depends on it so `terraform apply` always creates the budget first.
module "budget_alerts" {
  source = "./modules/budget_alerts"

  project_suffix   = var.project_suffix
  budget_limit_usd = var.budget_limit_usd
  alert_email      = var.budget_alert_email
}

module "s3_data" {
  source = "./modules/s3_data"

  project_suffix = var.project_suffix
  aws_region     = var.aws_region

  depends_on = [module.budget_alerts]
}

module "iam_bedrock_role" {
  source = "./modules/iam_bedrock_role"

  project_suffix   = var.project_suffix
  aws_account_id   = data.aws_caller_identity.current.account_id
  aws_region       = var.aws_region
  data_bucket_name = module.s3_data.bucket_name
  data_bucket_arn  = module.s3_data.bucket_arn

  depends_on = [module.budget_alerts]
}

module "observability" {
  source = "./modules/observability"

  project_suffix = var.project_suffix

  depends_on = [module.budget_alerts]
}

# Read-only role assumed by .github/workflows/terraform.yml for `plan`. Opt-in via
# enable_github_oidc — see modules/github_oidc for why it can plan but never apply.
module "github_oidc" {
  source = "./modules/github_oidc"
  count  = var.enable_github_oidc ? 1 : 0

  project_suffix             = var.project_suffix
  github_owner               = var.github_owner
  github_repo                = var.github_repo
  aws_region                 = var.aws_region
  state_bucket               = "bedrock-platform-${var.project_suffix}-tfstate"
  lock_table                 = "bedrock-platform-${var.project_suffix}-tflock"
  create_oidc_provider       = var.create_oidc_provider
  existing_oidc_provider_arn = var.existing_oidc_provider_arn
}
