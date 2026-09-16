// The Container Apps environment every Container App in this project deploys into.
//
// WRITTEN, NOT APPLIED. The environment already exists live (created by hand, 2026-09-01, Phase 0's
// findings -- "Stage 12, auto-created Log Analytics workspace"). This module exists for the same
// reason mock-core-banking.bicep and aoai.bicep do: Phase 7's goal is that every resource this
// project owns has a Bicep module, whether or not that module is the thing that originally created
// it. Values below are read from the live resource (`az containerapp env show`, 2026-09-16), not
// guessed -- deploying this module in Incremental mode against the live environment should be a
// no-op, not a change.
//
// A diff touching this file is never auto-accepted: even though the resource already exists, this
// module is capable of provisioning one on a subscription where it doesn't (CLAUDE.md, "never
// auto-accept a diff that provisions a billable resource").

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12.')
param location string = 'canadacentral'

@description('Container Apps environment name.')
param name string = 'cae-azure-banking-voice-p0'

@description('The Log Analytics workspace this environment sends container logs to. Restricted to the one workspace proven to deliver rows (PROJECT_STATE.md, "Live Azure state") -- the same `@allowed` list of one that app-insights.bicep uses, so a typo or a stale default cannot silently bind this to `...aiCS` (stale since 2026-08-25) or the `...aixC` orphan.')
@allowed([
  'workspace-rgazurebankingvoiceagenticai1D'
])
param logAnalyticsWorkspaceName string = 'workspace-rgazurebankingvoiceagenticai1D'

// The workspace already exists (same one app-insights.bicep binds to) -- this module never creates
// one, for the identical reason: don't let a fourth workspace get auto-provisioned by omission.
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspace.properties.customerId
        sharedKey: logAnalyticsWorkspace.listKeys().primarySharedKey
      }
    }
    // Consumption only -- matches live (`az containerapp env show`, 2026-09-16: workloadProfiles is
    // exactly one entry, type Consumption). docs/PLAN.md's budget models this project's fixed cost on
    // the Consumption plan; adding a Dedicated workload profile would invalidate that arithmetic the
    // same way changing mock-core-banking.bicep's container size would.
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    // No VNet integration live -- every Container App in this environment reaches the internet
    // directly (mock-core-banking.bicep's `external: false` restricts ingress per-app, not at the
    // environment level). Locking this down is Phase 7 networking work not yet scoped, same deferral
    // already named in app-insights.bicep and call-records-store.bicep.
    vnetConfiguration: null
    zoneRedundant: false
  }
}

@description('The environment\'s ARM resource id and name, for Container App modules (mock-core-banking.bicep, and any future voice-agent module) to reference via an `existing` lookup by name -- matching the pattern those modules already use.')
output id string = environment.id

@description('The environment name, matching the `environmentName` param mock-core-banking.bicep already takes.')
output name string = environment.name
