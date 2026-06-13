#!/bin/bash
set -e

echo "Building all services (linux/amd64 for AKS)..."

ACR_NAME="guardianacr.azurecr.io"

az acr login --name guardianacr
docker buildx create --name guardian-builder --use || docker buildx use guardian-builder

services=("ingestion" "fast-screening" "deep-vision" "policy-engine" "human-review" "notification")

for service in "${services[@]}"; do
    echo "Building $service..."
    docker buildx build --platform linux/amd64 -t $ACR_NAME/$service:latest --push ./services/$service
done

echo "All services built and pushed!"
