#!/bin/bash
set -e

echo "Setting up AKS Cluster..."

RESOURCE_GROUP="rg-guardian-ai-prod"
CLUSTER_NAME="aks-guardian-prod"

az aks create \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-managed-identity \
  --generate-ssh-keys \
  --network-plugin azure

az aks nodepool add \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $CLUSTER_NAME \
  --name gpupool \
  --node-count 0 \
  --min-count 0 \
  --max-count 5 \
  --enable-cluster-autoscaler \
  --node-vm-size Standard_NC6s_v3 \
  --node-taints sku=gpu:NoSchedule

az aks get-credentials \
  --resource-group $RESOURCE_GROUP \
  --name $CLUSTER_NAME \
  --overwrite-existing

helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm install keda kedacore/keda --namespace keda --create-namespace

echo "✅ AKS cluster created successfully!"
