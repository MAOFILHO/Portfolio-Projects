@description('''
Deploys the Azure FOUNDATION plus the monolith ("before") stack only:
ACR (Basic), Container Apps Environment (Consumption), MySQL Flexible Server
(Burstable B1ms, 4 logical DBs pre-created), a Static Web App (Free) for the
React frontend, and 2 Container Apps — monolith and bff. The three
microservices' Container Apps (user-, product-, order-service) are
deliberately NOT deployed here: they don't exist until the live migration
creates them on demand via the Azure SDK (see bff/app/azure_traffic.py),
which is the whole point of the demo — watching real Azure resources spin
up as the migration runs, not a pre-provisioned stack where "migration"
just flips a switch. The bff Container App gets a system-assigned managed
identity with Contributor scoped to this resource group so it can create
those Container Apps itself at runtime (see infra/provision.py). Every SKU
below is the cheapest tier that satisfies the requirement, chosen explicitly
in Phase 2 and never left to a CLI default. Names are resolved by
infra/provision.py BEFORE this deployment runs, after checking for
collisions with existing or soft-deleted resources.
''')
param location string = resourceGroup().location

param acrName string
param logAnalyticsName string
param containerAppsEnvName string
param staticWebAppName string
param mysqlServerName string

@description('Azure Static Web Apps is only available in a handful of regions (Central US, East US 2, West US 2, West Europe, East Asia) — NOT every region that supports Container Apps/MySQL/etc. (e.g. plain "East US" does not support it). Kept as its own parameter, independently configurable via AZURE_STATIC_WEB_APP_LOCATION in .env, so the primary `location` can be whatever region the user wants without breaking this one resource.')
param staticWebAppLocation string = 'eastus2'

param mysqlAdminUsername string
@secure()
param mysqlAdminPassword string

@description('Image tag to deploy for every service — set by provision.py after az acr build pushes images.')
param imageTag string = 'latest'

@description('Set true only when Container Apps should be created with minReplicas=1 for a live demo. Default false = scale-to-zero, effectively $0 idle cost.')
param keepWarm bool = false

var minReplicas = keepWarm ? 1 : 0

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  params: {
    location: location
    name: logAnalyticsName
  }
}

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    name: acrName
  }
}

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'containerAppsEnv'
  params: {
    location: location
    name: containerAppsEnvName
    logAnalyticsCustomerId: logAnalytics.outputs.customerId
    logAnalyticsSharedKey: logAnalytics.outputs.sharedKey
  }
}

module mysql 'modules/mysql.bicep' = {
  name: 'mysql'
  params: {
    location: location
    name: mysqlServerName
    adminUsername: mysqlAdminUsername
    adminPassword: mysqlAdminPassword
  }
}

module staticWebApp 'modules/static-web-app.bicep' = {
  name: 'staticWebApp'
  params: {
    location: staticWebAppLocation
    name: staticWebAppName
  }
}

var commonEnv = [
  { name: 'RUN_MODE', value: 'azure' }
  { name: 'AZURE_MYSQL_HOST', value: mysql.outputs.fqdn }
  { name: 'AZURE_MYSQL_PORT', value: '3306' }
  { name: 'AZURE_MYSQL_ADMIN_USER', value: mysqlAdminUsername }
  { name: 'AZURE_MYSQL_ADMIN_PASSWORD', secretRef: 'mysql-password' }
]

module monolith 'modules/container-app.bicep' = {
  name: 'monolith'
  params: {
    location: location
    name: 'monolith'
    environmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    acrUsername: acr.outputs.registryName
    acrPassword: listCredentials(resourceId('Microsoft.ContainerRegistry/registries', acrName), '2023-11-01-preview').passwords[0].value
    mysqlAdminPassword: mysqlAdminPassword
    imageName: 'monolith'
    imageTag: imageTag
    targetPort: 6000
    minReplicas: minReplicas
    envVars: commonEnv
  }
}

module bff 'modules/container-app.bicep' = {
  name: 'bff'
  params: {
    location: location
    name: 'bff'
    environmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: acr.outputs.loginServer
    acrUsername: acr.outputs.registryName
    acrPassword: listCredentials(resourceId('Microsoft.ContainerRegistry/registries', acrName), '2023-11-01-preview').passwords[0].value
    mysqlAdminPassword: mysqlAdminPassword
    imageName: 'bff'
    imageTag: imageTag
    targetPort: 8000
    // Pinned to exactly 1 replica (not the shared minReplicas/maxReplicas=3
    // default every other Container App gets) — the live migration's state
    // lives in an in-process singleton (see migration_engine.py), so two
    // replicas would each run their own independent copy of it. Caught for
    // real: letting bff scale out produced a migration status with an
    // impossible mix of "done" and "pending" steps as traffic
    // load-balanced between two replicas with different in-memory state.
    minReplicas: 1
    maxReplicas: 1
    enableSystemIdentity: true
    envVars: concat(commonEnv, [
      { name: 'MONOLITH_BASE_URL', value: 'https://${monolith.outputs.fqdn}' }
      { name: 'FRONTEND_ORIGIN', value: 'https://${staticWebApp.outputs.defaultHostname}' }
      { name: 'AZURE_RESOURCE_GROUP', value: resourceGroup().name }
      { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
      { name: 'AZURE_LOCATION', value: location }
      { name: 'AZURE_CONTAINER_APPS_ENV_ID', value: containerAppsEnv.outputs.environmentId }
      { name: 'AZURE_CONTAINER_APPS_DEFAULT_DOMAIN', value: containerAppsEnv.outputs.defaultDomain }
      { name: 'AZURE_ACR_LOGIN_SERVER', value: acr.outputs.loginServer }
      { name: 'AZURE_ACR_NAME', value: acr.outputs.registryName }
      { name: 'AZURE_ACR_PASSWORD', secretRef: 'acr-password' }
    ])
  }
}

output acrLoginServer string = acr.outputs.loginServer
output acrName string = acr.outputs.registryName
output mysqlFqdn string = mysql.outputs.fqdn
output containerAppsEnvId string = containerAppsEnv.outputs.environmentId
output containerAppsDefaultDomain string = containerAppsEnv.outputs.defaultDomain
output staticWebAppHostname string = staticWebApp.outputs.defaultHostname
output monolithFqdn string = monolith.outputs.fqdn
output bffFqdn string = bff.outputs.fqdn
output bffPrincipalId string = bff.outputs.principalId
