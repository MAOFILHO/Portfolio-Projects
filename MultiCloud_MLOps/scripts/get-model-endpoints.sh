#!/bin/bash
set -e

# Helper script to get Azure ML model endpoints after deployment
# Usage: ./scripts/get-model-endpoints.sh [model-name]
# Example: ./scripts/get-model-endpoints.sh nsfw-detector

MODEL_NAME=${1:-"nsfw-detector"}
ENDPOINT_NAME="${MODEL_NAME}-endpoint"

echo "🔍 Getting endpoint information for ${MODEL_NAME}..."

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install it first."
    exit 1
fi

# Get environment variables
RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-"guardian-ai-prod"}
WORKSPACE_NAME=${AZURE_ML_WORKSPACE:-"guardian-ml-workspace-prod"}

# Get endpoint details
SCORING_URI=$(az ml online-endpoint show \
    --name "${ENDPOINT_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --workspace-name "${WORKSPACE_NAME}" \
    --query scoring_uri -o tsv 2>/dev/null || echo "")

if [ -z "$SCORING_URI" ]; then
    echo "❌ Endpoint '${ENDPOINT_NAME}' not found."
    echo "   Make sure you've deployed the model first using:"
    echo "   python mlops/deployment/deploy_model.py"
    exit 1
fi

ENDPOINT_KEY=$(az ml online-endpoint get-credentials \
    --name "${ENDPOINT_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --workspace-name "${WORKSPACE_NAME}" \
    --query primaryKey -o tsv 2>/dev/null || echo "")

echo "✅ Endpoint Information:"
echo "━━━━━━━━━━━━━━━━━━━━━━━"
echo "Scoring URI: ${SCORING_URI}"
echo "Endpoint Key: ${ENDPOINT_KEY}"
echo ""
echo "📝 To update your ConfigMap or .env file, use these values:"
echo ""
echo "For Kubernetes ConfigMap:"
if [[ "$MODEL_NAME" == "nsfw-detector" ]]; then
  echo "  NSFW_MODEL_ENDPOINT: \"${SCORING_URI}\""
else
  echo "  VIOLENCE_MODEL_ENDPOINT: \"${SCORING_URI}\""
fi
echo "  MODEL_ENDPOINT_KEY: \"${ENDPOINT_KEY}\""
echo ""
echo "For docker-compose.yml or .env:"
if [[ "$MODEL_NAME" == "nsfw-detector" ]]; then
  echo "  NSFW_MODEL_ENDPOINT=${SCORING_URI}"
else
  echo "  VIOLENCE_MODEL_ENDPOINT=${SCORING_URI}"
fi
echo "  MODEL_ENDPOINT_KEY=${ENDPOINT_KEY}"