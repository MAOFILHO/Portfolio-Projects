// The call-record store: a Storage account holding the day's ledger and the escalation records.
//
// WRITTEN, NOT APPLIED. Same rule the mock-core-banking module beside it follows, and for the same
// reason: docs/PLAN.md's incremental-IaC rule says every phase adds its Bicep module, and writing it
// before it is needed makes the eventual provisioning a review of something already read rather than
// something authored under deploy pressure.
//
// BEFORE THIS IS EVER DEPLOYED, THREE THINGS MUST HAPPEN, IN THIS ORDER:
//
//   1. R-08 is recomputed against a **two**-Container-App fixed cost. DONE 2026-09-11 -- it passes
//      with headroom (COSTS.md, "R-08, recomputed"), and this account is the one input that recompute
//      could not price. See the UNVERIFIED block below.
//   2. Table Storage's rate and the role GUID below are read from live sources rather than from
//      memory. BOTH DONE 2026-09-12 -- see the VERIFIED block below.
//   3. Marco types `APPROVED: Phase 5` for the provisioning step. GIVEN 2026-09-11.
//
// A diff touching this file is never auto-accepted: it provisions a billable resource.
//
// ---
//
// VERIFIED 2026-09-12, each against a live source rather than documentation:
//
//   * **The role definition GUID below.** Read back from `az role definition list --name "Storage
//     Table Data Contributor"` on subscription 960936b9-ecde-465b-be8d-776ca077dcd0. It matches
//     character for character and the role is a BuiltInRole. This was the single most likely thing
//     in this file to be wrong, and getting it wrong produces a role assignment that returns 200 OK
//     and grants nothing.
//   * **Table Storage's price.** Read from the Retail Prices API for `canadacentral` / `Standard
//     LRS`: $0.00036 per 10,000 operations, $0.05 per GB-month. This workload costs under a cent a
//     month. COSTS.md, "The last unpriced input, priced".
//   * **This file compiles.** `az bicep build` exits 0 with no lint output, on Bicep CLI v0.47.16,
//     installed 2026-09-12. The header line that said no `bicep` CLI exists here is superseded.
//
// STILL UNVERIFIED, AND NAMED RATHER THAN ASSUMED:
//
//   * **That a role assignment returning ARM 200 OK proves access.** It does not. CLAUDE.md is
//     explicit that creation is not delivery. A correct GUID removes one way for the grant to be
//     empty; it does not prove the grant works. The exit criteria still require a write that is then
//     read back before anything here is described as working.
//   * **There is still no `main.bicep`**, so this module compiles in isolation and has never been
//     what-if'd against the real resource group. Human review remains the only check on its intent.

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12.')
param location string = 'canadacentral'

@description('Storage account name. Globally unique, 3-24 chars, lowercase letters and digits only -- which is why this one carries no hyphens while every other resource in this project does.')
@minLength(3)
@maxLength(24)
param name string = 'stazbankcallrecords'

@description('Principal ID of the voice agent Container App\'s system-assigned identity. The same identity B3\'s boot guard already uses to read ARM -- not a second one.')
param voiceAgentPrincipalId string

@description('Table the call-record store writes to. Must match call_records/store.py\'s TABLE_NAME.')
param tableName string = 'callrecords'

// Storage Table Data Contributor. Read, write and delete on table entities, and nothing else --
// notably NOT a control-plane role, so this identity cannot change the account's own configuration,
// read its keys, or reach blobs or queues.
//
// VERIFIED 2026-09-12 against a live `az role definition list` on this subscription: exact match,
// BuiltInRole. See the header.
var storageTableDataContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  sku: {
    // The cheapest option that serves tables. Locally-redundant is the right redundancy for a
    // prototype's operational bookkeeping: losing it costs a day's cap accounting and a list of
    // escalations, not anybody's money. Geo-redundancy would be paying for a guarantee nothing here
    // needs.
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    // **Keys off, entirely.** This is what makes "no connection string anywhere" enforced by the
    // resource rather than by everyone remembering -- with shared-key access disabled, a connection
    // string is not merely discouraged, it does not work. `boot.py`'s own refusal to accept one is
    // the same rule stated a second time, on the other side; either alone is a convention, and both
    // together are a property.
    allowSharedKeyAccess: false
    // Nothing here is ever public. There are no blobs, and if there were, they would not be either.
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    // Default action stays Allow: the voice agent reaches this over the public Storage endpoint from
    // a Container App with no VNet integration, so a network rule denying by default would refuse
    // the one caller this account has. Locking this down belongs with Phase 7's networking work,
    // where the VNet exists to allow -- doing it here would produce a store nothing can reach.
    publicNetworkAccess: 'Enabled'
  }
}

resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: account
  name: 'default'
}

resource table 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: tableName
}

// Scoped to this account and no wider. A subscription- or resource-group-scoped assignment would
// grant the voice agent table access to every storage account this project ever creates, which is
// the kind of over-grant that is invisible until it matters.
resource dataAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, voiceAgentPrincipalId, storageTableDataContributor)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', storageTableDataContributor
    )
    principalId: voiceAgentPrincipalId
    // Stated explicitly. Without it, ARM can fail the assignment when the principal is newly
    // created and not yet replicated -- it guesses the type by looking the principal up, and a
    // lookup that comes back empty is a deployment error that reads as a permissions problem.
    principalType: 'ServicePrincipal'
  }
}

@description('The table endpoint the voice agent uses as CALL_RECORDS_ACCOUNT_URL. An account URL, never a connection string -- see boot.py, which refuses the latter outright.')
output tableEndpoint string = account.properties.primaryEndpoints.table
