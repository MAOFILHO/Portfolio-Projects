# GitHub Actions OIDC identity for this project — a Microsoft Entra ID app
# registration + service principal + federated identity credential that lets
# GitHub Actions authenticate to Azure with no stored secret (azure/login's
# OIDC flow).
#
# Deliberately a SEPARATE Terraform root/state from ../terraform/, not a
# child module of it. ../terraform/hosting.tf used to manage these same
# three resources directly, in the same state as the AI infra + public
# hosting stack — which meant a plain `terraform destroy` there (what `make
# teardown` runs) destroyed this identity too. That's exactly what happened
# on 2026-08-10/11: the nightly teardown safety-net workflow's own
# `azure/login` step started failing with AADSTS700016 ("application ...
# was not found") because a prior local teardown had deleted the very app
# registration future teardown runs needed to authenticate as. This split
# makes that structurally impossible going forward: nothing in ../terraform/
# can reach into this state, so tearing down the AI infra/hosting stack any
# number of times never touches the identity that authenticates the
# workflows doing the tearing down.
#
# ../terraform/hosting.tf looks this identity up by client_id (a plain
# variable, not a Terraform reference — see its `github_oidc_client_id`
# variable) and grants it a role assignment scoped to whatever resource
# group currently exists. That role assignment DOES get destroyed/recreated
# every teardown/provision cycle — correctly: only the identity itself needs
# to survive, not any particular grant of access.
#
# Apply once, rarely touched again: `terraform init && terraform apply` from
# this directory with your own elevated local credentials (same bootstrap
# pattern as ../terraform/hosting.tf's custom role — see
# ../foundry-deployer-role.json's header comment). If this ever needs to be
# re-created (e.g. lost state), copy the new `client_id` output into the
# FOUNDRY_AZURE_CLIENT_ID GitHub Actions variable.

terraform {
  required_version = ">= 1.9"

  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }

  # Local backend, same as ../terraform/ — see that config's versions.tf for
  # the note on swapping in a remote backend. Deliberately its OWN state
  # file, in its own directory: that separation is the entire point of this
  # module existing.
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "azuread" {}

variable "display_name" {
  description = "Display name for the app registration. Deliberately NOT suffix-versioned like the AI infra (see ../terraform/main.tf's next_suffix.py) — this identity is meant to outlive any number of provision/teardown cycles, so it keeps the name it was first created with rather than churning on every suffix bump."
  type        = string
  default     = "foundry-travel-v1-github-oidc"
}

variable "github_repo" {
  description = "owner/repo of the monorepo this project lives in, for the OIDC federated credential's subject claim."
  type        = string
  default     = "MAOFILHO/Portfolio-Projects"
}

resource "azuread_application" "github_oidc" {
  display_name = var.display_name
}

resource "azuread_service_principal" "github_oidc" {
  client_id = azuread_application.github_oidc.client_id
}

resource "azuread_application_federated_identity_credential" "github_actions" {
  application_id = azuread_application.github_oidc.id
  display_name   = "github-actions-main"
  description    = "GitHub Actions workflow_dispatch runs on main authenticate as this app via OIDC — no stored client secret."
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repo}:ref:refs/heads/main"
}

output "client_id" {
  description = "Set as the FOUNDRY_AZURE_CLIENT_ID GitHub Actions variable, and as ../terraform/'s github_oidc_client_id variable."
  value       = azuread_application.github_oidc.client_id
}

output "service_principal_object_id" {
  description = "Not consumed directly anywhere — ../terraform/hosting.tf re-derives this itself via a data source keyed on client_id, so the two configs never need to be applied in a particular order."
  value       = azuread_service_principal.github_oidc.object_id
}
