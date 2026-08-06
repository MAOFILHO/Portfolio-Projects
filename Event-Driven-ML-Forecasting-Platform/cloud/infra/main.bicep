// ============================================================
// Event-Driven-ML-Forecasting-Platform — cloud demo deployment
//
// Subscription-scoped: creates its own resource group, then everything the
// single-VM stack needs. Deliberately NOT the multi-module pattern used by
// Azure-Agentic-Video-Surveillance/infra/main.bicep -- that project fans out
// to 8+ PaaS services; this one is one VM plus the network plumbing it
// needs, so a single file is more legible than module indirection would be.
//
// Naming: `resourceGroupName` and `namePrefix` are pre-resolved by the
// deploy CLI's naming.py (incremental-suffix collision handling) *before*
// this template runs -- this template just uses whatever names it's given,
// it doesn't compute uniqueness itself.
// ============================================================

targetScope = 'subscription'

@description('Pre-resolved resource group name (collision-checked by the deploy CLI before this runs)')
param resourceGroupName string

@description('Pre-resolved short name prefix for all resources in this deploy, e.g. "forecast" or "forecast-2"')
param namePrefix string

@description('Azure region for all resources')
param location string = 'eastus'

@description('SSH public key content for the VM admin user (password auth is disabled)')
param sshPublicKey string

@description('VM admin username')
param adminUsername string = 'azureuser'

@allowed(['Standard_D4s_v5', 'Standard_D2s_v5', 'Standard_D4s_v3'])
@description('VM size -- non-burstable so Airflow train_arima\'s sustained CPU load isn\'t throttled by burst credits. Defaults to D4s_v3 (same 4 vCPU/16GB shape as D4s_v5, older CPU generation) because this subscription had 0 quota for every v5-generation D-family SKU at the time this was written, while v3/v4-generation families already had headroom -- see deploy/src/forecast_deploy/config.py. Switch back to D4s_v5 once a v5 quota increase is granted; D2s_v5 (2 vCPU/8GB) remains available as a smaller Spot fallback, see docker-compose.cloud.yml\'s AIRFLOW__CORE__PARALLELISM note for the safety tradeoff at that size.')
param vmSize string = 'Standard_D4s_v3'

@allowed(['Regular', 'Spot'])
@description('Regular by default -- Spot draws from a separate, often-constrained quota pool with its own regional capacity limits, independent of the quota itself.')
param vmPriority string = 'Regular'

@description('OS disk size in GB -- room for the ~7GB Airflow image + backend image + build cache')
param osDiskSizeGb int = 64

// Tag every resource so the post-teardown smoke test can verify nothing
// tagged for this project is left behind at the subscription scope.
var tags = {
  project: 'forecasting-platform'
  managedBy: 'forecast-deploy'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module network 'modules/network.bicep' = {
  name: 'network'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalytics'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
  }
}

module vm 'modules/vm.bicep' = {
  name: 'vm'
  scope: rg
  params: {
    location: location
    namePrefix: namePrefix
    tags: tags
    subnetId: network.outputs.subnetId
    publicIpId: network.outputs.publicIpId
    nsgId: network.outputs.nsgId
    sshPublicKey: sshPublicKey
    adminUsername: adminUsername
    vmSize: vmSize
    vmPriority: vmPriority
    osDiskSizeGb: osDiskSizeGb
    // Bicep loads the script at compile time and substitutes the one
    // placeholder it has (__PUBLIC_IP__) with the address the network
    // module already resolved -- see bootstrap.sh's header comment for why
    // this replaced an earlier IMDS self-discovery approach.
    customData: base64(replace(loadTextContent('../cloud-init/bootstrap.sh'), '__PUBLIC_IP__', network.outputs.publicIpAddress))
  }
}

output resourceGroupName string = rg.name
output vmName string = vm.outputs.vmName
output publicIpAddress string = network.outputs.publicIpAddress
output logAnalyticsWorkspaceName string = logAnalytics.outputs.workspaceName
