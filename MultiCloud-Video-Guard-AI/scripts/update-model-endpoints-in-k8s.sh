#!/bin/bash
set -e

# Script to update Kubernetes ConfigMap with Azure ML endpoint URLs
# Usage: ./scripts/update-model-endpoints-in-k8s.sh

echo "🔍 Getting Azure ML endpoint information..."

# Get environment variables (or set defaults)
RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-"guardian-ai-prod"}
WORKSPACE_NAME=${AZURE_ML_WORKSPACE:-"guardian-ml-workspace-prod"}

# Get NSFW endpoint
NSFW_ENDPOINT=$(az ml online-endpoint show \
  --name nsfw-detector-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query scoring_uri -o tsv 2>/dev/null || echo "")

# Get Violence endpoint
VIOLENCE_ENDPOINT=$(az ml online-endpoint show \
  --name violence-detector-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query scoring_uri -o tsv 2>/dev/null || echo "")

# Get endpoint key (same for both endpoints)
ENDPOINT_KEY=$(az ml online-endpoint get-credentials \
  --name nsfw-detector-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query primaryKey -o tsv 2>/dev/null || echo "")

if [ -z "$NSFW_ENDPOINT" ] || [ -z "$VIOLENCE_ENDPOINT" ]; then
  echo "❌ Could not retrieve endpoint information"
  echo "   Make sure endpoints are deployed and accessible"
  exit 1
fi

echo "✅ Found endpoints:"
echo "   NSFW: $NSFW_ENDPOINT"
echo "   Violence: $VIOLENCE_ENDPOINT"

echo "📝 Updating ConfigMap..."
# Merge with existing ConfigMap (preserve other values)
kubectl get configmap guardian-config -n production -o yaml > /tmp/configmap-backup.yaml || true

kubectl create configmap guardian-config \
  --from-literal=NSFW_MODEL_ENDPOINT="$NSFW_ENDPOINT" \
  --from-literal=VIOLENCE_MODEL_ENDPOINT="$VIOLENCE_ENDPOINT" \
  --from-literal=MODEL_ENDPOINT_KEY="$ENDPOINT_KEY" \
  --dry-run=client -o yaml | \
  kubectl apply -f - -n production

echo "🔄 Restarting deep-vision pods..."
kubectl rollout restart deployment/deep-vision -n production

echo "⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/deep-vision -n production --timeout=5m

echo "✅ ConfigMap updated and pods restarted!"
echo ""
echo "📊 Verify endpoints are being used:"
echo "   kubectl logs -l app=deep-vision -n production --tail=50 | grep -i 'model endpoint'"
