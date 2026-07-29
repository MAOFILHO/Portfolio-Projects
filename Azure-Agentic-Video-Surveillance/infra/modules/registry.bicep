// ============================================================
// Azure Container Registry — Basic SKU (cheapest tier, ~$0.17/day).
// Used for `az acr build` cloud builds of the backend image, avoiding local
// Docker cross-compilation issues on Apple Silicon (see docs/troubleshooting.md).
// ============================================================

@description('Name for the Container Registry (must be globally unique, alphanumeric only)')
param name string

@description('Azure region')
param location string

@description('Resource tags')
param tags object = {}

@description('Principal ID of the managed identity that pulls images (granted AcrPull)')
param pullPrincipalId string

var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, pullPrincipalId, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: pullPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('Registry resource ID')
output id string = registry.id

@description('Registry name')
output name string = registry.name

@description('Registry login server, e.g. myregistry.azurecr.io')
output loginServer string = registry.properties.loginServer
