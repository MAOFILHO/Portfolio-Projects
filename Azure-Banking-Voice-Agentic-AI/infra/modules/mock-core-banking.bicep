// mock-core-banking as its own Container App.
//
// WRITTEN, NOT APPLIED. Phase 3 provisions nothing (docs/phase3/exit-criteria.md, criterion 9) --
// this module exists because docs/PLAN.md's incremental-IaC rule says every phase adds its Bicep
// module, and because writing it now is what makes the eventual provisioning a review of something
// already read rather than something authored under deploy pressure.
//
// BEFORE THIS IS EVER DEPLOYED, TWO THINGS MUST HAPPEN, IN THIS ORDER:
//
//   1. R-08 is recomputed against a **two**-Container-App fixed cost. **DONE 2026-09-11** and it
//      passes with headroom: fixed $14.60/mo, 45-67 demo runs/month against a gate of 5 (COSTS.md,
//      "R-08, recomputed"). This container's own marginal cost is **$7.88/mo, not $5.72** -- the
//      Container Apps free grant is per subscription and the voice agent already consumes all of
//      it, so this one bills on its whole consumption rather than net of a grant.
//   2. Marco types `APPROVED: Phase 5` for the provisioning step itself. **GIVEN 2026-09-11.**
//      (The token names Phase 5, not Phase 3: this module was written in Phase 3 and is applied in
//      Phase 5, and the approval that matters is the one for the phase that spends the money.)
//
// A diff touching this file is also never auto-accepted: it provisions a billable resource.
//
// ---
//
// REVIEWED 2026-09-11 (issue #56), before applying. What was checked, and what it still cannot be:
//
//   * `external: false` -- still internal. This is what keeps deferring shared-secret auth to
//     Phase 7 a considered decision rather than a PIN crossing the public internet in a body.
//   * 0.25 vCPU / 0.5 GiB, minReplicas 1, maxReplicas 1 -- unchanged, and R-08's recomputed
//     arithmetic assumes exactly this shape. **maxReplicas 1 is load-bearing twice**: it is what
//     keeps that figure true, and it is what makes the call-record ledger's read-then-write correct
//     (`call_records/store.py`). Changing it invalidates both, and both now say so.
//   * A liveness probe on /health, which touches no account state -- so a probe can never be the
//     thing that wakes or contends with the database.
//   * No number-release or number-delete call, here or in any script in this repo. **Checked
//     2026-09-11 rather than assumed** (issue #56): every hit for release/delete/purge across all
//     83 shell, Python, Bicep and Makefile files is either a read-only `phonenumber list`, an
//     unrelated identifier, or a comment restating the rule. `04-teardown-and-r08.sh` says in its
//     own words that it never calls a release, and it does not.
//   * **Still not validated by any tool.** There is no `bicep` CLI here and still no `main.bicep`,
//     so this has never been compiled, linted or what-if'd, and "consistent with the existing
//     modules" now has exactly one sibling to be consistent with. Human review is the only check
//     that exists, which is why this list is written down rather than done silently.

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
