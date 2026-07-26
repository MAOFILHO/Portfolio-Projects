// ============================================================
// Azure AI Vision — Cognitive Services account for Image Analysis 4.0
//
// Adapted from Video-Agents-Foundry-Solution/infra/modules/ai-foundry.bicep:
// keeps the same CognitiveServices account + RBAC shape, but drops the AI
// Foundry project and GlobalStandard model deployment (this system doesn't
// use an LLM) and sets kind=ComputerVision with a low-cost SKU (F0 free
// tier or S1 pay-per-call) instead of an S0 Foundry hub.
// ============================================================

@description('Name for the Vision Cognitive Services account')
param name string

@description('Azure region. Must be a region where Image Analysis 4.0 is available.')
param location string

@description('Resource tags')
param tags object = {}

@allowed(['F0', 'S1'])
@description('F0 = free tier (1 per subscription, 20 calls/min). S1 = pay-per-call, no rate cap.')
param skuName string = 'S1'

resource visionAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  tags: tags
  kind: 'ComputerVision'
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

@description('Vision account resource ID')
output id string = visionAccount.id

@description('Vision account name')
output name string = visionAccount.name

@description('Vision Image Analysis endpoint')
output endpoint string = visionAccount.properties.endpoint
