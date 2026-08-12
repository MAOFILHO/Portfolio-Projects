variable "ai_services_id" {
  description = "ID of the parent azurerm_ai_services (Foundry) account."
  type        = string
}

variable "deployment_name" {
  type = string
}

variable "model_format" {
  type    = string
  default = "OpenAI"
}

variable "model_name" {
  type = string
}

variable "model_version" {
  type = string
}

variable "sku_name" {
  description = "Set explicitly, never a provider default. GlobalStandard for base/catalog models, DeveloperTier for fine-tuned deployments — see COSTS.md for why."
  type        = string
}

variable "sku_capacity" {
  description = "Throughput units for GlobalStandard; ignored (must be 1) for DeveloperTier."
  type        = number
  default     = 10
}
