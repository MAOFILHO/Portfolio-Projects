// ============================================================
// Azure Communication Services — email alerting (Azure-managed domain, free
// to provision; cost is per-email/per-SMS send only). SMS requires a phone
// number purchased separately (not automated here — see docs/deployment.md);
// the ACS resource + connection string are provisioned regardless so SMS can
// be enabled later without redeploying infra.
// ============================================================

@description('Name for the Email Communication Service (manages the Azure-managed sender domain)')
param emailServiceName string

@description('Name for the Communication Services resource')
param communicationServiceName string

@description('Data location for Communication Services (not all Azure regions support ACS directly; "United States" is the safe default for eastus/eastus2 deployments)')
param dataLocation string = 'United States'

resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: emailServiceName
  location: 'global'
  properties: {
    dataLocation: dataLocation
  }
}

resource azureManagedDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  properties: {
    domainManagement: 'AzureManaged'
  }
}

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: communicationServiceName
  location: 'global'
  properties: {
    dataLocation: dataLocation
    linkedDomains: [
      azureManagedDomain.id
    ]
  }
}

@description('Communication Services resource ID')
output id string = communicationService.id

@description('Communication Services name')
output name string = communicationService.name

// mailFromSenderDomain is just the domain (e.g. "<guid>.azurecomm.net"), not
// a full address -- confirmed the hard way when the ACS email API rejected
// it outright: "Request body validation error. See property 'senderAddress'".
// Azure-managed domains always use "DoNotReply" as the (non-customizable)
// sender username, so prefix it to get an address the API actually accepts.
@description('Default Azure-managed sender email address (MailFrom on AzureManagedDomain)')
output senderEmail string = 'DoNotReply@${azureManagedDomain.properties.mailFromSenderDomain}'

// Consumed directly as a Container App / Function secretRef by the deploy pipeline; never written to disk or logs.
#disable-next-line outputs-should-not-contain-secrets
@description('Primary connection string for the Communication Services resource')
output connectionString string = communicationService.listKeys().primaryConnectionString
