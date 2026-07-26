// ============================================================
// Azure Static Web App (Free tier) — hosts the React + TypeScript dashboard.
// Deployment content is pushed post-provision by the CLI (s08_deploy_frontend)
// via the SWA CLI / deployment token — Bicep only provisions the empty app.
// ============================================================

@description('Name for the Static Web App')
param name string

@description('Azure region (Static Web Apps only supports a subset of regions)')
param location string

@description('Resource tags')
param tags object = {}

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    provider: 'None'
  }
}

@description('Static Web App resource ID')
output id string = staticWebApp.id

@description('Static Web App name')
output name string = staticWebApp.name

@description('Static Web App default hostname')
output defaultHostname string = staticWebApp.properties.defaultHostname
