@description('One reusable Container App module — instantiated 5 times from main.bicep (monolith, user-service, product-service, order-service, bff). Explicit cheap defaults: Consumption plan, minReplicas 0 (scale-to-zero), 0.25 vCPU / 0.5Gi.')
param location string
param name string
param environmentId string
param acrLoginServer string
param acrUsername string
@secure()
param acrPassword string
param imageName string
param imageTag string
param targetPort int
@description('Explicit minReplicas — never left to an implicit default. 0 = scale-to-zero, no idle billing.')
param minReplicas int = 0
param maxReplicas int = 3
param cpu string = '0.25'
param memory string = '0.5Gi'
param envVars array = []
param external bool = true
@description('Secret value for the AZURE_MYSQL_ADMIN_PASSWORD env var, referenced via secretRef so it never appears in plain env vars or deployment output.')
@secure()
param mysqlAdminPassword string
@description('Set true only for the bff app — grants it a system-assigned managed identity so it can create the microservices Container Apps on demand during a live migration (see infra/provision.py, which assigns Contributor scoped to this resource group after this deploys).')
param enableSystemIdentity bool = false

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: enableSystemIdentity ? {
    type: 'SystemAssigned'
  } : null
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: external
        targetPort: targetPort
        transport: 'auto'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
        {
          name: 'mysql-password'
          value: mysqlAdminPassword
        }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: '${acrLoginServer}/${imageName}:${imageTag}'
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: envVars
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output name string = containerApp.name
output principalId string = enableSystemIdentity ? containerApp.identity.principalId : ''
