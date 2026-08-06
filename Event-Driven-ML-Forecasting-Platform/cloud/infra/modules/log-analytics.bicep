// The one soft-delete-prone resource in this stack (14-day soft delete, no
// purge API -- only "recover"). Minimal retention/SKU to keep it cheap;
// mainly here for basic VM diagnostics and so the collision/soft-delete
// handling the user asked for has a real target -- see naming.py.
param location string
param namePrefix string
param tags object

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-${namePrefix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

output workspaceName string = logAnalytics.name
output workspaceId string = logAnalytics.id
