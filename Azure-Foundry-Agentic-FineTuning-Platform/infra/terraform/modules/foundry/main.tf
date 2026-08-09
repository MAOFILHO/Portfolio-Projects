# Azure AI Foundry account (Cognitive Services kind "AIServices") + one
# Foundry project nested under it. S0 is the only SKU Azure AI Services
# offers today — it is a pay-per-token multi-service account, not an hourly
# tier, which is why it's $0 idle (see COSTS.md).
#
# Uses azurerm_cognitive_account (kind="AIServices") rather than the
# provider's azurerm_ai_services resource, which is deprecated/feature-frozen
# in favor of this one.

resource "azurerm_cognitive_account" "this" {
  name                  = var.name
  location              = var.location
  resource_group_name   = var.resource_group_name
  kind                  = "AIServices"
  sku_name              = var.sku_name
  custom_subdomain_name = var.name

  # project_management_enabled=true is required for an azurerm_ai_foundry_project
  # to be created under this account (i.e. this makes it a Foundry hub, not just
  # a plain Cognitive Services multi-service account).
  project_management_enabled = true

  # Required so the fine-tuning + deployment APIs used by both labs are
  # reachable from outside a private network in this demo setup.
  public_network_access_enabled = true

  # Local (API-key) auth stays available alongside Entra ID so DEMO_MODE=live
  # can run with either AZURE_FOUNDRY_API_KEY or `az login` credentials.
  local_auth_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_cognitive_account_project" "this" {
  name                 = var.project_name
  location             = var.location
  cognitive_account_id = azurerm_cognitive_account.this.id

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
