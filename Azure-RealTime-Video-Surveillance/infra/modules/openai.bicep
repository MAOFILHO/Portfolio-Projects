// ============================================================
// Azure OpenAI — Cognitive Services account backing the Semantic Kernel
// agents (Triage, Notification Policy, NL Event Query, Nest WebRTC
// Diagnostic, Observability Monitoring).
//
// Modeled on modules/vision.bicep: same CognitiveServices account + RBAC
// shape (disableLocalAuth=true, RBAC-only, no keys), but kind=OpenAI plus a
// nested chat model deployment. Kept as its own module/account (not folded
// into vision.bicep) since Azure OpenAI model/region availability is a
// distinct constraint from Vision's.
// ============================================================

@description('Name for the Azure OpenAI account')
param name string

@description('Azure region. Must be a region where the chosen chat model is available for deployment.')
param location string

@description('Resource tags')
param tags object = {}

@allowed(['S0'])
@description('Azure OpenAI only offers the S0 SKU.')
param skuName string = 'S0'

@description('Name of the chat model deployment (referenced by app settings as OPENAI_CHAT_DEPLOYMENT)')
param chatDeploymentName string = 'chat'

// gpt-4o-mini (2024-07-18) -- this project's original default -- was fully
// retired ("ServiceModelDeprecated") by the time this was first deployed;
// gpt-5-mini is its current-generation, Generally Available (not even
// "Deprecating") successor, confirmed via `az cognitiveservices usage list`
// against this subscription. Re-check availability before reusing this
// default long after this comment was written -- model retirement is
// ongoing and out of this project's control.
@description('Chat model name to deploy')
param chatModelName string = 'gpt-5-mini'

@description('Chat model version')
param chatModelVersion string = '2025-08-07'

// GlobalStandard, not Standard: confirmed via `az cognitiveservices usage
// list --location <region>` that this subscription has GlobalStandard quota
// for gpt-5-mini/gpt-4o-mini in eastus2, not a regional Standard allocation.
@description('Deployment SKU for the chat model (e.g. GlobalStandard, Standard, DataZoneStandard) -- must match a SKU this subscription actually has quota under for the chosen model/region, not just one the model lists as theoretically supported.')
param chatSkuName string = 'GlobalStandard'

@description('Model deployment capacity, in thousands of tokens-per-minute. 100 (still a small fraction of typical subscription quota, ~3000 for GlobalStandard gpt-5-mini) gives real headroom over the previous default of 10, which was hit repeatedly under normal multi-agent usage (every alert triggers 2-3 chat completion calls in quick succession).')
param chatCapacity int = 100

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: skuName
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: openAiAccount
  name: chatDeploymentName
  sku: {
    name: chatSkuName
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
  }
}

@description('Azure OpenAI account resource ID')
output id string = openAiAccount.id

@description('Azure OpenAI account name')
output name string = openAiAccount.name

@description('Azure OpenAI endpoint')
output endpoint string = openAiAccount.properties.endpoint

@description('Chat model deployment name')
output chatDeploymentName string = chatDeployment.name
