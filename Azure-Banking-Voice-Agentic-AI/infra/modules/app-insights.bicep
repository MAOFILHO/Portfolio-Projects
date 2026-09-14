// Workspace-based Application Insights for Phase 6 observability (issue #62, follow-up to #61).
//
// APPLIED 2026-09-14 (Marco, via infra/provision-app-insights.sh) -- `appi-azure-banking-voice`
// exists, bound to workspace-rgazurebankingvoiceagenticai1D, provisioningState Succeeded. This
// module stays as the record of what was deployed, same reason the two modules beside it do.
//
// BEFORE THIS IS EVER DEPLOYED, THESE MUST HAPPEN, IN THIS ORDER:
//
//   1. Issue #61 (Phase 6 code) lands and passes CI against the in-memory exporter. This resource is
//      the destination that code's exporter needs, not a prerequisite for it.
//   2. R-08 is recomputed against Application Insights sharing the shared 5 GB Log Analytics grant.
//      DONE 2026-09-13 -- COSTS.md, "R-08, recomputed for Application Insights sharing the shared 5
//      GB grant": worst-case bound is ~8.2 MB/month, 0.16% of the grant. $0.00/mo added.
//   3. Marco types `APPROVED: Phase 6` for the provisioning step. GIVEN 2026-09-12 (per
//      PROJECT_STATE.md), but per CLAUDE.md this diff still gets a human look before it applies --
//      "never auto-accept a diff that provisions a billable resource... no matter how mechanical."
//
// A diff touching this file is never auto-accepted: it provisions a billable resource (though the
// recompute above says the bill is $0.00/mo at this project's volume).
//
// ---
//
// RESOLVED SINCE FIRST WRITTEN (2026-09-14, first two live runs of infra/provision-app-insights.sh):
//
//   * **This file did not compile as first written.** Line 98's `@description` used `''` to escape
//     an apostrophe (SQL-style); Bicep needs `\'`. Caught by the first live deployment attempt
//     (BCP071/BCP236), fixed, reverified with `az bicep build`.
//   * **The apiVersion for `Microsoft.Insights/components`** (`2020-02-02` below) deploys cleanly --
//     confirmed live, `provisioningState: Succeeded`.
//   * **The Bicep `connectionString` output is real but unreadable after the fact.** ARM redacts
//     `@secure()` outputs from deployment history unconditionally, so `az deployment group show`
//     always returns an empty value for it -- not a bug in this module, a property of how ARM
//     handles secure outputs everywhere. `infra/provision-app-insights.sh` reads the live resource
//     directly instead (`az monitor app-insights component show`), which is not subject to that
//     redaction. The output stays here as the documented, discoverable value regardless.
//
// STILL OPEN:
//
//   * **The exact ingestion role an Entra-authenticated identity needs.** Not this module's problem
//     to solve -- see `infra/provision-app-insights.sh`'s own header. This module provisions the
//     resource; it deliberately assigns no role to anyone, because the one role that would matter
//     (Monitoring-ingestion-equivalent for Application Insights, distinct from `Monitoring Metrics
//     Publisher`, which is Azure Monitor *metrics* ingestion, not App Insights telemetry) is an open
//     `/research` question per D10 (`docs/phase6/exit-criteria.md`) and CLAUDE.md's skill discipline
//     means this session does not invoke `/research` to settle it. Guessing a role name here would be
//     exactly the "invent an IAM role from memory" mistake the ticket that produced this file was
//     told not to make.

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12.')
param location string = 'canadacentral'

@description('Application Insights component name.')
param name string = 'appi-azure-banking-voice'

@description('The Log Analytics workspace this component is workspace-based on. Restricted to the one workspace proven to deliver rows (PROJECT_STATE.md, "Live Azure state") -- an `@allowed` list of one, deliberately, so a typo or a stale default cannot silently bind this to `...aiCS` (stale since 2026-08-25) or the `...aixC` orphan.')
@allowed([
  'workspace-rgazurebankingvoiceagenticai1D'
])
param logAnalyticsWorkspaceName string = 'workspace-rgazurebankingvoiceagenticai1D'

// The workspace already exists (auto-provisioned during Phase 0's Container Apps environment
// create, `docs/phase0/findings.md` "Stage 12 -- auto-created Log Analytics workspace") -- this
// module never creates one, matching D4's explicit settling of PROJECT_STATE.md open item 8
// ("the Log Analytics auto-provision choice"): bind explicitly, don't let a fourth workspace get
// auto-provisioned by omission the way the first three were.
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    // Workspace-based, not classic -- D4's own words. Ingestion and storage live in the Log
    // Analytics workspace above; this resource is the App-Insights-shaped view over it.
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
    // The voice agent Container App has no VNet integration (mock-core-banking.bicep's own note:
    // "no reason for it to be reachable from the internet" doesn't apply here in reverse -- this
    // resource has to be reachable FROM the Container App, which reaches it over the public
    // internet). Locking this down belongs with Phase 7's networking work, same deferral as
    // call-records-store.bicep's `publicNetworkAccess: 'Enabled'`.
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    // Local auth (the connection-string / instrumentation-key path) stays ENABLED. D10's preferred
    // path is Entra-authenticated ingestion via the existing managed identity, but which IAM role
    // that needs is an open `/research` question (see this file's header) -- disabling local auth
    // now would remove the only ingestion path this ticket can actually verify works, before the
    // role question is settled. Revisit when Phase 7's no-keys direction and D10's role question
    // both resolve -- named here as the Phase 7 debt D10 already describes, not a new one.
    DisableLocalAuth: false
  }
}

@description('The connection string the relay uses as APPLICATIONINSIGHTS_CONNECTION_STRING. Treated as sensitive: it is a bearer credential for ingestion (and, while DisableLocalAuth is false above, sufficient on its own -- no Entra token needed) exactly like a storage connection string, which is why call-records-store.bicep refuses one outright for its own resource. Unlike that resource, this one is not being asked to go keyless yet -- see DisableLocalAuth above.')
@secure()
output connectionString string = appInsights.properties.ConnectionString

@description('The component\'s ARM resource id, for a future role assignment once D10\'s role question is settled.')
output appInsightsId string = appInsights.id

@description('Application Insights instrumentation key. Retained only because some tooling still asks for it by this name; the relay itself uses the connection string, never this.')
output instrumentationKey string = appInsights.properties.InstrumentationKey
