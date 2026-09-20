// The voice-agent Container App.
//
// WRITTEN, NOT APPLIED. Modeled on `ca-azbank-echo-p0`'s live shape (`az containerapp show`,
// 2026-09-16) rather than a fresh design -- Marco's call, 2026-09-16: no separate "voice-agent" app
// exists or has ever existed; `ca-azbank-echo-p0` already is the caller-facing service and stays the
// production app going forward. This module keeps its live name so an Incremental deploy against the
// live resource group is a no-op, not a second app standing up beside the first.
//
// A diff touching this file is never auto-accepted: it provisions a billable resource, and (unlike
// container-apps-env.bicep) it also carries every value the relay needs to run as a `@secure()`
// param, never a literal. Four of the five (ACS connection string, AOAI key, App Insights connection
// string, Docker Hub password) are genuinely confidential; the fifth, `appBaseUrl`, is not (see its
// own param below for why it still carries the annotation).
//
// STILL OPEN, same as the rest of Phase 7's current-state table:
//
//   * **AOAI_KEY is still a live secret here.** D2 (docs/phase7/exit-criteria.md) retires it once the
//     relay's data-plane auth moves to the system-assigned identity; that migration is app code, not
//     this module, and hasn't happened yet. `aoaiKey` stays a required `@secure()` param until it
//     does -- removing the param now would just make a real deploy fail, not complete the migration.
//   * **`AZURE_MONITOR_AUTH=connection_string`, not identity.** D10's IAM role question
//     (app-insights.bicep's own header) is still open; this module carries the same named fallback the
//     live app already runs on, not a role assignment that doesn't exist yet.

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12.')
param location string = 'canadacentral'

@description('Name of the existing Container Apps environment to deploy into.')
param environmentName string

@description('Container App name. Matches the live app so this module describes it rather than standing up a second one.')
param name string = 'ca-azbank-echo-p0'

@description('Container image, including tag. Pinned by explicit tag -- never :latest, same rule mock-core-banking.bicep states for its own image param.')
param image string

@description('ACS connection string. The relay uses this to answer/manage the call, distinct from the ACS resource itself (acs.bicep) which this string authenticates against.')
@secure()
param acsConnectionString string

@description('The relay\'s own public base URL, used to build the ACS Event Grid webhook callback it registers on startup. Not actually confidential -- it is the app\'s own public FQDN, the same value `output fqdn` below exposes. `@secure()` stays anyway: this value flows into the Container App\'s `secrets` array below (matching the live app\'s shape exactly, `az containerapp show` 2026-09-16), and Bicep\'s linter requires any value assigned there to come from a secure source -- not a statement that this particular value is sensitive.')
@secure()
param appBaseUrl string

@description('AOAI data-plane key. Still required live -- see this file\'s header, D2 is not yet done. Blocked from ever being paired with disableLocalAuth: true on the AOAI side by check_aoai_key_migration_consistency.py; this module does not duplicate that check.')
@secure()
param aoaiKey string

@description('Application Insights connection string (D8/#61). Local-auth ingestion, matching app-insights.bicep\'s own DisableLocalAuth: false -- see that module\'s header for why.')
@secure()
param appInsightsConnectionString string

@description('Docker Hub password for the private registry pull. Docker Hub vs ACR is PROJECT_STATE.md open item 4, still on Docker Hub.')
@secure()
param dockerHubPassword string

@description('Docker Hub username for the registry pull.')
param dockerHubUsername string = 'maofilho'

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

// Referenced for its table endpoint below, rather than hardcoding the URL -- call-records-store.bicep
// already outputs `tableEndpoint` the same way; this module reads the live resource instead of
// duplicating that string, so a future account migration only ever needs one edit.
resource callRecordsAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: 'stazbankcallrecords'
}

resource voiceAgent 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    // System-assigned only -- the identity D2's managed-identity migration and Storage Table Data
    // Contributor (already granted, live) both hang off. No user-assigned identity anywhere in this
    // project.
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        // EXTERNAL, unlike mock-core-banking.bicep -- this is the app ACS's Event Grid webhook and
        // the public phone number's media path actually reach. allowInsecure stays false (default):
        // unlike the internal core-banking hop, there is no CORE_BANKING_URL-style reason to accept
        // plain HTTP here, and ACS's own webhook delivery expects TLS.
        external: true
        targetPort: 8000
        transport: 'Auto'
      }
      registries: [
        {
          server: 'docker.io'
          username: dockerHubUsername
          passwordSecretRef: 'dockerio-maofilho'
        }
      ]
      secrets: [
        { name: 'acs-conn', value: acsConnectionString }
        { name: 'app-base-url', value: appBaseUrl }
        { name: 'aoai-key', value: aoaiKey }
        { name: 'appinsights-conn', value: appInsightsConnectionString }
        { name: 'dockerio-maofilho', value: dockerHubPassword }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: image
          // No `probes` block, unlike mock-core-banking.bicep's `/health` liveness probe -- the live
          // app carries none either (`az containerapp show`, 2026-09-16). Matching live, not an
          // omission: adding one here would be new behavior this module doesn't have Marco's sign-off
          // to introduce, and mock-core-banking.bicep's probe checks no account state for a different
          // reason (it touches nothing this app relies on) that doesn't automatically transfer here.
          resources: {
            // Same shape as mock-core-banking.bicep's container -- docs/PLAN.md's budget models the
            // fixed monthly cost on exactly this size for both apps.
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'ACS_CONNECTION_STRING', secretRef: 'acs-conn' }
            { name: 'APP_BASE_URL', secretRef: 'app-base-url' }
            { name: 'AOAI_ENDPOINT', value: 'https://aoai-azure-banking-voice-cc.openai.azure.com/' }
            { name: 'AOAI_DEPLOYMENT', value: 'gpt-realtime-mini' }
            { name: 'AOAI_KEY', secretRef: 'aoai-key' }
            { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
            { name: 'AZURE_RESOURCE_GROUP', value: resourceGroup().name }
            { name: 'AOAI_ACCOUNT_NAME', value: 'aoai-azure-banking-voice-cc' }
            { name: 'CORE_BANKING_URL', value: 'http://ca-azbank-core-banking.internal.${environment.properties.defaultDomain}' }
            { name: 'CALL_RECORDS_ACCOUNT_URL', value: callRecordsAccount.properties.primaryEndpoints.table }
            // Phase 8: where the post-call pipeline writes redacted transcripts (Blob, same account).
            { name: 'TRANSCRIPTS_ACCOUNT_URL', value: callRecordsAccount.properties.primaryEndpoints.blob }
            // Phase 8: the redactor's Language endpoint and the summariser's text deployment (ADR-006, the
            // B3 text pin). Both optional in the app -- unset switches that one feature off.
            { name: 'LANGUAGE_ENDPOINT', value: 'https://lang-azure-banking-voice-cc.cognitiveservices.azure.com/' }
            { name: 'AOAI_TEXT_DEPLOYMENT', value: 'gpt-5.4-mini' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-conn' }
            // Named fallback, not identity -- see this file's header, D10 still open.
            { name: 'AZURE_MONITOR_AUTH', value: 'connection_string' }
          ]
        }
      ]
      scale: {
        // min-replicas=1, max-replicas=1 -- a caller already on the line cannot wait through a cold
        // start, and R-08's recomputed budget assumes exactly one billing replica (same load-bearing
        // constraint mock-core-banking.bicep's header names for its own app).
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

@description('The app\'s public FQDN -- what ACS\'s Event Grid subscription and the phone number\'s media path actually call.')
output fqdn string = voiceAgent.properties.configuration.ingress.fqdn

@description('The system-assigned identity\'s principal id, for role assignments (Storage Table Data Contributor, AOAI Reader -- already granted live to this app\'s real identity -- and D2\'s eventual data-plane role) to reference.')
output principalId string = voiceAgent.identity.principalId
