#!/bin/bash
set -e

echo "Setting up Azure Resources..."

RESOURCE_GROUP="rg-guardian-ai-prod"
LOCATION="eastus"
ACR_NAME="guardianacr"

az group create --name $RESOURCE_GROUP --location $LOCATION

az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Standard

echo "Azure resources created successfully!"
