#!/bin/bash
# Update all Kubernetes manifests to use the ACR name from your environment.
# Run after: az acr create ... and export ACR_NAME=your-acr-name
#
# Usage:
#   export ACR_NAME=guardianacr44724
#   ./scripts/update-acr-in-manifests.sh
# Or one-liner: ACR_NAME=guardianacr44724 ./scripts/update-acr-in-manifests.sh

set -e

if [ -z "${ACR_NAME}" ]; then
  echo "ERROR: ACR_NAME is not set."
  echo "Usage: export ACR_NAME=your-acr-name   # e.g. the name from 'az acr create --name \$ACR_NAME ...'"
  echo "       ./scripts/update-acr-in-manifests.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"

if [ ! -d "$K8S_DIR" ]; then
  echo "ERROR: k8s directory not found at $K8S_DIR"
  exit 1
fi

# Replace ACR_PLACEHOLDER with actual ACR name in all YAML files
# Works on both macOS (sed -i '') and Linux (sed -i)
case "$(uname -s)" in
  Darwin)
    find "$K8S_DIR" -name '*.yaml' -exec sed -i '' "s/ACR_PLACEHOLDER/$ACR_NAME/g" {} \;
    ;;
  *)
    find "$K8S_DIR" -name '*.yaml' -exec sed -i "s/ACR_PLACEHOLDER/$ACR_NAME/g" {} \;
    ;;
esac

echo "✅ Updated all manifests in k8s/ to use ACR: $ACR_NAME.azurecr.io"
