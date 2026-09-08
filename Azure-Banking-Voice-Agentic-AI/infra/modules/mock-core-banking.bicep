// mock-core-banking as its own Container App.
//
// WRITTEN, NOT APPLIED. Phase 3 provisions nothing (docs/phase3/exit-criteria.md, criterion 9) --
// this module exists because docs/PLAN.md's incremental-IaC rule says every phase adds its Bicep
// module, and because writing it now is what makes the eventual provisioning a review of something
// already read rather than something authored under deploy pressure.
//
// BEFORE THIS IS EVER DEPLOYED, TWO THINGS MUST HAPPEN, IN THIS ORDER:
//
//   1. R-08 is recomputed against a **two**-Container-App fixed cost. This would be the project's
//      second always-on container, and fixed cost is the line the entire $25/month ceiling turns
//      on (PROJECT_STATE.md, "Active risks"). The current figure -- Phase 0's 79.2 demo runs/month
//      -- assumes one.
//   2. Marco types `APPROVED: Phase 3` for the provisioning step itself. Deploying this creates a
//      billable resource, which CLAUDE.md's stop conditions gate absolutely.
//
// A diff touching this file is also never auto-accepted: it provisions a billable resource.

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12.')
param location string = 'canadacentral'

@description('Name of the existing Container Apps environment to deploy into.')
param environmentName string

@description('Container image, including tag. Pinned by digest or explicit tag -- never :latest.')
param image string

@description('Container App name.')
param name string = 'ca-azbank-core-banking'

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource coreBanking 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        // INTERNAL, not external. Only the voice agent calls this service, and it holds account
        // balances -- there is no reason for it to be reachable from the internet. This is also
        // what makes deferring shared-secret auth to Phase 7 a considered decision rather than an
        // omission (issue #25): the hop is not exposed in the first place.
        external: false
        targetPort: 8001
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'mock-core-banking'
          image: image
          resources: {
            // Same shape as the voice agent's container. docs/PLAN.md's budget models the fixed
            // monthly cost on exactly this size; changing it invalidates that arithmetic.
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8001
              }
            }
          ]
        }
      ]
      scale: {
        // min-replicas=1 for the same reason the voice agent uses it: a cold start measured in
        // seconds is disqualifying when a caller is already on the line waiting for a balance.
        // This is precisely why point 1 above is a precondition and not a formality -- this
        // replica bills continuously, exactly like the first one.
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

@description('Internal FQDN the voice agent would use as CORE_BANKING_URL.')
output internalUrl string = 'http://${coreBanking.properties.configuration.ingress.fqdn}'
