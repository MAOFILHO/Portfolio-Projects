# Guardian AI - Complete End-to-End Deployment Guide

**🎯 Goal**: Deploy the complete MLOps system to AWS + Azure cloud infrastructure
**⏱️ Time**: 4-6 hours (first-time deployment)

---

## Overview

This guide walks you through deploying the complete Guardian AI MLOps platform from scratch, including:
- AWS infrastructure (S3, SQS, DynamoDB)
- Azure infrastructure (AKS, ACR, Azure ML)
- All 6 microservices
- Kubernetes deployment
- Monitoring setup
- End-to-end testing

---

## 📋 Platform Notes

**Important for Windows Users:**

- **Default Commands**: All commands shown are for **Linux/macOS (bash)** by default
- **Windows Options**:
  - **Git Bash** (Recommended) - Runs bash commands directly, minimal changes needed
  - **WSL2** (Windows Subsystem for Linux) - Full Linux environment, best compatibility
  - **PowerShell** - See PowerShell alternatives provided for key sections below
- **PowerShell Alternatives**: Provided for critical setup steps (environment variables, AWS/Azure config, file operations)
- **Bash Scripts**: Scripts like `setup-aws.sh` require Git Bash or WSL2 on Windows

**Command Mapping Reference:**

| Operation | Linux/macOS (bash) | Windows (PowerShell) |
|-----------|-------------------|---------------------|
| Set environment variable | `export VAR=value` | `$env:VAR = "value"` |
| Get environment variable | `echo $VAR` | `Write-Host $env:VAR` |
| Command substitution | `$(command)` | `$(command)` |
| String substring | `cut -c1-8` | `$var.Substring(0,8)` |
| Timestamp | `date +%s` | `[DateTimeOffset]::Now.ToUnixTimeSeconds()` |
| Python venv activate | `source venv/bin/activate` | `.\venv\Scripts\Activate.ps1` |
| Create file with content | `cat > file <<EOF` | `@'...'@ | Out-File file` |
| Home directory | `~/Projects` | `$env:USERPROFILE\Projects` |
| Run bash script | `bash script.sh` | `bash script.sh` (Git Bash) or `wsl bash script.sh` |

---

## Prerequisites

### Required Tools

**All Platforms - Verify Installations:**
```bash
# These commands work on Linux, macOS, Windows PowerShell, and Git Bash
docker --version          # Docker Desktop 24+
kubectl version --client  # kubectl 1.28+
python --version          # Python 3.11+ (use 'python' on Windows, 'python3' on Linux/macOS)
aws --version            # AWS CLI 2.13+
az --version             # Azure CLI 2.50+
helm version             # Helm 3.12+
node --version           # Node.js 20+ (for frontend)
```

**Installation Instructions:**

**Linux/macOS:**
```bash
# macOS (using Homebrew)
brew install kubectl python@3.11 awscli azure-cli helm node

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y kubectl python3.11 python3-pip awscli azure-cli helm nodejs npm

# Linux (RHEL/CentOS)
sudo yum install -y kubectl python3.11 python3-pip awscli azure-cli helm nodejs npm
```

**Windows:**
```powershell
# Using Chocolatey (recommended)
choco install docker-desktop kubectl python311 awscli azure-cli kubernetes-helm nodejs

# Or using winget
winget install Docker.DockerDesktop
winget install Kubernetes.kubectl
winget install Python.Python.3.11
winget install Amazon.AWSCLI
winget install Microsoft.AzureCLI
winget install Kubernetes.Helm
winget install OpenJS.NodeJS

# Install Git Bash (recommended for Windows users)
winget install Git.Git
```

### Required Accounts
- **AWS account** with AdministratorAccess
- **Azure subscription** with Owner/Contributor access
- **GitHub account** (for version control and CI/CD)

---

## Phase 1: Project Setup & Initialization (30 minutes)

### Step 1.1: Clone/Initialize Project

**Linux/macOS (bash):**
```bash
# Navigate to project directory
cd ~/Projects/MLOps_Project

# Initialize git (if not already done)
git init

# Verify project structure
ls -la services/
ls -la k8s/
ls -la scripts/

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install common dependencies
pip install fastapi uvicorn python-multipart boto3 botocore redis httpx openai
```

**Windows (PowerShell):**
```powershell
# Navigate to project directory
cd $env:USERPROFILE\Projects\MLOps_Project

# Initialize git (if not already done)
git init

# Verify project structure
Get-ChildItem services\
Get-ChildItem k8s\
Get-ChildItem scripts\

# Create Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install common dependencies
pip install fastapi uvicorn python-multipart boto3 botocore redis httpx openai
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
cd ~/Projects/MLOps_Project
git init
ls -la services/
python -m venv venv
source venv/Scripts/activate  # Note: Scripts (capital S) on Windows
pip install fastapi uvicorn python-multipart boto3 botocore redis httpx openai
```

### Step 1.2: Verify Project Structure

**Linux/macOS (bash):**
```bash
# Ensure all required directories exist
mkdir -p services/{ingestion,fast-screening,deep-vision,policy-engine,human-review,notification}
mkdir -p k8s/{cpu-services,gpu-services,frontend}
mkdir -p scripts
mkdir -p mlops/{training,deployment}
mkdir -p tests/load
mkdir -p infrastructure

echo "✅ Project structure verified"
```

**Windows (PowerShell):**
```powershell
# Ensure all required directories exist
New-Item -ItemType Directory -Force -Path services\ingestion,services\fast-screening,services\deep-vision,services\policy-engine,services\human-review,services\notification
New-Item -ItemType Directory -Force -Path k8s\cpu-services,k8s\gpu-services,k8s\frontend
New-Item -ItemType Directory -Force -Path scripts,mlops\training,mlops\deployment,tests\load,infrastructure

Write-Host "✅ Project structure verified"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
mkdir -p services/{ingestion,fast-screening,deep-vision,policy-engine,human-review,notification}
mkdir -p k8s/{cpu-services,gpu-services,frontend}
mkdir -p scripts mlops/{training,deployment} tests/load infrastructure
```

---

## Phase 2: AWS Infrastructure Setup (30 minutes)

### Step 2.1: Configure AWS Credentials

**Linux/macOS (bash):**
```bash
# Configure AWS CLI
aws configure
# Enter: AWS Access Key ID
# Enter: AWS Secret Access Key
# Enter: Default region (ap-south-1 recommended for cost)
# Enter: Default output format (json)

# Verify configuration
aws sts get-caller-identity
aws configure get region

# Export for scripts
export AWS_REGION=$(aws configure get region)
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
```

**Windows (PowerShell):**
```powershell
# Configure AWS CLI
aws configure
# Enter: AWS Access Key ID
# Enter: AWS Secret Access Key
# Enter: Default region (ap-south-1 recommended for cost)
# Enter: Default output format (json)

# Verify configuration
aws sts get-caller-identity
aws configure get region

# Set environment variables for scripts
$env:AWS_REGION = aws configure get region
$env:AWS_ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)

Write-Host "AWS Account ID: $env:AWS_ACCOUNT_ID"
Write-Host "AWS Region: $env:AWS_REGION"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
aws configure
aws sts get-caller-identity
export AWS_REGION=$(aws configure get region)
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

### Step 2.2: Create AWS Resources (Simplified Architecture)

**Linux/macOS (bash):**
```bash
# Run AWS setup script (creates 1 S3 bucket, 2 SQS queues, 2 DynamoDB tables)
bash scripts/setup-aws.sh

# This creates:
# ✅ S3 bucket: guardian-videos-xxxxxxxx (primary video storage)
# ✅ SQS queue: guardian-video-processing (main processing queue)
# ✅ SQS queue: guardian-gpu-processing (GPU autoscaling queue)
# ✅ DynamoDB table: guardian-videos (single source of truth)
# ✅ DynamoDB table: guardian-events (audit log with TTL)

# Save the bucket name from output
export S3_BUCKET_NAME="guardian-videos-$(echo $AWS_ACCOUNT_ID | cut -c1-8)"

echo "✅ AWS resources created"
```

**Windows (PowerShell):**
```powershell
# Run AWS setup script (requires Git Bash or WSL for bash scripts)
# Option 1: Use Git Bash (recommended)
bash scripts/setup-aws.sh

# Option 2: Use WSL
wsl bash scripts/setup-aws.sh

# Save the bucket name (PowerShell syntax)
$accountIdPrefix = $env:AWS_ACCOUNT_ID.Substring(0, 8)
$env:S3_BUCKET_NAME = "guardian-videos-$accountIdPrefix"

Write-Host "✅ AWS resources created"
Write-Host "S3 Bucket: $env:S3_BUCKET_NAME"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
bash scripts/setup-aws.sh
export S3_BUCKET_NAME="guardian-videos-$(echo $AWS_ACCOUNT_ID | cut -c1-8)"
```

### Step 2.3: Get AWS Resource URLs

**Linux/macOS (bash):**
```bash
# Get SQS queue URLs
export SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-video-processing --query 'QueueUrl' --output text)
export SQS_GPU_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-gpu-processing --query 'QueueUrl' --output text)

# Verify resources exist
echo "S3 Bucket: $S3_BUCKET_NAME"
echo "SQS Main Queue: $SQS_QUEUE_URL"
echo "SQS GPU Queue: $SQS_GPU_QUEUE_URL"

# Test S3 access
aws s3 ls s3://$S3_BUCKET_NAME

# Test DynamoDB access
aws dynamodb describe-table --table-name guardian-videos --query 'Table.TableName'
aws dynamodb describe-table --table-name guardian-events --query 'Table.TableName'

echo "✅ AWS resources verified"
```

**Windows (PowerShell):**
```powershell
# Get SQS queue URLs
$env:SQS_QUEUE_URL = aws sqs get-queue-url --queue-name guardian-video-processing --query 'QueueUrl' --output text
$env:SQS_GPU_QUEUE_URL = aws sqs get-queue-url --queue-name guardian-gpu-processing --query 'QueueUrl' --output text

# Verify resources exist
Write-Host "S3 Bucket: $env:S3_BUCKET_NAME"
Write-Host "SQS Main Queue: $env:SQS_QUEUE_URL"
Write-Host "SQS GPU Queue: $env:SQS_GPU_QUEUE_URL"

# Test S3 access
aws s3 ls "s3://$env:S3_BUCKET_NAME"

# Test DynamoDB access
aws dynamodb describe-table --table-name guardian-videos --query 'Table.TableName'
aws dynamodb describe-table --table-name guardian-events --query 'Table.TableName'

Write-Host "✅ AWS resources verified"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
export SQS_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-video-processing --query 'QueueUrl' --output text)
export SQS_GPU_QUEUE_URL=$(aws sqs get-queue-url --queue-name guardian-gpu-processing --query 'QueueUrl' --output text)
```

### Step 2.4: Create .env File for Local Testing

**Linux/macOS (bash):**
```bash
cat > .env <<EOF
# AWS Configuration (Required)
AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)
AWS_REGION=$AWS_REGION
S3_BUCKET_NAME=$S3_BUCKET_NAME
SQS_QUEUE_URL=$SQS_QUEUE_URL
SQS_GPU_QUEUE_URL=$SQS_GPU_QUEUE_URL

# DynamoDB Tables
DYNAMODB_VIDEOS_TABLE=guardian-videos
DYNAMODB_EVENTS_TABLE=guardian-events

# Policy Engine Configuration
AUTO_APPROVE_THRESHOLD=0.2
AUTO_REJECT_THRESHOLD=0.8

# Azure OpenAI (Optional - Configure in Phase 4 if needed)
AZURE_OPENAI_ENABLED=false
# AZURE_OPENAI_API_KEY=
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_ENDPOINT=
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
EOF

echo "✅ .env file created"
```

**Windows (PowerShell):**
```powershell
# Create .env file using PowerShell here-string
$envContent = @"
# AWS Configuration (Required)
AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)
AWS_REGION=$env:AWS_REGION
S3_BUCKET_NAME=$env:S3_BUCKET_NAME
SQS_QUEUE_URL=$env:SQS_QUEUE_URL
SQS_GPU_QUEUE_URL=$env:SQS_GPU_QUEUE_URL

# DynamoDB Tables
DYNAMODB_VIDEOS_TABLE=guardian-videos
DYNAMODB_EVENTS_TABLE=guardian-events

# Policy Engine Configuration
AUTO_APPROVE_THRESHOLD=0.2
AUTO_REJECT_THRESHOLD=0.8

# Azure OpenAI (Optional - Configure in Phase 4 if needed)
AZURE_OPENAI_ENABLED=false
# AZURE_OPENAI_API_KEY=
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_ENDPOINT=
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
"@

$envContent | Out-File -FilePath .env -Encoding utf8

Write-Host "✅ .env file created"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
cat > .env <<EOF
# AWS Configuration (Required)
AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)
AWS_REGION=$AWS_REGION
S3_BUCKET_NAME=$S3_BUCKET_NAME
SQS_QUEUE_URL=$SQS_QUEUE_URL
SQS_GPU_QUEUE_URL=$SQS_GPU_QUEUE_URL

# DynamoDB Tables
DYNAMODB_VIDEOS_TABLE=guardian-videos
DYNAMODB_EVENTS_TABLE=guardian-events

# Policy Engine Configuration
AUTO_APPROVE_THRESHOLD=0.2
AUTO_REJECT_THRESHOLD=0.8

# Azure OpenAI (Optional - Configure in Phase 4 if needed)
AZURE_OPENAI_ENABLED=false
# AZURE_OPENAI_API_KEY=
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_ENDPOINT=
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
EOF
```

---

## Phase 3: Azure Infrastructure Setup (45 minutes)

### Step 3.1: Login to Azure

**Linux/macOS (bash):**
```bash
# Login to Azure
az login

# List subscriptions
az account list --output table

# Set active subscription
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify
az account show --output table

# Set variables
export RESOURCE_GROUP="guardian-ai-prod"
export LOCATION="eastus"  # or swedencentral, westeurope
export ACR_NAME="guardianacr$(date +%s | cut -c 6-10)"
export AKS_CLUSTER="guardian-ai-aks"

echo "Azure Subscription: $(az account show --query name -o tsv)"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "ACR Name: $ACR_NAME"
echo "AKS Cluster: $AKS_CLUSTER"
```

**Windows (PowerShell):**
```powershell
# Login to Azure
az login

# List subscriptions
az account list --output table

# Set active subscription
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify
az account show --output table

# Set variables
$env:RESOURCE_GROUP = "guardian-ai-prod"
$env:LOCATION = "eastus"  # or swedencentral, westeurope
$timestamp = [DateTimeOffset]::Now.ToUnixTimeSeconds()
$env:ACR_NAME = "guardianacr$($timestamp.ToString().Substring(5, 5))"
$env:AKS_CLUSTER = "guardian-ai-aks"

Write-Host "Azure Subscription: $(az account show --query name -o tsv)"
Write-Host "Resource Group: $env:RESOURCE_GROUP"
Write-Host "Location: $env:LOCATION"
Write-Host "ACR Name: $env:ACR_NAME"
Write-Host "AKS Cluster: $env:AKS_CLUSTER"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"
export RESOURCE_GROUP="guardian-ai-prod"
export LOCATION="eastus"
export ACR_NAME="guardianacr$(date +%s | cut -c 6-10)"
export AKS_CLUSTER="guardian-ai-aks"
```

### Step 3.2: Create Azure Resource Group

**Linux/macOS (bash):**
```bash
# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# Verify
az group show --name $RESOURCE_GROUP --output table

echo "✅ Resource group created"
```

**Windows (PowerShell):**
```powershell
# Create resource group
az group create `
  --name $env:RESOURCE_GROUP `
  --location $env:LOCATION

# Verify
az group show --name $env:RESOURCE_GROUP --output table

Write-Host "✅ Resource group created"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
az group create --name $RESOURCE_GROUP --location $LOCATION
az group show --name $RESOURCE_GROUP --output table
```

### Step 3.3: Create Azure Container Registry (ACR)

**Linux/macOS (bash):**
```bash
# Create ACR
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Standard \
  --location $LOCATION

# Enable admin access (for easier local testing)
az acr update --name $ACR_NAME --admin-enabled true

# Get ACR credentials
export ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
export ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query 'passwords[0].value' -o tsv)
export ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)

echo "ACR Login Server: $ACR_LOGIN_SERVER"
echo "ACR Username: $ACR_USERNAME"

# Login to ACR
az acr login --name $ACR_NAME

# Update all Kubernetes manifests to use this ACR (single source of truth)
# Manifests use ACR_PLACEHOLDER; this replaces it with your $ACR_NAME
./scripts/update-acr-in-manifests.sh

echo "✅ ACR created and logged in"
```

**Windows (PowerShell):**
```powershell
# Create ACR
az acr create `
  --resource-group $env:RESOURCE_GROUP `
  --name $env:ACR_NAME `
  --sku Standard `
  --location $env:LOCATION

# Enable admin access (for easier local testing)
az acr update --name $env:ACR_NAME --admin-enabled true

# Get ACR credentials
$env:ACR_USERNAME = az acr credential show --name $env:ACR_NAME --query username -o tsv
$env:ACR_PASSWORD = az acr credential show --name $env:ACR_NAME --query 'passwords[0].value' -o tsv
$env:ACR_LOGIN_SERVER = az acr show --name $env:ACR_NAME --query loginServer -o tsv

Write-Host "ACR Login Server: $env:ACR_LOGIN_SERVER"
Write-Host "ACR Username: $env:ACR_USERNAME"

# Login to ACR
az acr login --name $env:ACR_NAME

# Update all Kubernetes manifests to use this ACR (requires Git Bash or WSL for bash script)
bash scripts/update-acr-in-manifests.sh

Write-Host "✅ ACR created and logged in"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Standard --location $LOCATION
az acr update --name $ACR_NAME --admin-enabled true
export ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
export ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query 'passwords[0].value' -o tsv)
export ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
az acr login --name $ACR_NAME
./scripts/update-acr-in-manifests.sh
```

### Step 3.4: Create AKS Cluster
```bash
# Create AKS cluster (this takes 10-15 minutes)
# Check if AKS cluster already exists
if az aks show --resource-group $RESOURCE_GROUP --name $AKS_CLUSTER >/dev/null 2>&1; then
  echo "AKS cluster already exists, ensuring ACR is attached..."
  
  # Ensure ACR is attached
  if ! az aks check-acr --name $AKS_CLUSTER --resource-group $RESOURCE_GROUP --acr ${ACR_NAME}.azurecr.io >/dev/null 2>&1; then
    az aks update \
      --resource-group $RESOURCE_GROUP \
      --name $AKS_CLUSTER \
      --attach-acr $ACR_NAME
  fi
else
  # Create AKS cluster (this takes 10-15 minutes)
  az aks create \
    --resource-group $RESOURCE_GROUP \
    --name $AKS_CLUSTER \
    --node-count 4 \
    --node-vm-size Standard_D2s_v3 \
    --enable-managed-identity \
    --attach-acr $ACR_NAME \
    --generate-ssh-keys \
    --location $LOCATION \
    --network-plugin azure 
  
  echo "AKS cluster creation in progress (10-15 minutes)..."
  az aks wait --resource-group $RESOURCE_GROUP --name $AKS_CLUSTER --created
fi

# Get AKS credentials
az aks get-credentials \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_CLUSTER \
  --overwrite-existing

# Verify connection
kubectl get nodes

echo "✅ AKS credentials configured"
```

### Step 3.5: Add GPU Node Pool (for Deep Vision Service)
```bash
# Add GPU node pool with scale-to-zero capability
# az aks nodepool add \
#   --resource-group $RESOURCE_GROUP \
#   --cluster-name $AKS_CLUSTER \
#   --name gpupool \
#   --node-count 0 \
#   --min-count 0 \
#   --max-count 3 \
#   --node-vm-size Standard_NC6s_v3 \
#   --enable-cluster-autoscaler \
#   --labels workload=gpu \
#   --node-taints sku=gpu:NoSchedule

# echo "✅ GPU node pool added (scale-to-zero enabled)"
```

### Step 3.6: Install KEDA for GPU Autoscaling
```bash
# Add KEDA Helm repository
# helm repo add kedacore https://kedacore.github.io/charts
# helm repo update

# # Install KEDA
# helm install keda kedacore/keda \
#   --namespace keda \
#   --create-namespace

# # Verify KEDA installation
# kubectl get pods -n keda

# echo "✅ KEDA installed for GPU autoscaling"
```

### Step 3.7: Install NGINX Ingress Controller
```bash
# Add NGINX Ingress Helm repository
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install NGINX Ingress
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.service.externalTrafficPolicy=Local

echo "⏳ Waiting for external IP (2-3 minutes)..."

# Wait for external IP
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=300s

# Get external IP
# Linux/macOS (bash):
export EXTERNAL_IP=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Windows (PowerShell):
# $env:EXTERNAL_IP = kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

echo "✅ NGINX Ingress installed"
echo "External IP: $EXTERNAL_IP"
```

---

## Phase 4: Optional - Azure OpenAI Setup (15 minutes)

### Step 4.1: Create Azure OpenAI Resource (Optional)
```bash
# Skip this section if you don't want Azure OpenAI features
# Azure OpenAI is disabled by default to save costs

# Create Azure OpenAI resource
az cognitiveservices account create \
  --name "guardian-openai-$(date +%s | cut -c 6-10)" \
  --resource-group $RESOURCE_GROUP \
  --kind OpenAI \
  --sku S0 \
  --location eastus \
  --yes

# Get endpoint and key
export AZURE_OPENAI_ENDPOINT=$(az cognitiveservices account show \
  --name "guardian-openai-*" \
  --resource-group $RESOURCE_GROUP \
  --query properties.endpoint -o tsv)

export AZURE_OPENAI_API_KEY=$(az cognitiveservices account keys list \
  --name "guardian-openai-*" \
  --resource-group $RESOURCE_GROUP \
  --query key1 -o tsv)

# Deploy GPT-4o model
az cognitiveservices account deployment create \
  --name "guardian-openai-*" \
  --resource-group $RESOURCE_GROUP \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-05-13" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard

echo "✅ Azure OpenAI configured"
echo "Endpoint: $AZURE_OPENAI_ENDPOINT"

# Update .env file
cat >> .env <<EOF

# Azure OpenAI (Enabled)
AZURE_OPENAI_ENABLED=true
AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
EOF
```

---

## Phase 5: Build and Push Docker Images (30 minutes)

### Step 5.1: Setup Docker Buildx
```bash
# Create buildx builder (for multi-platform builds)
docker buildx create --name guardian-builder --use || docker buildx use guardian-builder

# Verify
docker buildx inspect --bootstrap

echo "✅ Docker buildx configured"
```

### Step 5.2: Build and Push All Service Images
```bash
# Login to ACR
docker login $ACR_LOGIN_SERVER -u $ACR_USERNAME -p $ACR_PASSWORD

# Build and push all services (6 backend + 1 API gateway + 1 frontend = 8 total)
echo "Building and pushing images to ACR..."

# 1. Ingestion Service
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-ingestion:v1 \
  --push ./services/ingestion

# 2. Fast Screening Service
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-fast-screening:v1 \
  --push ./services/fast-screening

# 3. Deep Vision Service (will run on CPU nodes)
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-deep-vision:v1 \
  --push ./services/deep-vision

# 4. Policy Engine Service
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-policy-engine:v1 \
  --push ./services/policy-engine

# 5. Human Review Service
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-human-review:v1 \
  --push ./services/human-review

# 6. Notification Service
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-notification:v1 \
  --push ./services/notification

# 7. API Gateway Service (for frontend queries)
docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-api-gateway:v1 \
  --push ./services/api-gateway

# 8. Frontend (React + Material-UI)
cd frontend
npm install
npm run build
cd ..

docker buildx build --platform linux/amd64 \
  -t $ACR_LOGIN_SERVER/guardian-ai-frontend:v1 \
  --push ./frontend

echo "✅ All 8 images pushed to ACR (6 backend + 1 API gateway + 1 frontend)"
```

### Step 5.3: Verify Images in ACR
```bash
# List all repositories
az acr repository list --name $ACR_NAME --output table

# Show tags for each service
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-ingestion
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-fast-screening
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-deep-vision
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-policy-engine
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-human-review
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-notification
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-api-gateway
az acr repository show-tags --name $ACR_NAME --repository guardian-ai-frontend

echo "✅ All 8 images verified in ACR"
```

---

## Phase 6: Configure Kubernetes Manifests (20 minutes)

### Step 6.1: Update Kubernetes ConfigMap with AWS Values
```bash
# Update ConfigMap with actual AWS values
cat > k8s/configmap.yaml <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: guardian-config
  namespace: production
data:
  # AWS Configuration
  AWS_REGION: "$AWS_REGION"
  S3_BUCKET_NAME: "$S3_BUCKET_NAME"
  
  # Simplified SQS Queues (2 queues)
  SQS_QUEUE_URL: "$SQS_QUEUE_URL"
  SQS_GPU_QUEUE_URL: "$SQS_GPU_QUEUE_URL"
  
  # Simplified DynamoDB Tables (2 tables)
  DYNAMODB_VIDEOS_TABLE: "guardian-videos"
  DYNAMODB_EVENTS_TABLE: "guardian-events"
  
  # Service Configuration
  LOG_LEVEL: "INFO"
  AUTO_APPROVE_THRESHOLD: "0.2"
  AUTO_REJECT_THRESHOLD: "0.8"
  
  # Redis Configuration
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"
  
  # Azure OpenAI Configuration (Optional)
  AZURE_OPENAI_ENABLED: "false"
  
  # Service URLs (for direct HTTP calls)
  NOTIFICATION_SERVICE_URL: "http://notification:8005"
  HUMAN_REVIEW_SERVICE_URL: "http://human-review:8004"
  POLICY_ENGINE_SERVICE_URL: "http://policy-engine-service:80"
EOF

echo "✅ ConfigMap updated with AWS values"
```

### Step 6.2: Update Image References in Kubernetes Manifests
```bash
# Update all deployment files with ACR name
find k8s -name "*.yaml" -type f -exec sed -i '' "s|[a-z0-9]*\.azurecr\.io|$ACR_LOGIN_SERVER|g" {} +

echo "✅ Kubernetes manifests updated with ACR login server"
```
### Step 6.2.1: Ensure ACR is Attached to AKS Cluster
```bash
# Ensure ACR is attached to AKS for image pull permissions
# This works for both new and existing clusters
if az aks check-acr --name $AKS_CLUSTER --resource-group $RESOURCE_GROUP --acr ${ACR_NAME}.azurecr.io &>/dev/null; then
  echo "✅ ACR is already attached to AKS cluster"
else
  echo "Attaching ACR to AKS cluster..."
  az aks update \
    --name $AKS_CLUSTER \
    --resource-group $RESOURCE_GROUP \
    --attach-acr $ACR_NAME
  
  echo "✅ ACR attached to AKS cluster"
fi
```
### Step 6.3: Create Kubernetes Namespace
```bash
# Create production namespace
kubectl create namespace production

# Verify
kubectl get namespaces

echo "✅ Production namespace created"
```

### Step 6.4: Create Kubernetes Secrets
```bash
# Create AWS credentials secret
kubectl create secret generic aws-secrets \
  --from-literal=AWS_ACCESS_KEY_ID="$(aws configure get aws_access_key_id)" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$(aws configure get aws_secret_access_key)" \
  -n production

# If Azure OpenAI is enabled, create OpenAI secret
if [ "$AZURE_OPENAI_ENABLED" = "true" ]; then
  kubectl create secret generic azure-openai-secrets \
    --from-literal=AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
    --from-literal=AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
    -n production
fi

# Verify secrets
kubectl get secrets -n production

echo "✅ Kubernetes secrets created"
```

---

## Phase 7: Deploy Services to Kubernetes (30 minutes)

### Step 7.1: Deploy ConfigMap
```bash
# Apply ConfigMap
kubectl apply -f k8s/configmap.yaml

# Verify
kubectl get configmap -n production
kubectl describe configmap guardian-config -n production

echo "✅ ConfigMap deployed"
```

### Step 7.2: Deploy Redis
```bash
# Deploy Redis
kubectl apply -f k8s/cpu-services/redis.yaml

# Wait for Redis to be ready
kubectl wait --for=condition=ready pod -l app=redis -n production --timeout=300s

# Verify
kubectl get pods -n production -l app=redis

echo "✅ Redis deployed"
```

### Step 7.3: Deploy CPU Services
```bash
# Deploy all CPU services (including API gateway)
kubectl apply -f k8s/cpu-services/ingestion-deployment.yaml
kubectl apply -f k8s/cpu-services/fast-screening.yaml
kubectl apply -f k8s/cpu-services/policy-engine.yaml
kubectl apply -f k8s/cpu-services/human-review-deployment.yaml
kubectl apply -f k8s/cpu-services/api-gateway.yaml
kubectl apply -f k8s/cpu-services/deep-vision.yaml

# Deploy notification service (if exists)
if [ -f k8s/cpu-services/notification.yaml ]; then
  kubectl apply -f k8s/cpu-services/notification.yaml
fi

echo "Waiting for all services to be ready (this may take 3-5 minutes)..."

# Wait for all services to be ready
kubectl wait --for=condition=ready pod -l app=redis -n production --timeout=300s
kubectl wait --for=condition=ready pod -l app=ingestion -n production --timeout=300s
kubectl wait --for=condition=ready pod -l app=fast-screening -n production --timeout=300s
kubectl wait --for=condition=ready pod -l app=policy-engine -n production --timeout=300s
kubectl wait --for=condition=ready pod -l app=human-review -n production --timeout=300s
kubectl wait --for=condition=ready pod -l app=api-gateway -n production --timeout=300s
kubectl wait --for=condition=ready pod -l app=deep-vision -n production --timeout=300s

# Verify
kubectl get pods -n production

echo "All CPU services deployed successfully."
```

<!-- ### Step 7.4: Deploy Deep Vision Service (CPU Version)
```bash
# NOTE: GPU node pool and KEDA are disabled due to subscription limitations
# The Deep Vision service runs on CPU nodes instead (slower but functional)

# Deploy Deep Vision service on CPU nodes
kubectl apply -f k8s/cpu-services/deep-vision.yaml

# Wait for Deep Vision to be ready
kubectl wait --for=condition=ready pod -l app=deep-vision -n production --timeout=300s

# Verify
kubectl get pods -n production -l app=deep-vision

echo "✅ Deep Vision service deployed on CPU nodes"
echo "⚠️  Note: Processing will be slower (~10-20s per video vs 2-3s on GPU)"
``` -->

### Step 7.5: Deploy Frontend
```bash
# Deploy frontend
kubectl apply -f k8s/frontend/frontend-deployment.yaml

# Wait for frontend to be ready
kubectl wait --for=condition=ready pod -l app=guardian-frontend -n production --timeout=300s

# Verify
kubectl get pods -n production -l app=guardian-frontend

echo "✅ Frontend deployed"
```

### Step 7.6: Deploy Ingress
```bash
# Deploy ingress (routes traffic to frontend and backend services)
kubectl apply -f k8s/ingress.yaml

# Verify
kubectl get ingress -n production

# Get ingress details
kubectl describe ingress guardian-ingress -n production

echo "✅ Ingress deployed"
echo "Application URL: http://$EXTERNAL_IP"
echo "Frontend: http://$EXTERNAL_IP"
echo "API: http://$EXTERNAL_IP/api"
```

### Step 7.7: Verify All Deployments
```bash
# Check all pods
kubectl get pods -n production

# Check all services
kubectl get svc -n production

# Check all deployments
kubectl get deployments -n production

# Check pod logs for any errors
kubectl logs -l tier=cpu -n production --tail=50

# Verify frontend is accessible
curl -I http://$EXTERNAL_IP

echo "✅ All services deployed (6 backend + 1 API gateway + 1 frontend = 8 total)"
```

---

## Phase 8: End-to-End Testing (30 minutes)

### Step 8.1: Test Frontend Access
```bash
# Open frontend in browser
echo "Frontend URL: http://$EXTERNAL_IP"
open "http://$EXTERNAL_IP"

# Or test with curl
curl -I http://$EXTERNAL_IP

# Expected: HTTP 200 OK

echo "✅ Frontend accessible"
```

### Step 8.2: Test Service Health Checks via API
```bash
# Get service endpoints
export INGESTION_URL="http://$EXTERNAL_IP/api/ingestion"
export API_GATEWAY_URL="http://$EXTERNAL_IP/api"
export POLICY_URL="http://$EXTERNAL_IP/api/policy"
export REVIEW_URL="http://$EXTERNAL_IP/api/review"

# Test health endpoints
echo "Testing service health checks..."

curl -s $INGESTION_URL/health | jq .
curl -s $POLICY_URL/health | jq .
curl -s $REVIEW_URL/health | jq .
curl -s $API_GATEWAY_URL/videos/health | jq .

echo "✅ All services responding"
```

### Step 8.3: Test Video Upload via Frontend
```bash
# Option 1: Use the frontend UI (Recommended)
echo "1. Open browser: http://$EXTERNAL_IP"
echo "2. Click 'Upload' tab"
echo "3. Drag & drop a test video (MP4, MOV, or AVI)"
echo "4. Click upload and note the job_id"
echo ""
echo "OR"
echo ""
echo "Option 2: Use curl (API testing)"

# Upload video via API
curl -X POST $INGESTION_URL/upload \
  -F "file=@test-video.mp4" \
  -v

# Save the job_id from response
export VIDEO_ID="<uuid-from-response>"

echo "✅ Video uploaded"
echo "Video ID: $VIDEO_ID"
```

### Step 8.4: Test Dashboard via Frontend
```bash
# Open dashboard in browser
echo "1. Click 'Dashboard' tab in the frontend"
echo "2. You should see your uploaded video"
echo "3. Check the status badge (should show 'Processing' or 'Uploaded')"
echo "4. Click 'View Details' to see full video information"
echo ""
echo "OR test via API:"

# Get all videos via API gateway
curl -s http://$EXTERNAL_IP/api/videos | jq .

# Get dashboard stats
curl -s http://$EXTERNAL_IP/api/dashboard/stats | jq .

echo "✅ Dashboard tested"
```

### Step 8.5: Verify Data in AWS
```bash
# Check video in S3
aws s3 ls s3://$S3_BUCKET_NAME/videos/

# Check video record in DynamoDB
aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION

# Check events in DynamoDB
aws dynamodb scan \
  --table-name guardian-events \
  --filter-expression "video_id = :vid" \
  --expression-attribute-values "{\":vid\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION \
  --limit 10

# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url $SQS_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages \
  --region $AWS_REGION

echo "✅ Data verified in AWS"
```

### Step 8.6: Monitor Processing
```bash
# Watch pod logs
kubectl logs -f -l app=ingestion -n production &
kubectl logs -f -l app=fast-screening -n production &
kubectl logs -f -l app=policy-engine -n production &

# Check GPU pod scaling (COMMENTED OUT - No GPU nodes)
# watch kubectl get pods -n production -l app=deep-vision

# Check KEDA metrics (COMMENTED OUT - KEDA not installed)
# kubectl get hpa -n production

echo "✅ Processing monitored"
```

### Step 8.7: Test Human Review Workflow
```bash
# Option 1: Use the frontend UI (Recommended)
echo "1. Click 'Review Queue' tab in the frontend"
echo "2. You should see videos pending review (if any)"
echo "3. Click 'Review' button on a video"
echo "4. Add review notes and click 'Approve' or 'Reject'"
echo ""
echo "OR test via API:"

# Get review queue via API
curl -s $REVIEW_URL/queue | jq .

# If video is in review queue, submit review
curl -X POST "$REVIEW_URL/review/$VIDEO_ID?approved=true&notes=Test+review" \
  -H "Content-Type: application/json"

echo "✅ Human review tested"
```

---

## Phase 8.5: Minimal MLOps Integration (Optional, 30 minutes)

### Overview
This phase wires up the existing MLOps scripts (`mlops/training/` and `mlops/deployment/`) with your application. By default, the system uses CLIP-only detection. After completing this phase, you can optionally use your own trained Azure ML models.

**Note**: This is a minimal implementation for learning purposes. For production CI/CD pipelines, see separate Azure DevOps/Azure ML documentation.

### Step 8.5.1: Setup Azure ML Workspace (One-time)
```bash
# Run the setup script
bash scripts/setup-mlops.sh

# Verify workspace was created
az ml workspace show \
  --name guardian-ml-workspace \
  --resource-group guardian-ai-prod
```

### Step 8.5.2: Train Models (Optional)
```bash
# Set environment variables
# Linux/macOS (bash):
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_RESOURCE_GROUP="guardian-ai-prod"
export AZURE_ML_WORKSPACE="guardian-ml-workspace"
export MLFLOW_TRACKING_URI="azureml://your-workspace"

# Windows (PowerShell):
# $env:AZURE_SUBSCRIPTION_ID = "your-subscription-id"
# $env:AZURE_RESOURCE_GROUP = "guardian-ai-prod"
# $env:AZURE_ML_WORKSPACE = "guardian-ml-workspace"
# $env:MLFLOW_TRACKING_URI = "azureml://your-workspace"

# Train models
cd mlops/training
python train_nsfw_model.py
python train_nsfw_model.py  # Run again for violence model (or modify script)
```

### Step 8.5.3: Deploy Models to Azure ML
```bash
cd mlops/deployment
python deploy_model.py

# This will output scoring URIs like:
# nsfw-detector: https://xxx.azureml.net/score
# violence-detector: https://xxx.azureml.net/score
```

### Step 8.5.4: Get Endpoint Information
```bash
# Use the helper script to get endpoints
bash scripts/get-model-endpoints.sh nsfw-detector
bash scripts/get-model-endpoints.sh violence-detector

# Or manually get endpoints:
az ml online-endpoint show \
  --name nsfw-detector-endpoint \
  --resource-group guardian-ai-prod \
  --workspace-name guardian-ml-workspace \
  --query scoring_uri -o tsv
```

### Step 8.5.5: Update Configuration

**For Local Development (docker-compose.yml):**
```bash
# Add to your .env file:
NSFW_MODEL_ENDPOINT="https://xxx.azureml.net/score"
VIOLENCE_MODEL_ENDPOINT="https://xxx.azureml.net/score"
MODEL_ENDPOINT_KEY="your-endpoint-key"

# Restart services
docker-compose restart deep-vision
```

**For Kubernetes (ConfigMap):**
```bash
# Update ConfigMap
kubectl edit configmap guardian-config -n production

# Add:
# NSFW_MODEL_ENDPOINT: "https://xxx.azureml.net/score"
# VIOLENCE_MODEL_ENDPOINT: "https://xxx.azureml.net/score"
# MODEL_ENDPOINT_KEY: "your-endpoint-key"

# Restart deep-vision pods
kubectl rollout restart deployment/deep-vision -n production
```

### Step 8.5.6: Verify Integration
```bash
# Check deep-vision logs to see if it's calling Azure ML endpoints
kubectl logs -l app=deep-vision -n production --tail=50 | grep "Model endpoint"

# Or for local:
docker-compose logs deep-vision | grep "Model endpoint"
```

### How It Works
- **Without Azure ML endpoints**: Deep-vision uses CLIP-only detection (default, works out of the box)
- **With Azure ML endpoints**: Deep-vision combines CLIP scores (30%) with custom model scores (70%) for improved accuracy
- **Fallback**: If endpoints are unavailable, the system gracefully falls back to CLIP-only

### Rollback Models (if needed)
```bash
# Rollback to previous model version
python mlops/deployment/rollback_model.py nsfw-detector
python mlops/deployment/rollback_model.py violence-detector
```

**Note**: For automated CI/CD pipelines with Azure DevOps and Azure ML Pipelines, see separate documentation (to be created separately).

---

## Phase 8.6: Post-Deployment Testing After ML Pipeline (45 minutes)

### Overview

This phase provides a comprehensive, step-by-step guide for verifying and testing your ML model deployment after running the `azure-pipelines-ml-deployment.yml` pipeline. This is **critical for learners** to understand the complete end-to-end workflow and ensure models are properly integrated into production.

**Prerequisites:**
- ✅ `azure-pipelines-ml-training.yml` pipeline completed successfully
- ✅ Models registered in Azure ML Model Registry
- ✅ `azure-pipelines-ml-deployment.yml` pipeline completed successfully

---

### Phase 1: Understanding What Happens During Deployment Pipeline

When `azure-pipelines-ml-deployment.yml` runs successfully, it performs the following actions:

#### 1.1: Deploys Models to Azure ML Online Endpoints
- Creates/updates `nsfw-detector-endpoint` (3 instances, Standard_DS3_v2)
- Creates/updates `violence-detector-endpoint` (3 instances, Standard_DS3_v2)
- Each endpoint becomes accessible via REST API with authentication

#### 1.2: Updates Kubernetes ConfigMap
- Retrieves endpoint URLs (`scoring_uri`) from Azure ML
- Retrieves endpoint authentication keys (`primaryKey`)
- Updates `k8s/configmap.yaml` with:
  - `NSFW_MODEL_ENDPOINT`: Full HTTPS URL to NSFW model endpoint
  - `VIOLENCE_MODEL_ENDPOINT`: Full HTTPS URL to violence model endpoint
  - `MODEL_ENDPOINT_KEY`: Authentication key for both endpoints

#### 1.3: Restarts Deep Vision Pods
- Applies updated ConfigMap to Kubernetes cluster
- Restarts `deep-vision` deployment to pick up new endpoint URLs
- Pods restart and load new environment variables

**Expected Pipeline Output:**
```
✅ Models deployed successfully
✅ ConfigMap updated with endpoint URLs
✅ deep-vision pods restarted
```

---

### Phase 2: Verification & Testing (Required Steps)

#### Step 2.1: Verify Endpoints Are Deployed

**Linux/macOS (bash):**
```bash
# Set variables (if not already set)
export AZURE_RESOURCE_GROUP="guardian-ai-prod"
export AZURE_ML_WORKSPACE="guardian-ai-ml-workspace-prod"

# Check endpoints in Azure ML Studio
az ml online-endpoint list \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --output table

# Expected output:
# NAME                        STATE    LOCATION    TARGET    MIR_MODE
# nsfw-detector-endpoint      Succeeded  eastus    3          None
# violence-detector-endpoint  Succeeded  eastus    3          None

# Check endpoint health (NSFW)
az ml online-endpoint show \
  --name nsfw-detector-endpoint \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --query "provisioning_state"

# Expected: "Succeeded"

# Check endpoint health (Violence)
az ml online-endpoint show \
  --name violence-detector-endpoint \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --query "provisioning_state"

# Expected: "Succeeded"

echo "✅ Endpoints verified"
```

**Windows (PowerShell):**
```powershell
# Set variables
$env:AZURE_RESOURCE_GROUP = "guardian-ai-prod"
$env:AZURE_ML_WORKSPACE = "guardian-ai-ml-workspace-prod"

# Check endpoints
az ml online-endpoint list `
  --resource-group $env:AZURE_RESOURCE_GROUP `
  --workspace-name $env:AZURE_ML_WORKSPACE `
  --output table

# Check endpoint health
az ml online-endpoint show `
  --name nsfw-detector-endpoint `
  --resource-group $env:AZURE_RESOURCE_GROUP `
  --workspace-name $env:AZURE_ML_WORKSPACE `
  --query "provisioning_state"

Write-Host "✅ Endpoints verified"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
export AZURE_RESOURCE_GROUP="guardian-ai-prod"
export AZURE_ML_WORKSPACE="guardian-ai-ml-workspace-prod"
az ml online-endpoint list --resource-group $AZURE_RESOURCE_GROUP --workspace-name $AZURE_ML_WORKSPACE --output table
```

#### Step 2.2: Verify ConfigMap Updated

**Linux/macOS (bash):**
```bash
# Check ConfigMap has endpoint URLs
kubectl get configmap guardian-config -n production -o yaml | grep -i "MODEL_ENDPOINT"

# Expected output:
#   NSFW_MODEL_ENDPOINT: https://xxx.azureml.net/v1/score
#   VIOLENCE_MODEL_ENDPOINT: https://xxx.azureml.net/v1/score
#   MODEL_ENDPOINT_KEY: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Verify deep-vision pods restarted
kubectl get pods -n production -l app=deep-vision

# Expected: Pods should show recent restart time (AGE should be recent)
# Example:
# NAME                          READY   STATUS    RESTARTS   AGE
# deep-vision-74b6f9cf8f-rpjhk  1/1     Running   0          2m

# Check pod logs for endpoint usage
kubectl logs -l app=deep-vision -n production --tail=50 | grep -i "endpoint\|model"

# Expected logs (if endpoints are configured):
# - "Using custom model endpoints"
# - "NSFW endpoint: https://..."
# - "Violence endpoint: https://..."

# OR (if endpoints not accessible, fallback):
# - "Model endpoint error: ..."
# - "Falling back to CLIP-only detection"

echo "✅ ConfigMap and pods verified"
```

**Windows (PowerShell):**
```powershell
# Check ConfigMap
kubectl get configmap guardian-config -n production -o yaml | Select-String -Pattern "MODEL_ENDPOINT"

# Verify pods
kubectl get pods -n production -l app=deep-vision

# Check logs
kubectl logs -l app=deep-vision -n production --tail=50 | Select-String -Pattern "endpoint|model"

Write-Host "✅ ConfigMap and pods verified"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
kubectl get configmap guardian-config -n production -o yaml | grep -i "MODEL_ENDPOINT"
kubectl get pods -n production -l app=deep-vision
```

#### Step 2.3: Test Model Endpoints Directly (Optional but Recommended)

**Linux/macOS (bash):**
```bash
# Get endpoint URL and key for NSFW model
export NSFW_ENDPOINT_URL=$(az ml online-endpoint show \
  --name nsfw-detector-endpoint \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --query scoring_uri -o tsv)

export ENDPOINT_KEY=$(az ml online-endpoint get-credentials \
  --name nsfw-detector-endpoint \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --query primaryKey -o tsv)

echo "NSFW Endpoint URL: $NSFW_ENDPOINT_URL"
echo "Endpoint Key: ${ENDPOINT_KEY:0:20}..." # Show first 20 chars only

# Test with a sample image (base64 encoded)
# Note: You'll need to encode a test image first
# For testing, you can use a simple test payload
curl -X POST "$NSFW_ENDPOINT_URL" \
  -H "Authorization: Bearer $ENDPOINT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
  }'

# Expected response: {"score": 0.0-1.0} or error message if image format invalid
# A valid response indicates the endpoint is working

# Test violence endpoint
export VIOLENCE_ENDPOINT_URL=$(az ml online-endpoint show \
  --name violence-detector-endpoint \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --query scoring_uri -o tsv)

curl -X POST "$VIOLENCE_ENDPOINT_URL" \
  -H "Authorization: Bearer $ENDPOINT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
  }'

echo "✅ Endpoint direct testing complete"
```

**Windows (PowerShell):**
```powershell
# Get endpoint URLs
$env:NSFW_ENDPOINT_URL = az ml online-endpoint show `
  --name nsfw-detector-endpoint `
  --resource-group $env:AZURE_RESOURCE_GROUP `
  --workspace-name $env:AZURE_ML_WORKSPACE `
  --query scoring_uri -o tsv

$env:ENDPOINT_KEY = az ml online-endpoint get-credentials `
  --name nsfw-detector-endpoint `
  --resource-group $env:AZURE_RESOURCE_GROUP `
  --workspace-name $env:AZURE_ML_WORKSPACE `
  --query primaryKey -o tsv

# Test endpoint
curl.exe -X POST "$env:NSFW_ENDPOINT_URL" `
  -H "Authorization: Bearer $env:ENDPOINT_KEY" `
  -H "Content-Type: application/json" `
  -d '{\"image\": \"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==\"}'

Write-Host "✅ Endpoint direct testing complete"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
export NSFW_ENDPOINT_URL=$(az ml online-endpoint show --name nsfw-detector-endpoint --resource-group $AZURE_RESOURCE_GROUP --workspace-name $AZURE_ML_WORKSPACE --query scoring_uri -o tsv)
export ENDPOINT_KEY=$(az ml online-endpoint get-credentials --name nsfw-detector-endpoint --resource-group $AZURE_RESOURCE_GROUP --workspace-name $AZURE_ML_WORKSPACE --query primaryKey -o tsv)
curl -X POST "$NSFW_ENDPOINT_URL" -H "Authorization: Bearer $ENDPOINT_KEY" -H "Content-Type: application/json" -d '{"image": "..."}'
```

---

### Phase 3: End-to-End Integration Testing (Critical for Learners)

#### Step 3.1: Test Video Upload Workflow

**Linux/macOS (bash):**
```bash
# Get external IP (if not already set)
export EXTERNAL_IP=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo "Application URL: http://$EXTERNAL_IP"

# Option 1: Upload via frontend (Recommended for learners)
echo "1. Open browser: http://$EXTERNAL_IP"
echo "2. Navigate to 'Upload' tab"
echo "3. Drag & drop a test video (MP4, MOV, or AVI)"
echo "4. Click 'Upload' and note the video_id from the response"
echo ""

# Option 2: Upload via API (for automated testing)
echo "OR upload via API:"
curl -X POST "http://$EXTERNAL_IP/api/ingestion/upload" \
  -F "file=@test-video.mp4" \
  -v

# Save the video_id from response
# Example response: {"video_id": "ab730f8c-bb35-462d-9eab-998663a32c13", ...}
export VIDEO_ID="<uuid-from-response>"

echo "✅ Video uploaded"
echo "Video ID: $VIDEO_ID"
```

**Windows (PowerShell):**
```powershell
# Get external IP
$env:EXTERNAL_IP = kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

Write-Host "Application URL: http://$env:EXTERNAL_IP"
Write-Host "1. Open browser: http://$env:EXTERNAL_IP"
Write-Host "2. Navigate to 'Upload' tab"
Write-Host "3. Upload a test video"

# Or via API
curl.exe -X POST "http://$env:EXTERNAL_IP/api/ingestion/upload" -F "file=@test-video.mp4"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
export EXTERNAL_IP=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl -X POST "http://$EXTERNAL_IP/api/ingestion/upload" -F "file=@test-video.mp4"
```

#### Step 3.2: Monitor Processing Pipeline

**Linux/macOS (bash):**
```bash
# Watch logs to see if models are being called
# This is CRITICAL to verify model integration
kubectl logs -f -l app=deep-vision -n production | grep -i "endpoint\|model\|nsfw\|violence"

# Expected logs (if endpoints are configured and working):
# - "🔔 Calling NSFW endpoint: https://xxx.azureml.net/v1/score"
# - "🔔 Calling Violence endpoint: https://xxx.azureml.net/v1/score"
# - "✅ NSFW model response: {'score': 0.15}"
# - "✅ Violence model response: {'score': 0.05}"
# - "Combining CLIP (30%) + Custom Model (70%) scores"

# Expected logs (if endpoints not accessible, graceful fallback):
# - "⚠️ Model endpoint error: Connection timeout"
# - "Falling back to CLIP-only detection"
# - "Using CLIP scores only"

# Expected logs (if endpoints not configured):
# - "Using CLIP only (no custom model endpoints configured)"

# Press Ctrl+C to stop watching logs
```

**Windows (PowerShell):**
```powershell
# Watch logs
kubectl logs -f -l app=deep-vision -n production | Select-String -Pattern "endpoint|model|nsfw|violence"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
kubectl logs -f -l app=deep-vision -n production | grep -i "endpoint\|model\|nsfw\|violence"
```

#### Step 3.3: Verify Model Integration

**Linux/macOS (bash):**
```bash
# Check if deep-vision is using custom models
kubectl logs -l app=deep-vision -n production --tail=100 | grep -E "endpoint|custom|CLIP"

# Check video processing status
curl -s "http://$EXTERNAL_IP/api/videos/$VIDEO_ID" | jq .

# Expected response includes:
# {
#   "video_id": "ab730f8c-bb35-462d-9eab-998663a32c13",
#   "status": "analyzed" | "processing" | "approved" | "rejected" | "review",
#   "nsfw_score": 0.15,
#   "violence_score": 0.05,
#   ...
# }

# Verify scores are calculated
curl -s "http://$EXTERNAL_IP/api/videos/$VIDEO_ID" | jq '.nsfw_score, .violence_score'

# Expected: Both scores should be present (0.0 to 1.0)

# Check if scores are from custom models (compare with CLIP-only baseline)
# Custom models typically provide more accurate scores
echo "✅ Model integration verified"
```

**Windows (PowerShell):**
```powershell
# Check logs
kubectl logs -l app=deep-vision -n production --tail=100 | Select-String -Pattern "endpoint|custom|CLIP"

# Check video status
$response = curl.exe -s "http://$env:EXTERNAL_IP/api/videos/$env:VIDEO_ID"
$response | ConvertFrom-Json | Format-List

Write-Host "✅ Model integration verified"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
kubectl logs -l app=deep-vision -n production --tail=100 | grep -E "endpoint|custom|CLIP"
curl -s "http://$EXTERNAL_IP/api/videos/$VIDEO_ID" | jq .
```

#### Step 3.4: Verify Complete Workflow

**Linux/macOS (bash):**
```bash
# 1. Check video status progression
#    Expected flow: uploaded → screened → analyzed → approved/rejected/review

echo "Checking video status progression..."
curl -s "http://$EXTERNAL_IP/api/videos/$VIDEO_ID" | jq '.status, .decision'

# Expected status progression:
# - "uploaded" → "screened" → "analyzed" → "approved"/"rejected"/"review"

# 2. Check DynamoDB for complete record
aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION | jq .

# Expected DynamoDB record includes:
# - video_id: UUID
# - uploaded_at: ISO timestamp
# - screened_at: ISO timestamp (if fast-screening completed)
# - analyzed_at: ISO timestamp (if deep-vision completed)
# - decided_at: ISO timestamp (if policy-engine made decision)
# - status: "approved" | "rejected" | "review"
# - decision: "approved" | "rejected" | "review"
# - nsfw_score: number (0.0-1.0)
# - violence_score: number (0.0-1.0)

# 3. Verify all stages completed
echo "Verifying all processing stages..."

# Check timestamps
UPLOADED=$(aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION \
  --query 'Item.uploaded_at.S' --output text)

SCREENED=$(aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION \
  --query 'Item.screened_at.S' --output text)

ANALYZED=$(aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION \
  --query 'Item.analyzed_at.S' --output text)

DECIDED=$(aws dynamodb get-item \
  --table-name guardian-videos \
  --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" \
  --region $AWS_REGION \
  --query 'Item.decided_at.S' --output text)

echo "Uploaded: ${UPLOADED:-'Not set'}"
echo "Screened: ${SCREENED:-'Not set'}"
echo "Analyzed: ${ANALYZED:-'Not set'}"
echo "Decided: ${DECIDED:-'Not set'}"

# All timestamps should be present for a complete workflow
if [ -n "$UPLOADED" ] && [ -n "$SCREENED" ] && [ -n "$ANALYZED" ] && [ -n "$DECIDED" ]; then
  echo "✅ All processing stages completed"
else
  echo "⚠️ Some stages may still be processing. Wait a few minutes and check again."
fi
```

**Windows (PowerShell):**
```powershell
# Check video status
$video = curl.exe -s "http://$env:EXTERNAL_IP/api/videos/$env:VIDEO_ID" | ConvertFrom-Json
Write-Host "Status: $($video.status)"
Write-Host "Decision: $($video.decision)"

# Check DynamoDB
$item = aws dynamodb get-item `
  --table-name guardian-videos `
  --key "{\"video_id\":{\"S\":\"$env:VIDEO_ID\"}}" `
  --region $env:AWS_REGION | ConvertFrom-Json

Write-Host "Uploaded: $($item.Item.uploaded_at.S)"
Write-Host "Screened: $($item.Item.screened_at.S)"
Write-Host "Analyzed: $($item.Item.analyzed_at.S)"
Write-Host "Decided: $($item.Item.decided_at.S)"

Write-Host "✅ Complete workflow verified"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
curl -s "http://$EXTERNAL_IP/api/videos/$VIDEO_ID" | jq '.status, .decision'
aws dynamodb get-item --table-name guardian-videos --key "{\"video_id\":{\"S\":\"$VIDEO_ID\"}}" --region $AWS_REGION | jq .
```

---

### Phase 4: Validation Checklist (For Learners)

After deployment pipeline completes, verify each item:

#### Azure ML Endpoints
- [ ] Both endpoints created (`nsfw-detector-endpoint`, `violence-detector-endpoint`)
- [ ] Endpoints show "Succeeded" provisioning state
- [ ] Endpoints are "Healthy" (traffic received, no errors)
- [ ] Endpoint URLs are accessible (tested with curl)

#### Kubernetes Integration
- [ ] ConfigMap updated with endpoint URLs (`NSFW_MODEL_ENDPOINT`, `VIOLENCE_MODEL_ENDPOINT`, `MODEL_ENDPOINT_KEY`)
- [ ] `deep-vision` pods restarted successfully
- [ ] Pods are "Running" and healthy (no CrashLoopBackOff)
- [ ] Pod logs show endpoint URLs are loaded

#### Model Integration
- [ ] `deep-vision` service can reach endpoints (check logs for "Calling NSFW endpoint" or "Calling Violence endpoint")
- [ ] Models are being called OR graceful fallback to CLIP (check logs)
- [ ] No connection errors in logs (no "Connection refused" or "Timeout")
- [ ] Scores are calculated (both `nsfw_score` and `violence_score` present)

#### End-to-End Testing
- [ ] Upload test video → Video appears in dashboard
- [ ] Processing completes → Status changes to final decision (`approved`/`rejected`/`review`)
- [ ] Scores are calculated → NSFW and Violence scores present (0.0-1.0)
- [ ] Video is playable → Streaming URL works
- [ ] Decision is made → Status is `approved`/`rejected`/`review` (not `pending` or `processing`)

---

### Phase 5: Production Verification

#### Step 5.1: Compare Model Performance

**Linux/macOS (bash):**
```bash
# Test with same video before/after model deployment
# Compare scores:
# - Before: CLIP-only scores (if endpoints not configured)
# - After: Custom model scores (should be more accurate)

echo "Comparing model performance..."

# Check logs for model usage
kubectl logs -l app=deep-vision -n production --tail=200 | grep -i "custom\|endpoint\|CLIP"

# Expected indicators of custom model usage:
# - "Combining CLIP (30%) + Custom Model (70%) scores"
# - "Custom model score: X"
# - "Final combined score: Y"

# If you see only "Using CLIP only", endpoints may not be configured correctly
echo "✅ Model performance comparison complete"
```

**Windows (PowerShell):**
```powershell
# Check logs
kubectl logs -l app=deep-vision -n production --tail=200 | Select-String -Pattern "custom|endpoint|CLIP"

Write-Host "✅ Model performance comparison complete"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
kubectl logs -l app=deep-vision -n production --tail=200 | grep -i "custom\|endpoint\|CLIP"
```

#### Step 5.2: Monitor Endpoint Metrics

**Linux/macOS (bash):**
```bash
# Check endpoint utilization in Azure Portal
echo "1. Open Azure Portal: https://portal.azure.com"
echo "2. Navigate to: Azure Machine Learning > Workspaces > $AZURE_ML_WORKSPACE > Endpoints"
echo "3. Select an endpoint (nsfw-detector-endpoint or violence-detector-endpoint)"
echo "4. Click 'Metrics' tab"
echo ""
echo "Monitor the following metrics:"
echo "- Request count (should increase as videos are processed)"
echo "- Response time (should be < 2 seconds per request)"
echo "- Error rate (should be < 1%)"
echo "- Cost per hour (Standard_DS3_v2 instances cost ~$0.20/hour each)"
echo ""
echo "OR use Azure CLI:"

# Get endpoint metrics (last 1 hour)
az monitor metrics list \
  --resource "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$AZURE_RESOURCE_GROUP/providers/Microsoft.MachineLearningServices/workspaces/$AZURE_ML_WORKSPACE/onlineEndpoints/nsfw-detector-endpoint" \
  --metric "RequestLatency" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --output table

echo "✅ Endpoint metrics monitoring complete"
```

**Windows (PowerShell):**
```powershell
Write-Host "1. Open Azure Portal: https://portal.azure.com"
Write-Host "2. Navigate to Azure Machine Learning > Workspaces > $env:AZURE_ML_WORKSPACE > Endpoints"
Write-Host "3. Select an endpoint and view Metrics"

Write-Host "✅ Endpoint metrics monitoring complete"
```

**Windows (Git Bash):**
```bash
# Same as Linux/macOS commands above
echo "Open Azure Portal to view endpoint metrics"
```

---

### Complete Workflow Summary

```
1. Training Pipeline (azure-pipelines-ml-training.yml)
   ↓
   Trains models → Registers in MLflow → Models available in registry
   
2. Deployment Pipeline (azure-pipelines-ml-deployment.yml)
   ↓
   Deploys to endpoints → Updates ConfigMap → Restarts pods
   
3. Verification & Testing (Manual Steps - This Phase)
   ↓
   Verify endpoints → Test endpoints → Verify ConfigMap → Check pod logs
   
4. End-to-End Testing (Critical)
   ↓
   Upload video → Monitor processing → Verify scores → Check decision
   
5. Production Use
   ↓
   Videos use custom models → Improved accuracy → Automated decisions
```

---

### Troubleshooting Common Issues

#### Issue: Endpoints Not Accessible from deep-vision Pods

**Symptoms:**
- Logs show "Connection refused" or "Timeout" errors
- Scores fall back to CLIP-only

**Diagnosis:**
```bash
# Check if endpoints are in ConfigMap
kubectl get configmap guardian-config -n production -o yaml | grep MODEL_ENDPOINT

# Check if deep-vision pods have the environment variables
kubectl exec -n production deployment/deep-vision -- env | grep MODEL_ENDPOINT

# Test endpoint connectivity from pod
kubectl exec -n production deployment/deep-vision -- python3 -c "
import os
import urllib.request
import json

endpoint = os.getenv('NSFW_MODEL_ENDPOINT')
key = os.getenv('MODEL_ENDPOINT_KEY')

if not endpoint:
    print('❌ NSFW_MODEL_ENDPOINT not set')
    exit(1)

print(f'Testing endpoint: {endpoint}')
try:
    req = urllib.request.Request(endpoint)
    req.add_header('Authorization', f'Bearer {key}')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=5) as response:
        print(f'✅ Endpoint accessible: {response.status}')
except Exception as e:
    print(f'❌ Endpoint error: {e}')
"
```

**Fix:**
```bash
# Re-run the deployment pipeline or manually update ConfigMap
# See Step 2.2 for ConfigMap update commands
```

#### Issue: Models Not Being Called (CLIP Fallback)

**Symptoms:**
- Logs show "Using CLIP only"
- No "Calling NSFW endpoint" messages

**Diagnosis:**
```bash
# Check if endpoints are configured
kubectl get configmap guardian-config -n production -o yaml | grep MODEL_ENDPOINT

# Check deep-vision code logic (endpoints may be empty strings)
kubectl logs -l app=deep-vision -n production --tail=100 | grep -i "endpoint\|model"
```

**Fix:**
- Ensure deployment pipeline completed successfully
- Verify ConfigMap has non-empty endpoint URLs
- Restart deep-vision pods: `kubectl rollout restart deployment/deep-vision -n production`

#### Issue: Endpoint Authentication Errors

**Symptoms:**
- Logs show "401 Unauthorized" or "Bearer token not provided"

**Diagnosis:**
```bash
# Check if MODEL_ENDPOINT_KEY is set
kubectl exec -n production deployment/deep-vision -- env | grep MODEL_ENDPOINT_KEY

# Verify key is correct
az ml online-endpoint get-credentials \
  --name nsfw-detector-endpoint \
  --resource-group $AZURE_RESOURCE_GROUP \
  --workspace-name $AZURE_ML_WORKSPACE \
  --query primaryKey -o tsv
```

**Fix:**
- Update ConfigMap with correct endpoint key
- Restart deep-vision pods

#### Issue: Video Stuck in "Processing" Status

**Symptoms:**
- Video uploaded but status never changes from "processing"
- Scores are calculated but decision is not made

**Diagnosis:**
```bash
# Check policy-engine logs
kubectl logs -l app=policy-engine -n production --tail=100 | grep -i "decide\|stuck"

# Check deep-vision logs for errors
kubectl logs -l app=deep-vision -n production --tail=100 | grep -i "error\|failed"

# Check if policy-engine is reachable from deep-vision
kubectl exec -n production deployment/deep-vision -- python3 -c "
import os
import urllib.request
url = os.getenv('POLICY_ENGINE_SERVICE_URL', 'http://policy-engine-service:80') + '/health'
try:
    with urllib.request.urlopen(url, timeout=5) as response:
        print(f'✅ Policy engine reachable: {response.status}')
except Exception as e:
    print(f'❌ Policy engine error: {e}')
"
```

**Fix:**
- Ensure `POLICY_ENGINE_SERVICE_URL` is correctly set in ConfigMap
- Verify policy-engine service is running: `kubectl get pods -n production -l app=policy-engine`
- Restart policy-engine if needed: `kubectl rollout restart deployment/policy-engine -n production`

---

### Next Steps After Successful Testing

1. ✅ **Document Results**: Record endpoint URLs, test results, and any issues encountered
2. ✅ **Monitor Production**: Set up alerts for endpoint errors or high latency
3. ✅ **Optimize Costs**: Review endpoint instance counts and scale down if needed
4. ✅ **Model Updates**: Plan for retraining and redeployment cycles
5. ✅ **Performance Tuning**: Compare custom model accuracy vs CLIP baseline

---

**Total Testing Time**: 45 minutes (first-time verification)
**Status**: ✅ Complete Post-Deployment Testing Guide
**Critical for Learners**: Yes - Ensures understanding of end-to-end ML integration

🎯 **Testing complete! Your ML models are now integrated into production.**

---

## Phase 9: Setup Monitoring (Optional, 30 minutes)

### Step 9.1: Install Prometheus
```bash
# Add Prometheus Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false

echo "✅ Prometheus installed"
```

### Step 9.2: Install Grafana
```bash
# Grafana is included in kube-prometheus-stack
# Get Grafana admin password
export GRAFANA_PASSWORD=$(kubectl get secret --namespace monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 --decode)

echo "Grafana admin password: $GRAFANA_PASSWORD"

# Port-forward Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80 &

echo "✅ Grafana available at http://localhost:3000"
echo "Username: admin"
echo "Password: $GRAFANA_PASSWORD"
```

### Step 9.3: Configure Service Monitors
```bash
# Create ServiceMonitor for our services
cat > k8s/monitoring/service-monitor.yaml <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: guardian-services
  namespace: production
spec:
  selector:
    matchLabels:
      monitor: guardian
  endpoints:
  - port: http
    interval: 30s
EOF

kubectl apply -f k8s/monitoring/service-monitor.yaml

echo "✅ Service monitors configured"
```

---

## Phase 10: Setup CI/CD (Optional, 30 minutes)

### Step 10.1: Configure GitHub Secrets
```bash
# Set GitHub secrets for CI/CD
# You'll need to do this manually in GitHub UI or use gh CLI

# Required secrets:
# - AZURE_CREDENTIALS (service principal JSON)
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - ACR_USERNAME
# - ACR_PASSWORD
# - AKS_CLUSTER_NAME
# - AKS_RESOURCE_GROUP

echo "Configure these secrets in GitHub:"
echo "1. Go to Settings > Secrets and variables > Actions"
echo "2. Add the following secrets:"
echo "   - AZURE_CREDENTIALS"
echo "   - AWS_ACCESS_KEY_ID"
echo "   - AWS_SECRET_ACCESS_KEY"
echo "   - ACR_USERNAME: $ACR_USERNAME"
echo "   - ACR_PASSWORD: $ACR_PASSWORD"
echo "   - AKS_CLUSTER_NAME: $AKS_CLUSTER"
echo "   - AKS_RESOURCE_GROUP: $RESOURCE_GROUP"
```

### Step 10.2: Test CI/CD Pipeline
```bash
# Push changes to trigger CI/CD
git add .
git commit -m "Deploy complete MLOps platform"
git push origin main

# Monitor GitHub Actions
echo "Check GitHub Actions at: https://github.com/yourusername/guardian-ai/actions"
```

---

## Phase 11: Load Testing (30 minutes)

### Step 11.1: Install k6
```bash
# Install k6 for load testing
brew install k6

# Verify
k6 version
```

### Step 11.2: Run Load Test
```bash
# Run load test script
bash scripts/load-test.sh

# Or use k6 directly
k6 run tests/load/load-test.js -e EXTERNAL_IP=$EXTERNAL_IP

echo "✅ Load testing complete"
```

### Step 11.3: Verify GPU Autoscaling (COMMENTED OUT - No GPU quota)
```bash
# NOTE: GPU autoscaling is disabled due to subscription limitations

# Monitor GPU pod scaling during load test
# watch kubectl get pods -n production -l app=deep-vision

# Check KEDA scaling events
# kubectl get events -n production --field-selector involvedObject.name=deep-vision-scaler

# Check HPA metrics
# kubectl get hpa -n production

# echo "✅ GPU autoscaling verified"

echo "⚠️  GPU autoscaling skipped (no GPU quota available)"
```

---

## Phase 12: Production Hardening (Optional, 1 hour)

### Step 12.1: Enable Network Policies
```bash
# Create network policies for security
kubectl apply -f k8s/network-policies/

echo "✅ Network policies enabled"
```

### Step 12.2: Configure Resource Limits
```bash
# Verify resource limits are set in deployments
kubectl describe deployment ingestion -n production | grep -A 5 "Limits"
kubectl describe deployment fast-screening -n production | grep -A 5 "Limits"

echo "✅ Resource limits configured"
```

### Step 12.3: Setup Backup Strategy
```bash
# Enable DynamoDB point-in-time recovery
aws dynamodb update-continuous-backups \
  --table-name guardian-videos \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

aws dynamodb update-continuous-backups \
  --table-name guardian-events \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Enable S3 versioning (already enabled by setup script)
aws s3api get-bucket-versioning --bucket $S3_BUCKET_NAME

echo "✅ Backup strategy configured"
```

---

## Success Checklist

### AWS Resources
- [ ] S3 bucket created and accessible
- [ ] 2 SQS queues created (video-processing, gpu-processing)
- [ ] 2 DynamoDB tables created (videos, events)
- [ ] DynamoDB TTL enabled on events table
- [ ] AWS credentials configured

### Azure Resources
- [ ] Resource group created
- [ ] ACR created and images pushed
- [ ] AKS cluster created with 3+ nodes
- [ ] ~~GPU node pool added~~ (Skipped - no GPU quota)
- [ ] ~~KEDA installed~~ (Skipped - not needed without GPU)
- [ ] NGINX Ingress installed with external IP

### Kubernetes Deployment
- [ ] Production namespace created
- [ ] ConfigMap deployed with AWS values
- [ ] Secrets created (AWS credentials)
- [ ] Redis deployed and running
- [ ] All 6 backend services deployed and running
- [ ] API Gateway deployed and running
- [ ] Frontend deployed and accessible
- [ ] ~~GPU service deployed with KEDA autoscaling~~ (Running on CPU instead)
- [ ] Ingress configured with all routes

### Testing & Validation
- [ ] Frontend accessible at http://EXTERNAL_IP
- [ ] Upload page works (drag & drop video)
- [ ] Dashboard displays videos with status
- [ ] Review queue shows pending reviews
- [ ] Video details page shows scores and timeline
- [ ] Health checks pass for all services
- [ ] Video upload works end-to-end
- [ ] Data appears in S3, DynamoDB, SQS
- [ ] ~~GPU autoscaling works (scales 0→1→0)~~ (Skipped - no GPU quota)
- [ ] Human review workflow functional via UI
- [ ] Monitoring configured (Prometheus + Grafana)
- [ ] Load testing completed

---

## Cost Management

### Current Monthly Costs
**AWS**: ~$25-40/month
- S3: $3-5
- SQS (2 queues): $1-2
- DynamoDB (2 tables): $10-20
- Data transfer: $5-10

**Azure**: ~$100-150/month
- AKS (3 nodes): $100-130
- ACR: $5
- ~~GPU nodes: $0 (scale-to-zero when idle)~~ (Not used - no GPU quota)
- Monitoring: $5-10

**Total**: ~$125-190/month

### Cost Optimization Tips
```bash
# Scale down AKS during off-hours
az aks scale \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_CLUSTER \
  --node-count 1

# Purge SQS queues when not testing
aws sqs purge-queue --queue-url $SQS_QUEUE_URL
aws sqs purge-queue --queue-url $SQS_GPU_QUEUE_URL

# Delete old S3 videos
aws s3 rm s3://$S3_BUCKET_NAME/videos/ --recursive --exclude "*" --include "*-old-*"

# Monitor costs
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost

az consumption usage list --output table
```

---

## Troubleshooting

### Issue: Pods not starting
```bash
# Check pod status
kubectl get pods -n production

# Describe pod
kubectl describe pod <POD_NAME> -n production

# Check logs
kubectl logs <POD_NAME> -n production

# Check events
kubectl get events -n production --sort-by='.lastTimestamp'
```

### Issue: Cannot pull images from ACR
```bash
# Verify ACR attachment
az aks check-acr --resource-group $RESOURCE_GROUP --name $AKS_CLUSTER --acr $ACR_NAME

# Re-attach ACR if needed
az aks update --resource-group $RESOURCE_GROUP --name $AKS_CLUSTER --attach-acr $ACR_NAME
```

### Issue: Services cannot connect to AWS
```bash
# Verify AWS secrets
kubectl get secret aws-secrets -n production -o yaml

# Test AWS connectivity from pod
kubectl exec -it <POD_NAME> -n production -- env | grep AWS
kubectl exec -it <POD_NAME> -n production -- python3 -c "import boto3; print(boto3.client('s3').list_buckets())"
```

### Issue: GPU pods not scaling (COMMENTED OUT - No GPU quota)
```bash
# NOTE: GPU autoscaling is disabled due to subscription limitations

# Check KEDA operator
# kubectl get pods -n keda

# Check ScaledObject
# kubectl describe scaledobject deep-vision-scaler -n production

# Check SQS queue depth
# aws sqs get-queue-attributes --queue-url $SQS_GPU_QUEUE_URL --attribute-names ApproximateNumberOfMessages

echo "⚠️  GPU troubleshooting skipped (no GPU quota available)"
```

---

## Cleanup (When Done Testing)

### Delete Kubernetes Resources
```bash
# Delete all resources in production namespace
kubectl delete namespace production

# Delete KEDA (COMMENTED OUT - Not installed)
# helm uninstall keda -n keda
# kubectl delete namespace keda

# Delete Ingress
helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace ingress-nginx

# Delete Monitoring
helm uninstall prometheus -n monitoring
kubectl delete namespace monitoring
```

### Delete Azure Resources
```bash
# Delete entire resource group (removes AKS, ACR, etc.)
az group delete --name $RESOURCE_GROUP --yes --no-wait

# Remove local Kubernetes context
kubectl config delete-context $AKS_CLUSTER
```

### Delete AWS Resources
```bash
# Delete S3 bucket
aws s3 rb s3://$S3_BUCKET_NAME --force

# Delete SQS queues
aws sqs delete-queue --queue-url $SQS_QUEUE_URL
aws sqs delete-queue --queue-url $SQS_GPU_QUEUE_URL

# Delete DynamoDB tables
aws dynamodb delete-table --table-name guardian-videos
aws dynamodb delete-table --table-name guardian-events
```

---

## Next Steps

After completing this deployment:
1. ✅ Document any issues encountered
2. ✅ Take screenshots of working system
3. ✅ Export monitoring dashboards
4. ✅ Create final learner documentation
5. ✅ Prepare demo videos/walkthroughs

---

**Total Deployment Time**: 4-6 hours (first time)
**Status**: ✅ Complete End-to-End Deployment
**Cost**: ~$125-190/month
**Production Ready**: Yes

🚀 **System fully deployed and validated!**
