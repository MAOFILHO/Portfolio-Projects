// ============================================================
// Storage — Blob (frames + annotated events), Queue (alerts), Table (events)
// Adapted from Video-Agents-Foundry-Solution/infra/modules/storage.bicep:
// same StorageV2 / Hot / keyless (allowSharedKeyAccess=false) shape, extended
// with the extra container, queue, and table this system needs.
// ============================================================

@description('Name of the storage account')
param name string

@description('Azure region for the storage account')
param location string

@description('Resource tags')
param tags object = {}

@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
])
@description('Storage account SKU. Standard_LRS is cheapest and has the broadest region availability.')
param skuName string = 'Standard_LRS'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: skuName
  }
  properties: {
    accessTier: 'Hot'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource framesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'frames'
  properties: {
    publicAccess: 'None'
  }
}

resource clipsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'clips'
  properties: {
    publicAccess: 'None'
  }
}

resource eventsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'events'
  properties: {
    publicAccess: 'None'
  }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource alertsQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueService
  name: 'alerts'
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource eventsTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'events'
}

resource auditTable 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'audit'
}

@description('Storage account resource ID')
output id string = storageAccount.id

@description('Storage account name')
output name string = storageAccount.name

@description('Blob service primary endpoint')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('Queue service primary endpoint')
output queueEndpoint string = storageAccount.properties.primaryEndpoints.queue

@description('Table service primary endpoint')
output tableEndpoint string = storageAccount.properties.primaryEndpoints.table
