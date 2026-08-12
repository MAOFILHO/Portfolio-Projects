variable "project_name" {
  description = "Short project slug used to build resource names."
  type        = string
  default     = "foundry-travel"
}

variable "location" {
  description = "Azure region. Locked to eastus2 by user decision — matches every screenshot in both source lab guides and is where the gpt-5.4 family is Global Standard."
  type        = string
  default     = "eastus2"

  validation {
    condition     = var.location == "eastus2"
    error_message = "This project is scoped to eastus2 only (see PLAN.md — region decision)."
  }
}

variable "budget_ceiling_usd" {
  description = "Monthly consumption budget ceiling in USD. Alerts fire at 50/80/100%."
  type        = number
  default     = 25
}

variable "budget_contact_emails" {
  description = "Email addresses notified by the budget alert."
  type        = list(string)
  default     = []
}

variable "managed_by_tag" {
  description = "Tag applied to every resource so teardown/sweep can find all of them, at any auto-increment suffix."
  type        = string
  default     = "foundry-agentic-platform"
}

variable "base_model_deployments" {
  description = "Always-available catalog models deployed for Demo 1 / Demo 2 / Demo 3, all on GlobalStandard SKU with an explicit $0/hr rate (pay-per-token)."
  type = map(object({
    model_format  = string
    model_name    = string
    model_version = string
    sku_name      = string
    capacity      = number
  }))
  default = {
    gpt-4-1 = {
      model_format  = "OpenAI"
      model_name    = "gpt-4.1"
      model_version = "2025-04-14"
      sku_name      = "GlobalStandard"
      capacity      = 10
    }
    gpt-5-4 = {
      model_format  = "OpenAI"
      model_name    = "gpt-5.4"
      model_version = "2026-03-05"
      sku_name      = "GlobalStandard"
      capacity      = 10
    }
    gpt-5-4-mini = {
      model_format  = "OpenAI"
      model_name    = "gpt-5.4-mini"
      model_version = "2026-03-17"
      sku_name      = "GlobalStandard"
      capacity      = 10
    }
  }
}

variable "dockerhub_username" {
  description = "Docker Hub username hosting the public backend image (see README — chosen over Azure Container Registry to stay at $0/mo)."
  type        = string
}

variable "backend_image_tag" {
  description = "Tag of the backend image on Docker Hub the Container App should run."
  type        = string
  default     = "latest"
}

variable "github_oidc_client_id" {
  description = "Client ID of the GitHub Actions OIDC identity, managed separately in ../terraform-identity/ (its `client_id` output) — looked up here via a data source, never created or destroyed by this config. Same value as the FOUNDRY_AZURE_CLIENT_ID GitHub Actions variable. Defaulted to the current real value so `make provision` needs no extra flag; override if the identity is ever re-created."
  type        = string
  default     = "adf281a0-ad5f-4d77-b8f1-be5a6898238f"
}

variable "enable_next_suffix_probe" {
  description = "If true, calls the next_suffix.py external data source, which shells out to `az` to probe for name collisions before choosing a numeric suffix. If false (default for CI/mock validation), uses suffix 'v1' unconditionally so `terraform validate`/`plan` work with no Azure login."
  type        = bool
  default     = false
}
