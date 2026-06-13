#!/bin/bash
set -e

echo "Production Hardening..."

RESOURCE_GROUP="rg-guardian-ai-prod"
KV_NAME="guardian-kv-prod"

az security pricing create \
  --name VirtualMachines \
  --tier Standard

az keyvault create \
  --name $KV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location eastus

echo "Store secrets in Key Vault:"
echo "az keyvault secret set --vault-name $KV_NAME --name ServiceBusConnection --value '<YOUR_CONNECTION>'"

kubectl create secret generic azure-secrets \
  --from-literal=storage-connection=$BLOB_STORAGE_CONN \
  --from-literal=servicebus-connection=$SERVICE_BUS_CONN \
  --namespace production

echo "Production hardening complete!"
