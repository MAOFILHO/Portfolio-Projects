output "id" {
  value = azurerm_cognitive_account.this.id
}

output "endpoint" {
  value = azurerm_cognitive_account.this.endpoint
}

output "primary_key" {
  value     = azurerm_cognitive_account.this.primary_access_key
  sensitive = true
}

output "project_id" {
  value = azurerm_cognitive_account_project.this.id
}

output "project_name" {
  value = azurerm_cognitive_account_project.this.name
}
