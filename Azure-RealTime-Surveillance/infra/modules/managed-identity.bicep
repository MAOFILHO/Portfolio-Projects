// ============================================================
// Managed Identity — one user-assigned identity shared by the Container App
// and the Function App, granted keyless (RBAC-only) access to Storage
// (Blob/Queue/Table) and Cognitive Services (Vision).
//
// Adapted from Video-Agents-Foundry-Solution/infra/modules/managed-identity.bicep:
// same identity + role-assignment pattern, extended with Queue/Table Data
// Contributor and Cognitive Services User roles.
// ============================================================

@description('Name of the user-assigned managed identity')
param name string

@description('Azure region for the managed identity')
param location string

@description('Resource tags')
param tags object = {}

@description('Resource ID of the storage account to grant access to')
param storageAccountId string

@description('Resource ID of the Cognitive Services (Vision) account to grant access to')
param visionAccountId string

@description('Resource ID of the Log Analytics workspace to grant read access to (backend Observability page queries traces/exceptions from here)')
param logAnalyticsWorkspaceId string

// Built-in role definition IDs.
//
// Storage Blob Data OWNER (not Contributor) here: the Function App's
// AzureWebJobsStorage is wired as an identity-based connection
// (functionapp.bicep), and Microsoft's docs for that specific connection
// mode require Blob Data *Owner* -- the runtime's own internal host-lease
// container (azure-webjobs-hosts) needs permissions Contributor doesn't
// grant. Confirmed the hard way: Contributor produced a real
// AuthorizationPermissionMismatch host crash-loop in Application Insights
// (host restarted repeatedly, ConsecutiveErrors climbing, blob trigger never
// fired) even though our own "frames"/"events" containers worked fine under
// Contributor alone.
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageQueueDataContributorRoleId = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var storageTableDataContributorRoleId = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var logAnalyticsReaderRoleId = '73c42c96-874c-492b-b04d-ab87d138a893'

// Storage Account CONTRIBUTOR (control-plane, not a data-plane role) here:
// functionapp.bicep's native (poll-based, non-Event-Grid) blob trigger uses
// the WebJobs SDK's BlobLogListener, which calls
// BlobServiceClient.GetProperties/SetProperties to enable Storage Analytics
// Logging on the account -- that's a blobServices/read|write control-plane
// action, which none of the Blob Data roles above grant (they only cover
// data-plane blob/container operations). Confirmed via Application Insights:
// host stuck in a crash-loop with a 403 AuthorizationPermissionMismatch
// thrown from Azure.Storage.Blobs.BlobServiceClient.GetPropertiesAsync,
// inside Microsoft.Azure.WebJobs.Extensions.Storage.Blobs.Listeners
// .BlobLogListener.EnableLoggingAsync -- even with Storage Blob Data Owner
// already granted.
var storageAccountContributorRoleId = '17d1049b-9a84-46fb-8f53-869881c3d3ab'

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: last(split(storageAccountId, '/'))
}

resource visionAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: last(split(visionAccountId, '/'))
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource storageBlobDataOwnerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, managedIdentity.id, storageBlobDataOwnerRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageQueueDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, managedIdentity.id, storageQueueDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageQueueDataContributorRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageTableDataContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, managedIdentity.id, storageTableDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageTableDataContributorRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAccountContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, managedIdentity.id, storageAccountContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageAccountContributorRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource cognitiveServicesUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(visionAccountId, managedIdentity.id, cognitiveServicesUserRoleId)
  scope: visionAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource logAnalyticsReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalyticsWorkspaceId, managedIdentity.id, logAnalyticsReaderRoleId)
  scope: logAnalyticsWorkspace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', logAnalyticsReaderRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('Managed identity resource ID')
output id string = managedIdentity.id

@description('Managed identity principal ID')
output principalId string = managedIdentity.properties.principalId

@description('Managed identity client ID')
output clientId string = managedIdentity.properties.clientId

@description('Managed identity name')
output name string = managedIdentity.name
