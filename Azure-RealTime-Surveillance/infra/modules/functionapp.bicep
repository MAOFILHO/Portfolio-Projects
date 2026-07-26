// ============================================================
// Azure Function (Python, Consumption plan) — the async frame-analysis worker.
//
// Uses a native Blob-trigger binding (`path: frames/{name}`) rather than an
// Event Grid subscription: Event Grid requires a webhook handshake against the
// function's own extension endpoint, which only exists *after* the function
// code is deployed — that's a circular dependency for a pure-Bicep-first
// pipeline. The native blob trigger needs no extra resource and typically
// fires within seconds on Consumption; see docs/architecture.md for the
// tradeoff (a few minutes of worst-case latency vs. Event Grid).
//
// AzureWebJobsStorage is wired via an identity-based connection (no storage
// keys) using the shared user-assigned managed identity.
// ============================================================

@description('Name for the Function App (must be globally unique)')
param functionAppName string

@description('Name for the (Consumption) hosting plan')
param hostingPlanName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object = {}

@description('Resource ID of the user-assigned managed identity to attach')
param managedIdentityId string

@description('Client ID of the user-assigned managed identity')
param managedIdentityClientId string

@description('Storage account name backing AzureWebJobsStorage and the blob trigger')
param storageAccountName string

@description('Vision account endpoint')
param visionEndpoint string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Alert rule: comma-separated tags to watch')
param alertWatchTags string

@description('Alert rule: minimum detection confidence (0-1)')
param alertMinConfidence string

@description('Alert rule: minimum matching detections to trigger')
param alertMinCount string

@description('Detection backend: azure_vision (default) or ssd_mobilenet')
param analyzerBackend string = 'azure_vision'

@description('Alert rule: number of person detections in one frame that triggers a "crowd" alert (0 disables)')
param alertCrowdThreshold string = '0'

@description('Alert rule: restricted zone as "x0,y0,x1,y1" normalized 0.0-1.0 coordinates for the trespassing rule (empty disables)')
param alertRestrictedZone string = ''

@description('Alert rule: optional override of the tag->severity map, "tag:severity,tag:severity" (empty uses the built-in default)')
param alertSeverityMap string = ''

@description('ACS connection string secret value (empty string disables email/SMS alerting)')
@secure()
param acsConnectionString string = ''

@description('ACS sender email address')
param acsSenderEmail string = ''

@description('Alert recipient email address')
param alertEmailTo string = ''

@description('Alert recipient SMS number (E.164 format)')
param alertSmsTo string = ''

@description('ACS SMS "from" number (E.164 format, leave empty if SMS not provisioned)')
param acsSmsFrom string = ''

resource hostingPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: hostingPlanName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    serverFarmId: hostingPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      appSettings: concat([
        { name: 'AzureWebJobsStorage__accountName', value: storageAccountName }
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__clientId', value: managedIdentityClientId }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AZURE_CLIENT_ID', value: managedIdentityClientId }
        { name: 'STORAGE_ACCOUNT_NAME', value: storageAccountName }
        { name: 'VISION_ENDPOINT', value: visionEndpoint }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'ALERT_WATCH_TAGS', value: alertWatchTags }
        { name: 'ALERT_MIN_CONFIDENCE', value: alertMinConfidence }
        { name: 'ALERT_MIN_COUNT', value: alertMinCount }
        { name: 'ANALYZER_BACKEND', value: analyzerBackend }
        { name: 'ALERT_CROWD_THRESHOLD', value: alertCrowdThreshold }
        { name: 'ALERT_RESTRICTED_ZONE', value: alertRestrictedZone }
        { name: 'ALERT_SEVERITY_MAP', value: alertSeverityMap }
        { name: 'ACS_SENDER_EMAIL', value: acsSenderEmail }
        { name: 'ALERT_EMAIL_TO', value: alertEmailTo }
        { name: 'ALERT_SMS_TO', value: alertSmsTo }
        { name: 'ACS_SMS_FROM', value: acsSmsFrom }
      ], !empty(acsConnectionString) ? [
        { name: 'ACS_CONNECTION_STRING', value: acsConnectionString }
      ] : [])
    }
  }
}

@description('Function App resource ID')
output id string = functionApp.id

@description('Function App name')
output name string = functionApp.name

@description('Function App default hostname')
output defaultHostname string = functionApp.properties.defaultHostName
