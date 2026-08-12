output "suffix" {
  description = "The auto-increment suffix chosen for this apply (e.g. v1)."
  value       = local.suffix
}

output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "foundry_endpoint" {
  value = module.foundry.endpoint
}

output "foundry_account_id" {
  value = module.foundry.id
}

output "project_name" {
  value = module.foundry.project_name
}

output "foundry_primary_key" {
  value     = module.foundry.primary_key
  sensitive = true
}

output "base_model_deployment_names" {
  value = { for k, v in module.base_deployments : k => v.name }
}

output "app_insights_connection_string" {
  value     = azurerm_application_insights.this.connection_string
  sensitive = true
}

output "budget_id" {
  value = module.budget.budget_id
}

# --- Hosting (see hosting.tf) ------------------------------------------------
output "container_app_fqdn" {
  description = "Public backend URL — use as VITE_API_BASE_URL when building the frontend."
  value       = local.container_app_fqdn
}

output "static_web_app_default_host_name" {
  description = "Public frontend hostname."
  value       = azurerm_static_web_app.frontend.default_host_name
}

output "static_web_app_deployment_token" {
  description = "Pass to `swa deploy --deployment-token`."
  value       = azurerm_static_web_app.frontend.api_key
  sensitive   = true
}

output "entra_signin_client_id" {
  description = "Use as VITE_ENTRA_CLIENT_ID when building the frontend."
  value       = azuread_application.easy_auth.client_id
}

output "entra_api_scope" {
  description = "Use as VITE_ENTRA_API_SCOPE when building the frontend — the scope MSAL requests to get a token the backend's own auth_entra.py validates."
  value       = "${local.entra_audience}/access_as_user"
}

output "entra_tenant_id" {
  value = data.azuread_client_config.current.tenant_id
}

output "github_oidc_client_id" {
  description = "Passthrough of the input variable of the same name (the identity itself is managed in ../terraform-identity/, not here) — kept as an output for convenience, so scripts that read Terraform outputs don't need to know which config actually owns it."
  value       = var.github_oidc_client_id
}
