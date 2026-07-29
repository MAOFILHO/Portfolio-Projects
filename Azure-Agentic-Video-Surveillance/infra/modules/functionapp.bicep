// ============================================================
// Azure Function (Python, Consumption plan) — the async frame-analysis worker.
//
// Blob trigger source is Event Grid (source: "EventGrid" in function_app.py's
// @app.blob_trigger), not the classic polling-based LogsAndContainerScan.
// The classic source is documented by Microsoft as taking "up to 10 minutes"
// to discover a new blob in the worst case, and in practice was observed
// exceeding even a 600s wait repeatedly once this pipeline started running
// under real CI/CD (every CI deploy redeploys fresh Function code, so the
// polling mechanism cold-starts every single run -- see docs/troubleshooting.md
// #10). An earlier version of this comment avoided Event Grid specifically
// because a webhook-subscription destination requires the function's own
// extension endpoint to already be live -- a circular dependency for a
// Bicep-first pipeline where infra deploys before function code does. The
// `AzureFunction` destination type doesn't need a webhook, but confirmed the
// hard way that it still validates the function resource actually exists
// ("Destination endpoint not found ... Resource should pre-exist") -- so the
// event *subscription* (unlike the System Topic below, which doesn't
// reference the function) is created in s07_deploy_function.py, after the
// function code is published, not here.
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

@description('Azure OpenAI endpoint, backing the Semantic Kernel agents')
param openAiEndpoint string = ''

@description('Azure OpenAI chat model deployment name')
param openAiChatDeploymentName string = 'chat'

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

@description('Langfuse public key (empty disables Langfuse agent tracing)')
@secure()
param langfusePublicKey string = ''

@description('Langfuse secret key')
@secure()
param langfuseSecretKey string = ''

@description('Langfuse host (cloud or self-hosted)')
param langfuseHost string = 'https://cloud.langfuse.com'

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
        { name: 'OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'OPENAI_CHAT_DEPLOYMENT', value: openAiChatDeploymentName }
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
      ] : [], !empty(langfusePublicKey) ? [
        { name: 'LANGFUSE_PUBLIC_KEY', value: langfusePublicKey }
        { name: 'LANGFUSE_SECRET_KEY', value: langfuseSecretKey }
        { name: 'LANGFUSE_HOST', value: langfuseHost }
      ] : [])
    }
  }
}

resource storageAccountRef 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// The System Topic itself doesn't reference the Function App, so it's safe
// to create here at infra-deploy time. The event *subscription* -- which
// does reference the Function by resource ID -- can NOT also live here: the
// AzureFunction destination type validates that
// `<functionAppId>/functions/AnalyzeFrame` already exists, and this Function
// App's code hasn't been published yet at this point in the pipeline
// (s07_deploy_function runs after s03_deploy_infra). That subscription is
// created imperatively in s07_deploy_function.py instead, right after the
// function code is actually deployed.
resource blobEventsTopic 'Microsoft.EventGrid/systemTopics@2023-12-15-preview' = {
  name: '${storageAccountName}-blob-events'
  location: location
  tags: tags
  properties: {
    source: storageAccountRef.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

@description('Function App resource ID')
output id string = functionApp.id

@description('Function App name')
output name string = functionApp.name

@description('Function App default hostname')
output defaultHostname string = functionApp.properties.defaultHostName
