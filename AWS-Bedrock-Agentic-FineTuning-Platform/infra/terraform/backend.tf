# Partial backend configuration — Terraform backend blocks cannot reference variables,
# so bucket/key/dynamodb_table are supplied at `terraform init` time via
# -backend-config (see Makefile's `provision` target and
# scripts/bootstrap_state.sh's printed outputs).
terraform {
  backend "s3" {
    region  = "us-east-1"
    encrypt = true
  }
}
