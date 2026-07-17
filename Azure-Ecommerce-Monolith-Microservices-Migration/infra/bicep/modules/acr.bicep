@description('Azure Container Registry — Basic tier, the cheapest SKU that supports az acr build (cloud-side image builds, no local Docker daemon required).')
param location string
param name string

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: name
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

output loginServer string = registry.properties.loginServer
output registryName string = registry.name
