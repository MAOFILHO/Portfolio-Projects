# Public hosting for the app itself (not the AI infra, which is provisioned
# in main.tf) — a Container App running the FastAPI backend, a Static Web
# App serving the React frontend, and Microsoft Entra ID sign-in gating both.
#
# Prerequisite this file assumes already exists, created out-of-band via
# `az role definition create --role-definition @infra/foundry-deployer-role.json`
# (matches this monorepo's convention — see sibling
# Event-Driven-ML-Forecasting-Platform/cloud/infra/forecast-deployer-role.json,
# which is applied the same way, not Terraform-managed). This is a real
# chicken-and-egg: the role must exist before the `data` lookup below can
# resolve it, and the very first `terraform apply` here still needs to run
# with your own elevated local credentials (same as every apply so far in
# this project) — only *subsequent* deploys can use the narrower OIDC
# identity looked up below.

data "azurerm_client_config" "current" {}
data "azuread_client_config" "current" {}

data "azurerm_role_definition" "foundry_deployer" {
  name  = "Foundry Platform Deployer"
  scope = azurerm_resource_group.this.id
}

locals {
  container_app_name  = "ca-${local.name_prefix}-api"
  static_web_app_name = "swa-${local.name_prefix}"
  # Static App ID URI, not the more common api://<client_id> pattern (see
  # azuread_application.easy_auth's comment for why) — but a fully
  # arbitrary string isn't allowed either: this tenant's default policy
  # requires an identifier URI to contain a verified domain, the tenant ID,
  # or the app ID (confirmed live —
  # InvalidUniqueTenantIdentifierAsPerAppPolicy). The tenant ID is already
  # known before the application exists (it's a data source, not this
  # resource's own computed output), so it satisfies the policy without
  # reintroducing the self-reference problem client_id would.
  entra_audience = "api://${data.azuread_client_config.current.tenant_id}/${local.name_prefix}-signin"
}

# --- GitHub Actions OIDC identity (looked up, not managed here) ------------
# The app registration + service principal + federated credential live in
# ../terraform-identity/, a deliberately separate Terraform root/state — see
# that config's header comment for why. This config only looks the identity
# up (by client_id) and grants it access; it can never destroy it, even via
# a full `terraform destroy` (what `make teardown` runs).
data "azuread_service_principal" "github_oidc" {
  client_id = var.github_oidc_client_id
}

# Scoped to this project's resource group only, not the whole subscription —
# the role definition's AssignableScopes is subscription-wide (matches the
# sibling project's pattern), but the actual assignment here is narrowed.
# Re-created every provision/teardown cycle along with the resource group
# it's scoped to — that churn is fine, and expected: only the identity
# itself (../terraform-identity/) needs to survive teardown, not any
# particular grant of access.
resource "azurerm_role_assignment" "github_oidc_deployer" {
  scope              = azurerm_resource_group.this.id
  role_definition_id = data.azurerm_role_definition.foundry_deployer.id
  principal_id       = data.azuread_service_principal.github_oidc.object_id
}

# --- Container Apps Environment (reuses existing Log Analytics) ----------
resource "azurerm_container_app_environment" "this" {
  name                       = "cae-${local.name_prefix}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
  tags                       = local.tags
}

locals {
  container_app_fqdn = "https://${local.container_app_name}.${azurerm_container_app_environment.this.default_domain}"
}

# --- Static Web App (frontend) --------------------------------------------
resource "azurerm_static_web_app" "frontend" {
  name                = local.static_web_app_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

# --- Entra ID sign-in + resource-server app (MSAL.js) ----------------------
# One app registration plays both roles: `single_page_application` for the
# browser-side MSAL.js PKCE flow that acquires the token, and its exposed
# `api` scope is what the backend validates tokens against itself (see
# src/app/auth_entra.py) — NOT Container Apps' built-in Easy Auth, which is
# deliberately not used here: it authenticates the browser's CORS preflight
# (OPTIONS) request too, and a preflight structurally never carries
# credentials, so Easy Auth always 401s it — confirmed live and matches a
# known, unresolved Container Apps platform limitation
# (microsoft/azure-container-apps#359). No client secret needed — the SPA
# flow is PKCE-based (public client), and the backend validates tokens by
# fetching Microsoft's public signing keys, not by presenting a secret of
# its own. Single-tenant (AzureADMyOrg) is enough for a personal project.
resource "azuread_application" "easy_auth" {
  display_name     = "${local.name_prefix}-signin"
  sign_in_audience = "AzureADMyOrg"

  # A static App ID URI, not the more common `api://<client_id>` pattern —
  # deliberately, because that pattern needs a *separate*
  # azuread_application_identifier_uri resource (client_id isn't known until
  # after this resource is created, so it can't self-reference). In
  # practice that separate-resource split proved fragile: Microsoft Graph's
  # PATCH semantics reset identifierUris to empty whenever this application
  # resource was modified for any *other* reason afterward (reproduced
  # live, twice, independently — not a one-off flake). A static string set
  # directly in this same resource's own create/update payload every time
  # has no such drift window, since there's nothing separate to drift from.
  identifier_uris = [local.entra_audience]

  # Standard "SPA calling its own protected API" pattern (one app
  # registration playing both roles) — exposes a user-consentable scope
  # (type = "User", no tenant-admin consent required) so MSAL.js can
  # request an access token whose audience the backend validates against.
  api {
    # Explicit, not left at whatever the provider/API defaults to — a v1.0
    # access token has issuer https://sts.windows.net/{tenant}/, not the
    # https://login.microsoftonline.com/{tenant}/v2.0 issuer auth_entra.py
    # validates against. Reproduced live: the very first sign-in attempt
    # got "invalid token: Invalid issuer" before this was set explicitly.
    requested_access_token_version = 2

    oauth2_permission_scope {
      id                         = "8f9e6c1a-2f3d-4c8f-9c2e-4f6a1b0d7e21"
      admin_consent_description  = "Allow the app to call the Foundry Agentic FineTuning Platform API as the signed-in user."
      admin_consent_display_name = "Access API as user"
      user_consent_description   = "Allow the app to call the API on your behalf."
      user_consent_display_name  = "Access API"
      value                      = "access_as_user"
      type                       = "User"
    }
  }

  single_page_application {
    # Entra requires a trailing slash on a redirect URI with no path segment
    # — a bare origin like "https://host" is rejected, "https://host/" isn't.
    redirect_uris = [
      "https://${azurerm_static_web_app.frontend.default_host_name}/",
    ]
  }
}

resource "azuread_service_principal" "easy_auth" {
  client_id = azuread_application.easy_auth.client_id
}

# --- Container App (backend) ----------------------------------------------
resource "azurerm_container_app" "backend" {
  name                         = local.container_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  tags                         = local.tags

  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "backend"
      image  = "docker.io/${var.dockerhub_username}/azure-microsoftfoundry-agentic-finetuning-platform-backend:${var.backend_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      # DEMO_MODE defaults to mock — a public instance should never default
      # to live billing. Flip to "live" via `az containerapp update` only
      # when intentionally demoing against real Azure, watching the budget.
      env {
        name  = "DEMO_MODE"
        value = "mock"
      }
      env {
        name  = "AZURE_FOUNDRY_ENDPOINT"
        value = module.foundry.endpoint
      }
      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = data.azurerm_client_config.current.subscription_id
      }
      env {
        name  = "AZURE_RESOURCE_GROUP"
        value = azurerm_resource_group.this.name
      }
      env {
        name  = "AZURE_LOCATION"
        value = var.location
      }
      env {
        name  = "CORS_ORIGINS"
        value = "https://${azurerm_static_web_app.frontend.default_host_name}"
      }
      # Deliberately no AZURE_FOUNDRY_API_KEY — the whole point of granting
      # this Container App's Managed Identity a role on the Foundry account
      # below is that azure_foundry.py's existing DefaultAzureCredential
      # fallback picks up ManagedIdentityCredential automatically with zero
      # code changes.
      #
      # These activate src/app/auth_entra.py's bearer-token check on every
      # route except /health — blank in local/mock dev, where the check is
      # a no-op (see that module's docstring for why this exists instead of
      # Container Apps' built-in Easy Auth).
      env {
        name  = "ENTRA_TENANT_ID"
        value = data.azuread_client_config.current.tenant_id
      }
      env {
        name  = "ENTRA_CLIENT_ID"
        value = azuread_application.easy_auth.client_id
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  depends_on = [module.foundry]
}

# The Container App's own identity needs access to the Foundry account it
# calls — this is what makes the DefaultAzureCredential Managed Identity
# path (see azure_foundry.py) actually work once deployed.
resource "azurerm_role_assignment" "container_app_foundry_access" {
  scope                = module.foundry.id
  role_definition_name = "Cognitive Services OpenAI Contributor"
  principal_id         = azurerm_container_app.backend.identity[0].principal_id
}
