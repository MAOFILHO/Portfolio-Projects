// ============================================================
// Observability — Log Analytics Workspace + Application Insights
// Cheapest viable tier: PerGB2018 with a short retention window.
// ============================================================

@description('Name for the Log Analytics workspace')
param logAnalyticsName string

@description('Name for the Application Insights resource')
param appInsightsName string

@description('Azure region')
param location string

@description('Resource tags')
param tags object = {}

@description('Log retention in days (kept short to minimize cost)')
param retentionInDays int = 30

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

@description('Log Analytics workspace resource ID')
output logAnalyticsId string = logAnalytics.id

@description('Log Analytics workspace GUID (customerId) -- what the Logs Query SDK/API takes, distinct from the ARM resource ID above')
output logAnalyticsWorkspaceGuid string = logAnalytics.properties.customerId

@description('Application Insights connection string')
output connectionString string = appInsights.properties.ConnectionString

@description('Application Insights instrumentation key')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('Application Insights resource name (for Azure Portal deep links)')
output appInsightsName string = appInsights.name
