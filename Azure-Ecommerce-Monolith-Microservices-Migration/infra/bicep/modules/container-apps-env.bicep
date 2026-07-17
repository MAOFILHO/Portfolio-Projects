@description('Container Apps Environment — Consumption plan only (no Dedicated/workload profiles), so every app inside it defaults to pay-per-use, scale-to-zero billing.')
param location string
param name string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

output environmentId string = environment.id
@description('The environment default domain (e.g. "orange-sea-123.eastus.azurecontainerapps.io") — lets the BFF construct FQDNs for microservices Container Apps it creates on the fly at runtime, without querying Azure again for a value that is deterministic.')
output defaultDomain string = environment.properties.defaultDomain
