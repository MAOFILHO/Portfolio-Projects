# Auto-loaded by Terraform on every plan/apply/destroy.
#
# These three are committed deliberately: they are not secrets, and they must persist in
# every invocation. Without them a plain `terraform plan` defaults enable_github_oidc to
# false and proposes DESTROYING the GitHub Actions role that CI depends on.
#
# Credentials and PII stay out of this file — project_suffix, aws_region,
# budget_alert_email and budget_limit_usd come from .env via the Makefile, and .env is
# git-ignored.

enable_github_oidc = true
github_owner       = "MAOFILHO"
github_repo        = "Portfolio-Projects"
