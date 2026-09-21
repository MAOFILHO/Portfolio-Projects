// Azure AI Language: the account the post-call redactor calls (Phase 8, ADR-007), and the RBAC grant
// that lets the voice agent call it without a stored key.
//
// WRITTEN AGAINST AN ALREADY-LIVE RESOURCE, same posture as aoai.bicep beside it: the account was
// created by hand on 2026-09-19 and has served every post-call redaction since. It exists here so a
// clean subscription can reach the same state (Phase 8 gate review, Spec finding: "IaC is
// incremental -- every phase adds" its module, docs/PLAN.md). **Not yet wired into `azbank-deploy`**
// (`src/azbank_deploy/`): adding a billable node to `make deploy` / `make teardown` is its own
// decision, and this file has never been deployed.
//
// VERIFIED LIVE 2026-09-21, read back from the resource itself rather than from memory:
//
//   * `az cognitiveservices account list`: kind `TextAnalytics`, sku `S`, location `canadacentral`,
//     `customSubDomainName` equal to the account name, `publicNetworkAccess` `Enabled`,
//     `disableLocalAuth` unset (`null`, i.e. keys allowed), no network ACLs, no tags.
//   * `az role assignment list --scope <account>`: exactly one assignment, `Cognitive Services
//     Language Reader`, to the voice agent's system-assigned identity.
//   * `az role definition list --name "Cognitive Services Language Reader"`: BuiltInRole, GUID
//     `7628b7b8-a8b2-4cdc-b46f-e9b35248918e`, and its `dataActions` include
//     `.../Language/analyze-conversations/jobs/action` by name -- the data-plane permission the
//     conversation PII job needs, confirmed rather than assumed from the role's English name.
//
// `az deployment group what-if` (read-only, 2026-09-21) against the live resource group:
//
//   * The account shows `Modify` on `disableLocalAuth` (unset live, `false` here: the same effect,
//     keys allowed) and on `allowProjectManagement`, a property this file does not declare.
//   * **The role assignment shows `Create`, not `NoChange`.** The live one was made by hand under a
//     different assignment name, and Azure refuses a second assignment of the same role to the same
//     principal at the same scope (`RoleAssignmentExists`). So this module cannot be deployed over
//     the live account as it stands: remove the hand-made assignment first, or deploy only into a
//     clean subscription. (aoai.bicep's assignment shows `NoChange`; it was made by that module.)
//
// **Not verified: the billing unit.** COSTS.md, "Phase 8 -- every input priced", says how Language
// counts a conversation record is unmeasured. Nothing here changes that.
//
// A diff touching this file is never auto-accepted: it provisions a billable resource
// (CLAUDE.md, STOP CONDITIONS).

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12. Matches the live resource.')
param location string = 'canadacentral'

@description('Language account name. Matches the live resource -- verified 2026-09-21.')
param name string = 'lang-azure-banking-voice-cc'

@description('Principal ID of the voice agent Container App\'s system-assigned identity -- the same one aoai.bicep and call-records-store.bicep grant to, not a second identity.')
param voiceAgentPrincipalId string

// Cognitive Services Language Reader. Data-plane only, and it includes the analyze-conversations
// job the redactor submits. Not a control-plane role: this identity cannot change the account's
// configuration or read its keys. Verified 2026-09-21 -- see the header.
var cognitiveServicesLanguageReader = '7628b7b8-a8b2-4cdc-b46f-e9b35248918e'

resource account 'Microsoft.CognitiveServices/accounts@2025-09-01' = {
  name: name
  location: location
  kind: 'TextAnalytics'
  sku: {
    name: 'S'
  }
  properties: {
    // Required for Entra ID token auth: without a custom subdomain the account accepts keys only.
    // Matches the live value, which already equals the account name.
    customSubDomainName: name
    // Matches the live value (unset, so keys allowed). The voice agent authenticates by managed
    // identity and never reads a key; flipping this to `true` is a hardening step of its own, not
    // part of writing the module down.
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
  }
}

// Scoped to this account and no wider, for the reason aoai.bicep's identical comment gives.
resource dataAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, voiceAgentPrincipalId, cognitiveServicesLanguageReader)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', cognitiveServicesLanguageReader
    )
    principalId: voiceAgentPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('The Language account\'s endpoint. This is the `LANGUAGE_ENDPOINT` the voice agent reads.')
output endpoint string = account.properties.endpoint
