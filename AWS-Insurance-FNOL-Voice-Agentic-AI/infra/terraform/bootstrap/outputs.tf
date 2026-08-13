/*
 * These outputs are what every other stack's `backend "s3"` block needs. They are printed by
 * `make bootstrap` so the values can be checked against what the backend blocks already hardcode --
 * a backend block cannot interpolate variables, so the bucket name is necessarily duplicated as a
 * literal in each stack, and this output is how that duplication gets verified rather than trusted.
 */

output "state_bucket" {
  description = "S3 bucket holding every stack's state except this one's."
  value       = aws_s3_bucket.tfstate.id
}

output "state_bucket_arn" {
  description = "ARN of the state bucket."
  value       = aws_s3_bucket.tfstate.arn
}

output "region" {
  description = "Region the backend lives in. Must match every backend block's `region`."
  value       = var.region
}
