variable "name" {
  description = "Foundry (Cognitive Services AIServices) account name."
  type        = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "project_name" {
  description = "Foundry project name, nested under the account."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "sku_name" {
  description = "S0 is the only tier Azure AI Services (Foundry) offers — set explicitly rather than left to a provider default, per skill rule."
  type        = string
  default     = "S0"
}
