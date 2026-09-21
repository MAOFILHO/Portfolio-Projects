// Azure OpenAI: the Cognitive Services account, its pinned realtime model deployment, and the RBAC
// grant that lets the voice agent call it without a stored key.
//
// WRITTEN AGAINST AN ALREADY-LIVE RESOURCE, same posture as acs.bicep beside it: the account and its
// `gpt-realtime-mini` deployment were created by hand in Phase 0 (2026-08-20) and have been live
// since. This module exists so a clean subscription can reach the same state, and so this project's
// exit from `AOAI_KEY` (Phase 7 D2) is a property in this file, not a promise in a doc.
//
// VERIFIED LIVE 2026-09-16, each against the resource itself rather than memory:
//
//   * **Every property below** -- kind, sku, customSubDomainName, the deployment's model name,
//     version, sku, capacity, and versionUpgradeOption -- read back from `az cognitiveservices
//     account show` / `az cognitiveservices account deployment list` on the live resource.
//   * **`disableLocalAuth` is currently `null`** (effectively "keys allowed") on the live resource.
//     This module declares it `false` too, for now -- see the two-part gate below for why `true` is
//     not yet safe to deploy, and `scripts/check_aoai_key_migration_consistency.py` for the real,
//     blocking check that makes that gate mechanical rather than a comment someone could miss
//     (added 2026-09-16, code-review Spec-axis finding: D5 got a real CI check, D2 initially did
//     not).
//   * **The RBAC role.** `az role definition list --name "Cognitive Services OpenAI User"`:
//     BuiltInRole, GUID `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`, and its `dataActions` include
//     `Microsoft.CognitiveServices/accounts/OpenAI/deployments/realtime/action` by name -- the exact
//     data-plane permission the realtime API needs, confirmed rather than assumed from the role's
//     English name alone.
//   * **The voice agent's identity already holds `Reader` on this account** (principal
//     `5e09fe34-8913-4aa2-80ac-618af308a88f`, `az role assignment list --all`), granted in an
//     earlier phase. `Reader`'s own `dataActions` are read-only (`Microsoft.CognitiveServices/*/
//     read`) and grant no inference access -- this module's role assignment is additive, not a
//     replacement.
//
// THIS MODULE MUST NOT BE DEPLOYED AGAINST THE LIVE RESOURCE UNTIL BOTH OF THESE HAPPEN, IN ORDER:
//
//   1. `azbank_voice_agent`'s realtime client is migrated off `AOAI_KEY` onto a Microsoft Entra ID
//      token acquired from the same system-assigned identity this module grants the role to
//      (`DefaultAzureCredential` in the deployed environment). Not done as of this file's authoring.
//   2. A real call is placed and verified working end-to-end on the new auth path -- the same
//      "ARM 200 OK does not prove delivery" standard this project holds everywhere else (CLAUDE.md,
//      Resume discipline; `docs/phase6/d16-smoke-call-result.md` is the pattern to repeat).
//
//   Only after both are true should `disableLocalAuth` below flip to `true` -- doing so retires
//   `AOAI_KEY` for real at that point; flipping it before then would break the one thing currently
//   reaching this account. The role assignment is unrelated to this sequencing and safe to apply any
//   time (it is additive, and Reader already coexists with it today).
//
// A diff touching this file is never auto-accepted: it can affect a billable, call-path-critical
// resource, even though the role-assignment half is expected to be a no-op-if-already-granted add.

@description('Azure region. Canada Central, no fallback -- docs/PLAN.md decision 12. Matches the live resource.')
param location string = 'canadacentral'

@description('AOAI account name. Matches the live resource -- verified 2026-09-16.')
param name string = 'aoai-azure-banking-voice-cc'

@description('Principal ID of the voice agent Container App\'s system-assigned identity -- the same one call-records-store.bicep grants Storage Table Data Contributor to, not a second identity.')
param voiceAgentPrincipalId string

// B3's active pin (docs/PLAN.md decision 14; azbank_voice_agent/boot.py's ALLOWED_REALTIME_MODELS),
// written as a single literal pair -- 'name', 'version' -- deliberately, not as two separate `var`
// lines. check_b3_allowlist.py's PAIR_PATTERN only catches a name and version written together this
// way; two separate variables is exactly the "living in separate, unrelated variables" gap that
// script's own docstring already names as out of its reach (found live 2026-09-16 while testing this
// file: a deliberately wrong version in two separate vars passed the check silently). This literal
// form is what makes the pair actually scannable, so scripts/check_b3_allowlist.py scans this file
// (added Phase 7, 2026-09-16) and catches drift for real, not just by naming convention.
var realtimeModelPin = ['gpt-realtime-mini', '2025-10-06']

// B3's second pin, the non-realtime text deployment the post-call summariser calls (ADR-006;
// boot.py's ALLOWED_TEXT_MODELS). Same single-literal-pair form as above, for the same reason.
// Added at the Phase 8 gate review: the deployment was hand-provisioned on 2026-09-19 and this file
// declared only the realtime pin, so the text pin had no Bicep-side enforcement. Every property in
// `textDeployment` below was read back on 2026-09-21 from `az cognitiveservices account deployment
// list`: GlobalStandard, capacity 10, NoAutoUpgrade, rai policy Microsoft.DefaultV2 (the default,
// which the realtime deployment above also carries and this file leaves unstated). Never deployed.
// `what-if` (read-only, 2026-09-21) shows this deployment `Modify` on `currentCapacity`
// (server-populated) and `raiPolicyName` (unset here, DefaultV2 live) -- the same two deltas the
// existing realtime deployment already shows, so the text pin adds no new kind of change.
var textModelPin = ['gpt-5.4-mini', '2026-03-17']

// Cognitive Services OpenAI User. Data-plane inference only (including
// .../deployments/realtime/action) -- notably NOT a control-plane role, so this identity cannot
// create or delete deployments, rotate keys, or change the account's own configuration. Verified
// 2026-09-16 against a live `az role definition list` on this subscription -- see the header.
var cognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2025-09-01' = {
  name: name
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    // Required for Entra ID (AAD) token auth to work at all -- without a custom subdomain, this
    // account only accepts key auth, making disableLocalAuth self-defeating. Matches the live value,
    // which already equals the account name.
    customSubDomainName: name
    // Phase 7 debt, not the target end-state: matches the live value (effectively `false`) until
    // the two-part gate in the header is satisfied. check_aoai_key_migration_consistency.py enforces
    // that this can only ever be `true` once AOAI_KEY is gone from the app's source -- flip this
    // value only after that check would already pass.
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
  }
}

resource realtimeDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = {
  parent: account
  name: realtimeModelPin[0]
  sku: {
    name: 'GlobalStandard'
    capacity: 1
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: realtimeModelPin[0]
      version: realtimeModelPin[1]
    }
    // Matches the live deployment -- a silent version bump is exactly what B3's runtime boot guard
    // (a separate control from this file, see boot.py) exists to catch even if this property were
    // ever wrong.
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

resource textDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = {
  parent: account
  name: textModelPin[0]
  // Deployments on one account are created one at a time; a second in parallel is refused.
  dependsOn: [realtimeDeployment]
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: textModelPin[0]
      version: textModelPin[1]
    }
    // Matches the live deployment. A drifted pin costs one call's summary and nothing else
    // (`boot.assert_text_model_safety`, non-fatal), which is why this is not the fatal guard the
    // realtime pin has.
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

// Scoped to this account and no wider -- the same reasoning call-records-store.bicep's identical
// comment gives for its own role assignment: a subscription- or resource-group-scoped grant would
// hand the voice agent inference access to every Cognitive Services account this project ever
// creates.
resource dataAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, voiceAgentPrincipalId, cognitiveServicesOpenAIUser)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAIUser
    )
    principalId: voiceAgentPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('The AOAI resource\'s base endpoint. Consumed by the voice agent once it moves off AOAI_KEY-derived configuration.')
output endpoint string = account.properties.endpoint

@description('The realtime deployment name, for anything building the deployment-scoped realtime URL.')
output realtimeDeploymentName string = realtimeDeployment.name

@description('The text deployment name: the `AOAI_TEXT_DEPLOYMENT` the voice agent reads.')
output textDeploymentName string = textDeployment.name
