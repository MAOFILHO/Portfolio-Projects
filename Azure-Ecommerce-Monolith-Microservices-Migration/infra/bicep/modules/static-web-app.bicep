@description('Azure Static Web App — Free tier (100GB bandwidth/mo, 1GB storage) for the React frontend.')
param location string
param name string

resource staticSite 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    buildProperties: {
      skipGithubActionWorkflowGeneration: true
    }
  }
}

output defaultHostname string = staticSite.properties.defaultHostname
output name string = staticSite.name
