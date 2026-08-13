/*
 * `model_ids` is what deployment feeds to the application as FNOL_ROUTER_MODEL_ID and friends.
 *
 * `region_sets` is Marco's verification condition, expressed as an output rather than a claim in a
 * comment. His words on approving `ADR-016`: "verify the wrapped profile actually routes cross-region
 * rather than pinning to one region. That is the property 17 exists to protect, and 'application profile
 * wrapping a system profile' is exactly the shape where an assumption could hold in the docs and not in
 * the response metadata."
 *
 * `models` is a COMPUTED attribute -- Bedrock returns it, we do not set it -- so this output is the
 * resource's own report of which regions it can route to, read back after apply. `make verify-inference`
 * asserts the three cross-region profiles each carry 3 regions and fails if any collapsed to 1.
 */

output "model_ids" {
  description = "Profile ARNs to invoke instead of raw model IDs. Feed to FNOL_*_MODEL_ID env vars."
  value       = { for k, v in aws_bedrock_inference_profile.this : k => v.arn }
}

output "region_sets" {
  description = "Regions each profile can route to, as reported by Bedrock. The constraint 17 check."
  value = {
    for k, v in aws_bedrock_inference_profile.this :
    k => sort([for m in v.models : split(":", m.model_arn)[3]])
  }
}

output "status" {
  description = "Profile status. Anything but ACTIVE means the profile is not usable."
  value       = { for k, v in aws_bedrock_inference_profile.this : k => v.status }
}
