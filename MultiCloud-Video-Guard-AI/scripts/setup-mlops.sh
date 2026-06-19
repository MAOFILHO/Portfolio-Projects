#!/bin/bash
set -e

echo "Setting up MLOps Platform..."

RESOURCE_GROUP="rg-guardian-ai-prod"
WORKSPACE_NAME="guardian-ai-ml-workspace-prod"
LOCATION="eastus"

az ml workspace create \
  --name $WORKSPACE_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

az monitor app-insights component create \
  --app guardian-ai-insights \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --application-type web

echo "MLOps platform created successfully!"
