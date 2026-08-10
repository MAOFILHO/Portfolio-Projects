#!/usr/bin/env bash
# One-time bootstrap of the Terraform remote state bucket + DynamoDB lock table.
# Run this once, before the first `terraform init` in infra/terraform/. Billable —
# creates real S3 + DynamoDB resources (both effectively free at this scale, but real).
set -euo pipefail

cd "$(dirname "$0")/../infra/terraform/bootstrap"

if [[ -z "${PROJECT_SUFFIX:-}" ]]; then
  echo "ERROR: PROJECT_SUFFIX env var is required (stable naming, never random)." >&2
  exit 1
fi

terraform init
terraform apply -var="project_suffix=${PROJECT_SUFFIX}"

echo
echo "Bootstrap complete. Record these outputs in infra/terraform/backend.tf:"
terraform output
