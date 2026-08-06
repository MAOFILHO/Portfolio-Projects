// Spot-priced VM running the whole stack via cloud-init (customData) --
// see cloud-init/bootstrap.sh. Password auth is disabled; SSH key only.
param location string
param namePrefix string
param tags object
param subnetId string
param publicIpId string
param nsgId string
param sshPublicKey string
param adminUsername string
param vmSize string
param osDiskSizeGb int
param customData string

@allowed(['Regular', 'Spot'])
@description('Regular by default: Spot pricing is cheaper but draws from a separate, often-constrained per-subscription quota pool and can hit transient regional capacity shortages independent of that quota. Set to Spot explicitly once quota/capacity is confirmed available.')
param vmPriority string = 'Regular'

resource nic 'Microsoft.Network/networkInterfaces@2023-11-01' = {
  name: 'nic-${namePrefix}'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: subnetId
          }
          publicIPAddress: {
            id: publicIpId
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
    networkSecurityGroup: {
      id: nsgId
    }
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = {
  name: 'vm-${namePrefix}'
  location: location
  tags: tags
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    // Spot pricing (when vmPriority == 'Spot') is cheap and per-second
    // billed but draws from a separate, often-constrained quota pool with
    // its own regional capacity limits -- Deallocate (not Delete) on
    // eviction so a `forecast-deploy` rerun can restart the same VM rather
    // than needing a full reprovision if Azure reclaims the capacity
    // mid-demo. Regular priority skips both properties entirely --
    // conditional object below since Bicep errors if priority/eviction/
    // billing keys are present at all on a Regular VM, not just if they're
    // empty.
    priority: vmPriority
    evictionPolicy: vmPriority == 'Spot' ? 'Deallocate' : null
    billingProfile: vmPriority == 'Spot' ? {
      maxPrice: -1
    } : null
    osProfile: {
      computerName: 'forecast-vm'
      adminUsername: adminUsername
      customData: customData
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: osDiskSizeGb
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
}

output vmName string = vm.name
