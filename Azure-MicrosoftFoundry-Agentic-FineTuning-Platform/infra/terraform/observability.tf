# Observability wired at the infra layer too (mirrors src/app/telemetry.py):
# PerGB2018 Log Analytics (5 GB/mo free, 30-day retention) backing an
# Application Insights resource. Both are consumption-based, no hourly SKU.

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.name_prefix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.tags
}

resource "azurerm_application_insights" "this" {
  name                = "appi-${local.name_prefix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"

  tags = local.tags
}
