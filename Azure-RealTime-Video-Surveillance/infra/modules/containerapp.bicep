// ============================================================
// Container Apps Environment + the FastAPI backend Container App.
// Consumption plan, scale-to-zero (minReplicas=0) so idle cost is ~$0;
// smallest workload profile (0.25 vCPU / 0.5Gi).
//
// The image is set to a placeholder `mcr.microsoft.com/k8se/quickstart:latest`
// on first deploy (this resource cannot reference an image that doesn't exist
// yet); the deploy pipeline's s05_build_backend step builds the real image via
// ACR and updates the Container App with `az containerapp update --image`.
// ============================================================

@description('Name for the Container Apps managed environment')
param environmentName string

@description('Name for the Container App')
param appName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object = {}

@description('Log Analytics workspace resource ID (for the managed environment)')
param logAnalyticsId string

@description('Log Analytics workspace GUID (customerId) -- for the backend Observability page to query traces/exceptions via the Logs Query SDK')
param logAnalyticsWorkspaceGuid string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Resource ID of the user-assigned managed identity to attach')
param managedIdentityId string

@description('Client ID of the user-assigned managed identity (for DefaultAzureCredential)')
param managedIdentityClientId string

@description('Container registry login server')
param registryLoginServer string

@description('Storage account blob endpoint')
param storageBlobEndpoint string

@description('Vision account endpoint')
param visionEndpoint string

@description('Alert rule: comma-separated tags to watch')
param alertWatchTags string

@description('Alert rule: minimum detection confidence (0-1)')
param alertMinConfidence string

@description('Alert rule: minimum matching detections to trigger')
param alertMinCount string

@description('Detection backend the Function uses -- display-only here, the backend itself does not run detection')
param analyzerBackend string = 'azure_vision'

@description('Alert rule: number of person detections in one frame that triggers a "crowd" alert (0 disables) -- display-only here')
param alertCrowdThreshold string = '0'

@description('Alert rule: restricted zone as "x0,y0,x1,y1" normalized coordinates -- display-only here')
param alertRestrictedZone string = ''

@description('Alert rule: optional tag->severity map override -- display-only here')
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

@description('Shared secret required on POST /api/v1/frames via the X-Api-Key header (empty disables the check)')
@secure()
param frameUploadApiKey string = ''

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsId, '/'))
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registryLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: concat([
        {
          name: 'frame-upload-api-key'
          value: frameUploadApiKey
        }
      ], !empty(acsConnectionString) ? [
        {
          name: 'acs-connection-string'
          value: acsConnectionString
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: 'mcr.microsoft.com/k8se/quickstart:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat([
            { name: 'AZURE_CLIENT_ID', value: managedIdentityClientId }
            { name: 'STORAGE_BLOB_ENDPOINT', value: storageBlobEndpoint }
            { name: 'VISION_ENDPOINT', value: visionEndpoint }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'LOG_ANALYTICS_WORKSPACE_ID', value: logAnalyticsWorkspaceGuid }
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
            { name: 'FRAME_UPLOAD_API_KEY', secretRef: 'frame-upload-api-key' }
          ], !empty(acsConnectionString) ? [
            { name: 'ACS_CONNECTION_STRING', secretRef: 'acs-connection-string' }
          ] : [])
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'http-scale'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

@description('Container App resource ID')
output id string = containerApp.id

@description('Container App name')
output name string = containerApp.name

@description('Container App default (public) FQDN')
output fqdn string = containerApp.properties.configuration.ingress.fqdn

@description('Container Apps managed environment ID')
output environmentId string = managedEnvironment.id
