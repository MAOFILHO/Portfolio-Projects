# Build order (mirrors PLAN.md / TASKS.md Phase 4 — order matters):
#   1. resource group
#   2. budget alert            <- created BEFORE any billable resource
#   3. Foundry account/project
#   4. model deployments (base catalog models, then the fine-tuned one
#      is created out-of-band by the finetune agent/API, not by Terraform,
#      since its name depends on a training job that hasn't run yet)
#   5. observability (Log Analytics + Application Insights)

locals {
  tags = {
    managed_by  = var.managed_by_tag
    project     = var.project_name
    environment = "demo"
  }
}

# --- 0. auto-increment suffix ------------------------------------------------
data "external" "suffix" {
  program = ["python3", "${path.module}/scripts/next_suffix.py"]

  query = {
    project_name   = var.project_name
    managed_by_tag = var.managed_by_tag
    enable_probe   = tostring(var.enable_next_suffix_probe)
    lock_path      = "${path.module}/.suffix.lock"
  }
}

locals {
  suffix      = data.external.suffix.result.suffix
  name_prefix = "${var.project_name}-${local.suffix}"
}

# --- 1. resource group --------------------------------------------------------
resource "azurerm_resource_group" "this" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.tags
}

# --- 2. budget alert (BEFORE anything billable) -------------------------------
module "budget" {
  source = "./modules/budget"

  budget_name       = "budget-${local.name_prefix}"
  resource_group_id = azurerm_resource_group.this.id
  amount_usd        = var.budget_ceiling_usd
  contact_emails    = var.budget_contact_emails
  start_date        = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())

  depends_on = [azurerm_resource_group.this]
}

# --- 3. Foundry account + project ---------------------------------------------
module "foundry" {
  source = "./modules/foundry"

  name                = "aif-${local.name_prefix}"
  project_name        = "proj-${local.name_prefix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags

  depends_on = [module.budget]
}

# --- 4. base catalog model deployments -----------------------------------------
module "base_deployments" {
  source   = "./modules/model_deployment"
  for_each = var.base_model_deployments

  ai_services_id  = module.foundry.id
  deployment_name = each.value.model_name
  model_format    = each.value.model_format
  model_name      = each.value.model_name
  model_version   = each.value.model_version
  sku_name        = each.value.sku_name
  sku_capacity    = each.value.capacity

  depends_on = [module.foundry]
}
