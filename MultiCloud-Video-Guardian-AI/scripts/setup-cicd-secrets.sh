#!/bin/bash
set -e

echo "Setting up CI/CD Secrets..."

echo "Add these secrets to GitHub repository settings:"
echo ""
echo "ACR_USERNAME: Get from Azure Portal"
echo "ACR_PASSWORD: Get from Azure Portal"
echo ""
echo "AZURE_CREDENTIALS: Run this command:"
echo "az ad sp create-for-rbac --name guardian-ai-sp --role contributor --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-guardian-ai-prod --sdk-auth"
echo ""
echo "Copy the JSON output to GitHub Secrets as AZURE_CREDENTIALS"

echo "Instructions displayed!"
