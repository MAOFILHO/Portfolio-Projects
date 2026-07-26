// ============================================================
// Nest doorbell ingestor — a second Container App in the SAME managed
// environment as the backend (no second environment created here).
//
// Fundamentally different scaling shape from the backend: this holds a
// persistent Google Cloud Pub/Sub streaming-pull connection with no inbound
// HTTP traffic at all, so it has NO `ingress` block and is fixed at
// minReplicas=1/maxReplicas=1 -- it must never scale to zero (would drop the
// live subscription) and must never scale beyond 1 (would create a competing
// consumer double-processing the same Nest camera events).
//
// The GCP service-account key is mounted as a file (Secret-type volume)
// rather than passed as a plain env var, at the well-known
// GOOGLE_APPLICATION_CREDENTIALS path -- google-cloud-pubsub's implicit ADC
// credential discovery picks this up with zero application code changes.
// ============================================================

@description('Name for the ingestor Container App')
param appName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object = {}

@description('Resource ID of the existing Container Apps managed environment to join (shared with the backend)')
param environmentId string

@description('Resource ID of the shared user-assigned managed identity')
param managedIdentityId string

@description('Container registry login server')
param registryLoginServer string

@description('Shared secret the backend requires on POST /api/v1/frames')
@secure()
param backendApiKey string

@description('Deployed backend base URL, e.g. https://ca-xxxx.region.azurecontainerapps.io')
param backendUrl string

@description('Full JSON content of a GCP service-account key with roles/pubsub.subscriber on the Nest events subscription')
@secure()
param gcpServiceAccountKeyJson string

@description('Google OAuth client secret (Nest/SDM API, unrelated to the GCP Pub/Sub credential above)')
@secure()
param googleClientSecret string

@description('Google OAuth long-lived refresh token (Nest/SDM API)')
@secure()
param googleRefreshToken string

param googleClientId string
param googleDeviceAccessProjectId string
param googleDevices string
param gcpPubsubProjectId string
param gcpPubsubSubscriptionId string
param watchEventTypes string = 'sdm.devices.events.CameraMotion.Motion,sdm.devices.events.CameraPerson.Person,sdm.devices.events.CameraClipPreview.ClipPreview'

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
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      // No `ingress` block: outbound-only (Pub/Sub in, HTTP POST to the
      // backend out) -- unlike the backend, nothing calls into this app.
      registries: [
        {
          server: registryLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: [
        { name: 'backend-api-key', value: backendApiKey }
        { name: 'google-client-secret', value: googleClientSecret }
        { name: 'google-refresh-token', value: googleRefreshToken }
        { name: 'gcp-service-account-key', value: gcpServiceAccountKeyJson }
      ]
    }
    template: {
      containers: [
        {
          name: 'nest-ingestor'
          // Placeholder; the deploy pipeline's s06_deploy_ingestor step
          // builds the real image via ACR and updates it in place.
          image: 'mcr.microsoft.com/k8se/quickstart:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'BACKEND_URL', value: backendUrl }
            { name: 'BACKEND_API_KEY', secretRef: 'backend-api-key' }
            { name: 'GOOGLE_CLIENT_ID', value: googleClientId }
            { name: 'GOOGLE_CLIENT_SECRET', secretRef: 'google-client-secret' }
            { name: 'GOOGLE_REFRESH_TOKEN', secretRef: 'google-refresh-token' }
            { name: 'GOOGLE_DEVICE_ACCESS_PROJECT_ID', value: googleDeviceAccessProjectId }
            { name: 'GOOGLE_DEVICES', value: googleDevices }
            { name: 'GCP_PUBSUB_PROJECT_ID', value: gcpPubsubProjectId }
            { name: 'GCP_PUBSUB_SUBSCRIPTION_ID', value: gcpPubsubSubscriptionId }
            { name: 'WATCH_EVENT_TYPES', value: watchEventTypes }
            { name: 'GOOGLE_APPLICATION_CREDENTIALS', value: '/mnt/secrets/gcp-key.json' }
          ]
          volumeMounts: [
            { volumeName: 'gcp-key', mountPath: '/mnt/secrets' }
          ]
        }
      ]
      volumes: [
        {
          name: 'gcp-key'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'gcp-service-account-key', path: 'gcp-key.json' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

@description('Ingestor Container App resource ID')
output id string = containerApp.id

@description('Ingestor Container App name')
output name string = containerApp.name
