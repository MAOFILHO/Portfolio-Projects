// ============================================================
// Azure Real-Time Surveillance — main deployment template
// Subscription-scoped: creates its own resource group, then fans out to
// small single-purpose modules. Pattern adapted from
// Video-Agents-Foundry-Solution/infra/main.bicep, stripped of AKS/GPU/Arc/
// Video-Indexer/AI-Foundry resources and replaced with a minimal, cost-aware
// serverless surveillance stack.
// ============================================================

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment used to generate a short unique hash for resource names')
param environmentName string

@minLength(1)
@description('Primary Azure region for all resources (must support Image Analysis 4.0 and Container Apps, e.g. eastus2, eastus)')
param location string

@description('Name of the resource group. Defaults to "<environmentName>-rg" if empty.')
param resourceGroupName string = ''

@allowed(['F0', 'S1'])
@description('Azure AI Vision SKU. F0 is free (1 per subscription, 20 calls/min); S1 is pay-per-call with no rate cap.')
param visionSkuName string = 'S1'

@allowed(['Standard_LRS', 'Standard_ZRS', 'Standard_GRS'])
@description('Storage account SKU. Standard_LRS is cheapest and has the broadest region availability.')
param storageSkuName string = 'Standard_LRS'

@description('Comma-separated detection tags that trigger an alert')
param alertWatchTags string = 'person'

@description('Minimum detection confidence (0-1) to count toward an alert')
param alertMinConfidence string = '0.6'

@description('Minimum number of matching detections required to trigger an alert')
param alertMinCount string = '1'

@description('Detection backend the Function uses: azure_vision (default) or ssd_mobilenet (self-hosted, no Azure cost)')
param analyzerBackend string = 'azure_vision'

@description('Alert rule: number of person detections in one frame that triggers a "crowd" alert (0 disables)')
param alertCrowdThreshold string = '0'

@description('Alert rule: restricted zone as "x0,y0,x1,y1" normalized 0.0-1.0 image-fraction coordinates for the trespassing rule (empty disables)')
param alertRestrictedZone string = ''

@description('Alert rule: optional override of the tag->severity map, "tag:severity,tag:severity" (empty uses the built-in Critical/High/Medium/Low default)')
param alertSeverityMap string = ''

@description('Azure region for the Vision resource specifically -- must support Image Analysis 4.0 Captions (e.g. eastus). Independent of `location` since ARM cannot move an existing resource between regions in-place.')
param visionLocation string = 'eastus'

@description('ACS sender email address (leave empty until the Bicep-provisioned Azure-managed domain address is known; wired post-deploy by the CLI)')
param acsSenderEmail string = ''

@description('Alert recipient email address')
param alertEmailTo string = ''

@description('Alert recipient SMS number (E.164 format, e.g. +15551234567)')
param alertSmsTo string = ''

@description('ACS SMS "from" number (E.164 format). Leave empty if you have not provisioned an ACS phone number.')
param acsSmsFrom string = ''

@description('Deploy the always-on Nest doorbell ingestor Container App (opt-in; adds a fixed 24/7 compute cost -- see docs/cost.md)')
param nestIngestorEnabled bool = false

@description('Google OAuth client ID (Nest/SDM API)')
param googleClientId string = ''

@description('Google OAuth client secret (Nest/SDM API)')
@secure()
param googleClientSecret string = ''

@description('Google OAuth long-lived refresh token (Nest/SDM API)')
@secure()
param googleRefreshToken string = ''

@description('Google Device Access project ID (console.nest.google.com/device-access)')
param googleDeviceAccessProjectId string = ''

@description('Comma-separated "device_id:camera_id" pairs for every Nest camera to watch')
param googleDevices string = ''

@description('GCP project ID hosting the Pub/Sub topic/subscription for Nest camera events')
param gcpPubsubProjectId string = ''

@description('GCP Pub/Sub subscription ID the ingestor reads from')
param gcpPubsubSubscriptionId string = 'nest-surveillance-sub'

@description('Full JSON content of a GCP service-account key with roles/pubsub.subscriber on the subscription above')
@secure()
param gcpServiceAccountKeyJson string = ''

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var rgName = !empty(resourceGroupName) ? resourceGroupName : '${environmentName}-rg'
var tags = {
  'azd-env-name': environmentName
  project: 'azure-realtime-surveillance'
}
// Generated once, deterministically, rather than passed in from outside --
// same precedent as communication.bicep's ACS connection string (listKeys()).
// Shared between the backend (checks it) and the Nest ingestor (sends it).
var frameUploadApiKey = guid(subscription().id, environmentName, location, 'frame-upload-api-key')

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
  tags: tags
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    name: 'st${resourceToken}'
    location: location
    tags: tags
    skuName: storageSkuName
  }
}

module vision 'modules/vision.bicep' = {
  name: 'vision'
  scope: rg
  params: {
    name: 'vis-${resourceToken}'
    location: visionLocation
    tags: tags
    skuName: visionSkuName
  }
}

module managedIdentity 'modules/managed-identity.bicep' = {
  name: 'managed-identity'
  scope: rg
  params: {
    name: 'id-${resourceToken}'
    location: location
    tags: tags
    storageAccountId: storage.outputs.id
    visionAccountId: vision.outputs.id
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsId
  }
}

module registry 'modules/registry.bicep' = {
  name: 'registry'
  scope: rg
  params: {
    name: 'acr${resourceToken}'
    location: location
    tags: tags
    pullPrincipalId: managedIdentity.outputs.principalId
  }
}

module observability 'modules/observability.bicep' = {
  name: 'observability'
  scope: rg
  params: {
    logAnalyticsName: 'log-${resourceToken}'
    appInsightsName: 'appi-${resourceToken}'
    location: location
    tags: tags
  }
}

module communication 'modules/communication.bicep' = {
  name: 'communication'
  scope: rg
  params: {
    emailServiceName: 'acs-email-${resourceToken}'
    communicationServiceName: 'acs-${resourceToken}'
  }
}

module containerApp 'modules/containerapp.bicep' = {
  name: 'container-app'
  scope: rg
  params: {
    environmentName: 'cae-${resourceToken}'
    appName: 'ca-${resourceToken}'
    location: location
    tags: tags
    logAnalyticsId: observability.outputs.logAnalyticsId
    logAnalyticsWorkspaceGuid: observability.outputs.logAnalyticsWorkspaceGuid
    appInsightsConnectionString: observability.outputs.connectionString
    managedIdentityId: managedIdentity.outputs.id
    managedIdentityClientId: managedIdentity.outputs.clientId
    registryLoginServer: registry.outputs.loginServer
    storageBlobEndpoint: storage.outputs.blobEndpoint
    visionEndpoint: vision.outputs.endpoint
    alertWatchTags: alertWatchTags
    alertMinConfidence: alertMinConfidence
    alertMinCount: alertMinCount
    analyzerBackend: analyzerBackend
    alertCrowdThreshold: alertCrowdThreshold
    alertRestrictedZone: alertRestrictedZone
    alertSeverityMap: alertSeverityMap
    acsConnectionString: communication.outputs.connectionString
    acsSenderEmail: !empty(acsSenderEmail) ? acsSenderEmail : communication.outputs.senderEmail
    alertEmailTo: alertEmailTo
    alertSmsTo: alertSmsTo
    acsSmsFrom: acsSmsFrom
    frameUploadApiKey: frameUploadApiKey
  }
}

module nestIngestor 'modules/nest-ingestor.bicep' = if (nestIngestorEnabled) {
  name: 'nest-ingestor'
  scope: rg
  params: {
    appName: 'ca-nest-${resourceToken}'
    location: location
    tags: tags
    environmentId: containerApp.outputs.environmentId
    managedIdentityId: managedIdentity.outputs.id
    registryLoginServer: registry.outputs.loginServer
    backendApiKey: frameUploadApiKey
    backendUrl: 'https://${containerApp.outputs.fqdn}'
    gcpServiceAccountKeyJson: gcpServiceAccountKeyJson
    googleClientId: googleClientId
    googleClientSecret: googleClientSecret
    googleRefreshToken: googleRefreshToken
    googleDeviceAccessProjectId: googleDeviceAccessProjectId
    googleDevices: googleDevices
    gcpPubsubProjectId: gcpPubsubProjectId
    gcpPubsubSubscriptionId: gcpPubsubSubscriptionId
  }
}

module functionApp 'modules/functionapp.bicep' = {
  name: 'function-app'
  scope: rg
  params: {
    functionAppName: 'func-${resourceToken}'
    hostingPlanName: 'plan-${resourceToken}'
    location: location
    tags: tags
    managedIdentityId: managedIdentity.outputs.id
    managedIdentityClientId: managedIdentity.outputs.clientId
    storageAccountName: storage.outputs.name
    visionEndpoint: vision.outputs.endpoint
    appInsightsConnectionString: observability.outputs.connectionString
    alertWatchTags: alertWatchTags
    alertMinConfidence: alertMinConfidence
    alertMinCount: alertMinCount
    analyzerBackend: analyzerBackend
    alertCrowdThreshold: alertCrowdThreshold
    alertRestrictedZone: alertRestrictedZone
    alertSeverityMap: alertSeverityMap
    acsConnectionString: communication.outputs.connectionString
    acsSenderEmail: !empty(acsSenderEmail) ? acsSenderEmail : communication.outputs.senderEmail
    alertEmailTo: alertEmailTo
    alertSmsTo: alertSmsTo
    acsSmsFrom: acsSmsFrom
  }
}

module staticWebApp 'modules/staticwebapp.bicep' = {
  name: 'static-web-app'
  scope: rg
  params: {
    name: 'swa-${resourceToken}'
    location: location
    tags: tags
  }
}

// ============================================================
// Outputs — consumed by src/surveil_deploy/steps/s04_resolve_names.py
// ============================================================
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_LOCATION string = location
output STORAGE_ACCOUNT_NAME string = storage.outputs.name
output STORAGE_BLOB_ENDPOINT string = storage.outputs.blobEndpoint
output VISION_ACCOUNT_NAME string = vision.outputs.name
output VISION_ENDPOINT string = vision.outputs.endpoint
output MANAGED_IDENTITY_ID string = managedIdentity.outputs.id
output MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.outputs.clientId
output CONTAINER_REGISTRY_NAME string = registry.outputs.name
output CONTAINER_REGISTRY_LOGIN_SERVER string = registry.outputs.loginServer
output CONTAINER_APP_NAME string = containerApp.outputs.name
output CONTAINER_APP_FQDN string = containerApp.outputs.fqdn
output FUNCTION_APP_NAME string = functionApp.outputs.name
output STATIC_WEB_APP_NAME string = staticWebApp.outputs.name
output STATIC_WEB_APP_DEFAULT_HOSTNAME string = staticWebApp.outputs.defaultHostname
output APPINSIGHTS_CONNECTION_STRING string = observability.outputs.connectionString
output APPINSIGHTS_NAME string = observability.outputs.appInsightsName
output ACS_SENDER_EMAIL string = communication.outputs.senderEmail
output NEST_INGESTOR_ENABLED string = string(nestIngestorEnabled)
output NEST_INGESTOR_CONTAINER_APP_NAME string = nestIngestor.?outputs.name ?? ''
