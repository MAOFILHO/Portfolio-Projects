# Azure DevOps & Azure ML Integration Guide

**🎯 Goal**: Complete the MLOps workflow with automated CI/CD pipelines using Azure DevOps and Azure ML

**💰 Cost**: ~$20-100/month (Azure DevOps Pipelines + Azure ML compute)

**⏱️ Time**: 4-6 hours (first-time setup)

---

## Overview

This guide walks you through setting up:
1. **Azure DevOps** - CI/CD pipelines for application services (build, test, deploy)
2. **Azure ML** - ML pipelines for model training and deployment
3. **Integration** - Connecting both systems for complete MLOps workflow

**Note**: This guide focuses on Azure Portal UI workflows. For CLI-based setup, see alternative commands in appendices.

---

## Prerequisites

### Required Azure Resources (Already Created)
- ✅ Azure Subscription
- ✅ Resource Group: `guardian-ai-prod`
- ✅ AKS Cluster: `guardian-ai-aks` (or your cluster name)
- ✅ ACR: `guardianacr58206` (or your ACR name)
- ✅ Azure ML Workspace: `guardian-ml-workspace-prod` (create if not exists)

### Required Accounts & Permissions
- Azure subscription with **Owner** or **Contributor** role
- GitHub account (if using GitHub integration)
- Azure DevOps account (will create during setup)

### Current Project State
- ✅ All services deployed to AKS
- ✅ ConfigMap updated with Azure ML endpoint variables
- ✅ MLOps scripts ready (`mlops/training/`, `mlops/deployment/`)
- ✅ Docker images in ACR

---

## Part 1: Azure DevOps Setup (2-3 hours)

### Phase 1.1: Create Azure DevOps Organization & Project

#### Step 1.1.1: Create Organization
1. Go to [Azure DevOps Portal](https://dev.azure.com)
2. Click **"Create organization"** (or sign in if you have one)
3. Fill in:
   - **Organization name**: `guardian-ai-org` (or your choice)
   - **Region**: Choose closest to your AKS cluster
   - **Verify email** if prompted
4. Click **"Continue"**

#### Step 1.1.2: Create Project
1. After organization is created, click **"Create project"**
2. Fill in:
   - **Project name**: `guardian-ai-mlops`
   - **Visibility**: Private (recommended for learning)
   - **Version control**: Git (recommended)
   - **Work item process**: Basic (simplest)
3. Click **"Create"**

#### Step 1.1.3: Import Your Repository
**Option A: Connect Existing GitHub Repository**
1. In your project, go to **Repos** → **Files**
2. Click **"Import repository"**
3. Select **"GitHub"**
4. Authorize Azure DevOps to access GitHub
5. Select your repository: `MLOps_Project`
6. Click **"Import"**

**Option B: Push Code to Azure Repos**
1. In your project, go to **Repos** → **Files**
2. Copy the repository URL shown
3. From your local machine:
   ```bash
   cd /Users/chenkonsam/Projects/MLOps_Project
   git remote add azure-devops <repository-url>
   git push azure-devops main
   ```

---

### Phase 1.2: Create Service Connections

Service connections allow Azure DevOps to access your Azure resources.

#### Step 1.2.1: Create Azure Resource Manager Service Connection
1. In your project, go to **Project Settings** (gear icon, bottom left)
2. Under **Pipelines**, click **"Service connections"**
3. Click **"Create service connection"**
4. Select **"Azure Resource Manager"**
5. Select **"Identity type - App Registration (automatic)"** (recommended)
6. Select **"Credential - Workload Identity federation (automatic)"** (recommended)
7. Click **"Next"**
8. Fill in:
   - **Subscription**: Select your Azure subscription
   - **Resource group**: `guardian-ai-prod`
   - **Service connection name**: `guardian-azure-connection`
   - **Security**: Grant access permission to all pipelines (or specific pipelines)
9. Click **"Save"**

#### Step 1.2.2: Create Docker Registry Service Connection (ACR)
1. In **Service connections**, click **"Create service connection"**
2. Select **"Docker Registry"**
3. Select **"Azure Container Registry"**
4. Select **"Authentication Type - Workload Identity federation"** 
5. Fill in:
   - **Azure subscription**: Select your subscription
   - **Azure container registry**: `guardianacr58206` (or your ACR name)
   - **Service connection name**: `guardian-acr-connection`
   - **Security**: Grant access permission to all pipelines
6. Click **"Save"**

#### Step 1.2.3: Create Kubernetes Service Connection
1. In **Service connections**, click **"Create service connection"**
2. Select **"Kubernetes"**
3. Select **"Azure subscription"**
4. Fill in:
   - **Subscription**: Select your subscription
   - **Resource group**: `guardian-ai-prod`
   - **Kubernetes cluster**: `guardian-ai-aks` (or your cluster name)
   - **Namespace**: `production`
   - Disable: Use cluster admin credentials
   - **Service connection name**: `guardian-aks-connection`
   - **Security**: Grant access permission to all pipelines
5. Click **"Save"**

---

### Phase 1.3: Setup Self-Hosted Agent (macOS/Linux)

The pipelines use `pool: name: 'Default'`, which requires a self-hosted agent. This phase sets up the agent on your local machine (macOS or Linux).

#### Step 1.3.1: Verify/Create Default Agent Pool

1. Go to **Azure DevOps** → Your project (`guardian-ai-mlops`)
2. Click **Project Settings** (gear icon, bottom left)
3. Under **Pipelines**, click **"Agent pools"**
4. Verify **"Default"** pool exists (it should exist by default)
5. If it doesn't exist:
   - Click **"+ Add pool"**
   - Select **"Self-hosted"**
   - Name: `Default`
   - Click **"Create"**

**Note**: The pipeline YAML uses `pool: name: 'Default'`, so ensure this pool exists.

#### Step 1.3.2: Create Personal Access Token (PAT)

1. In Azure DevOps, click your profile (top right) → **"Personal access tokens"**
2. Click **"+ New Token"**
3. Fill in:
   - **Name**: `Self-hosted Agent Token` (or any descriptive name)
   - **Organization**: Select your organization
   - **Expiration**: Choose expiration (90 days recommended for learning)
   - **Scopes**: Select **"Full access"** (for learning) or **"Agent Pools (Read & manage)"** (more secure)
4. Click **"Create"**
5. **Important**: Copy the token immediately (you won't see it again)
   - Format: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Save it securely (you'll need it in Step 1.3.5)

#### Step 1.3.3: Download Agent Software

1. In Azure DevOps, go to **Project Settings** → **Agent pools**
2. Click on **"Default"** pool
3. Click **"New agent"**
4. Select your OS:
   - **macOS**: Download `vsts-agent-osx-x64-*.tar.gz` (or `vsts-agent-osx-arm64-*.tar.gz` for Apple Silicon)
   - **Linux**: Download `vsts-agent-linux-x64-*.tar.gz`
5. Extract the archive:
   ```bash
   # macOS
   cd ~/Downloads
   tar -xzf vsts-agent-osx-x64-*.tar.gz
   cd vsts-agent-osx-x64-*
   
   # Linux
   cd ~/Downloads
   tar -xzf vsts-agent-linux-x64-*.tar.gz
   cd vsts-agent-linux-x64-*
   ```

#### Step 1.3.4: Configure Agent (macOS - Gatekeeper Fix)

**Important for macOS**: macOS Gatekeeper may block the agent scripts. Fix this first:

```bash
# Navigate to agent directory
cd ~/Downloads/vsts-agent-osx-x64-*  # or vsts-agent-osx-arm64-* for Apple Silicon

# Remove quarantine attributes (allows scripts to run)
xattr -cr .
```

**Why this is needed**: macOS Gatekeeper blocks unsigned executables. This command removes the quarantine attribute so `./config.sh` and `./run.sh` can execute.

**Note**: On Linux, skip this step (the `xattr` command is macOS-specific).

#### Step 1.3.5: Configure Agent

1. Run the configuration script:
   ```bash
   ./config.sh
   ```

2. When prompted, enter:
   - **Server URL**: `https://dev.azure.com/<your-org-name>`
     - Example: `https://dev.azure.com/guardian-ai-org`
     - **Important**: Use only the organization URL, NOT the project URL
   - **Authentication type**: `PAT` (Personal Access Token)
   - **Personal Access Token**: Paste the token from Step 1.3.2
   - **Agent pool**: `Default` (or press Enter for default)
   - **Agent name**: Your machine name (e.g., `Heeyaichens-Mac-mini`) or press Enter for auto-generated name
   - **Work folder**: Press Enter for default (`_work`)

3. Configuration completes successfully when you see:
   ```
   ✓ Successfully added the agent
   ```

#### Step 1.3.6: Run Agent

1. Start the agent:
   ```bash
   ./run.sh
   ```

2. You should see:
   ```
   Scanning for tool capabilities.
   Connecting to the server.
   Listening for Jobs
   ```

3. **Keep this terminal open** - the agent must stay running to pick up pipeline jobs.

4. **For other terminal tasks**: Open a new terminal window/tab (don't close the agent terminal).

#### Step 1.3.7: Verify Agent is Online

1. In Azure DevOps, go to **Project Settings** → **Agent pools** → **Default**
2. You should see your agent listed with status **"Online"** (green dot)
3. If it shows **"Offline"**:
   - Check the terminal where `./run.sh` is running for errors
   - Verify PAT token hasn't expired
   - Verify server URL is correct (organization only, no project path)

#### Troubleshooting Agent Setup

**Issue: "No agent found" when running pipeline**
- Verify agent pool name matches pipeline YAML (`Default`)
- Check agent is online in Azure DevOps
- Ensure `./run.sh` is running in a terminal

**Issue: "xattr: command not found" (Linux)**
- The `xattr -cr .` command is macOS-specific. On Linux, skip Step 1.3.4.

**Issue: Agent shows "Offline" but `./run.sh` is running**
- Check server URL is correct (organization only: `https://dev.azure.com/<org>`, not `https://dev.azure.com/<org>/<project>`)
- Verify PAT token is valid and has correct permissions
- Run `xattr -cr .` in the agent directory before `./config.sh` (macOS only)

**Note**: For Apple Silicon Macs, consider using the ARM64 agent (`vsts-agent-osx-arm64-*.tar.gz`) to avoid X64 emulation warnings and improve performance.

---

### Phase 1.4: Create Application CI/CD Pipeline

This pipeline builds Docker images and deploys to AKS.

#### Step 1.4.1: Create Pipeline YAML File
1. In your project, go to **Repos** → **Files**
2. Navigate to root directory
3. Click **"New"** → **"File"**
4. Name: `azure-pipelines-app-ci-cd.yml`
6. Click **"Commit"** to save the file

#### Step 1.4.2: Create Variable Group (Required)
The pipeline uses **only** the variable group for env-specific values; there are no hardcoded ACR or cluster names in the YAML. Each learner must create this group and set their own values so the same pipeline file works for everyone.

1. In your project, go to **Pipelines** → **Library**
2. Click **"+ Variable group"**
3. Name: `guardian-variables`
4. Add the following variables (use **your own** values from your Azure setup):
   - **`ACR_NAME`**: Your Azure Container Registry name (e.g. the name from `az acr create --name <ACR_NAME> ...`). Example: `guardianacr58206`
   - **`AKS_CLUSTER`**: Your AKS cluster name. Example: `guardian-ai-aks`
   - **`RESOURCE_GROUP`**: The resource group containing ACR and AKS. Example: `guardian-ai-prod`
   - **`NAMESPACE`**: Kubernetes namespace for the app. Example: `production`
5. Click **"Save"**

If any of these variables are missing, the pipeline will fail when it runs. Do not edit the pipeline YAML to hardcode values—use this variable group so each user can run the project with their own ACR and cluster.

#### Step 1.4.3: Create Pipeline from YAML
1. Go to **Pipelines** → **Pipelines**
2. Click **"Create Pipeline"**
3. Select **"Azure Repos Git"** (or GitHub if using GitHub)
4. Select your repository: `MLOps_Project`
5. Select **"Existing Azure Pipelines YAML file"**
6. Branch: `main`
7. Path: `azure-pipelines-app-ci-cd.yml`
8. Click **"Continue"**
9. Review the pipeline, click **"Run"**

#### Step 1.4.4: Verify Pipeline Runs Successfully
1. Go to **Pipelines** → **Pipelines**
2. Click on your pipeline: `MLOps_Project`
3. Watch the build progress
4. Check for any errors and fix them
5. Once successful, the pipeline will:
   - Build all Docker images
   - Push to ACR
   - Deploy to AKS

---

## Part 2: Azure ML Setup & Configuration (1-2 hours)

### Phase 2.1: Verify/Create Azure ML Workspace

#### Step 2.1.1: Check if Workspace Exists
1. Go to [Azure Portal](https://portal.azure.com)
2. Search for **"Machine Learning"**
3. Check if workspace `guardian-ai-ml-workspace-prod` exists in resource group `guardian-ai-prod`

#### Step 2.1.2: Create Workspace (if not exists)
1. Click **"+ Create"**
2. Fill in:
   - **Subscription**: Your subscription
   - **Resource group**: `guardian-ai-prod`
   - **Workspace name**: `guardian-ai-ml-workspace-prod`
   - **Region**: Same as your AKS cluster
   - **Storage account**: Create new (auto-generated name)
   - **Key vault**: Create new (auto-generated name)
   - **Application insights**: Create new (auto-generated name)
   - **Container registry**: None (or select your ACR if you want)
3. Click **"Review + Create"** → **"Create"**
4. Wait for deployment (2-3 minutes)

#### Step 2.1.3: Get Workspace Details
1. Go to your workspace: `guardian-ai-ml-workspace-prod`
2. Note down:
   - **Workspace name**: `guardian-ai-ml-workspace-prod`
   - **Resource group**: `guardian-ai-prod`
   - **Subscription ID**: (from Overview page)
   - **MLflow tracking URI**: (from Overview → Properties, format: `azureml://eastus.api.azureml.ms/mlflow/v1.0/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.MachineLearningServices/workspaces/<workspace>`)

---

### Phase 2.2: Create Compute Targets

Compute targets are where your ML training jobs run.

#### Step 2.2.1: Create CPU Compute Cluster (for training)
1. In Azure ML workspace, go to **Compute** → **Compute clusters**
2. Click **"+ New"**
3. Fill in:
   - **Compute name**: `cpu-training-cluster`
   - **Virtual machine type**: CPU
   - **Virtual machine size**: `Standard_DS3_v2` (4 vCPUs, 14 GB RAM) - good for learning
   - **Minimum nodes**: `0` (scale to zero when not in use)
   - **Maximum nodes**: `2`
   - **Idle seconds before scale down**: `120`
4. Click **"Create"**
5. Wait for creation (2-3 minutes)

<!-- #### Step 2.2.2: Create GPU Compute Cluster (optional, for faster training)
1. In **Compute** → **Compute clusters**, click **"+ New"**
2. Fill in:
   - **Compute name**: `gpu-training-cluster`
   - **Virtual machine type**: GPU
   - **Virtual machine size**: `Standard_NC6s_v3` (6 vCPUs, 112 GB RAM, 1 GPU)
   - **Minimum nodes**: `0`
   - **Maximum nodes**: `1`
   - **Idle seconds before scale down**: `120`
3. Click **"Create"**
4. **Note**: GPU clusters are expensive (~$2-3/hour). Use CPU for learning. -->

---

### Phase 2.3: Create ML Pipeline for Training

Azure ML Pipelines automate model training workflows.

#### Step 2.3.1: Prepare Training Script
Your training script (`mlops/training/train_nsfw_model.py`) is already ready. Verify it uses:
- `MLClient` from `azure.ai.ml`
- Environment variables for configuration
- MLflow for tracking

#### Step 2.3.2: Create Pipeline YAML File
1. In Azure DevOps, go to **Repos** → **Files**
2. Create new file: `azure-pipelines-ml-training.yml`
3. Copy the following content:

```yaml
# Azure DevOps Pipeline: ML Model Training
# Trigger: Manual or on schedule/tag

trigger: none  # Manual trigger only

pool:
  vmImage: 'ubuntu-latest'

variables:
  - group: guardian-variables
  - name: AZURE_SUBSCRIPTION_ID
    value: 'your-subscription-id'  # Replace with your subscription ID
  - name: AZURE_RESOURCE_GROUP
    value: 'guardian-ai-prod'
  - name: AZURE_ML_WORKSPACE
    value: 'guardian-ml-workspace'
  - name: COMPUTE_CLUSTER
    value: 'cpu-training-cluster'

stages:
  - stage: TrainModels
    displayName: 'Train ML Models'
    jobs:
      - job: TrainNSFWModel
        displayName: 'Train NSFW Detection Model'
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '3.11'
            displayName: 'Use Python 3.11'

          - script: |
              python -m pip install --upgrade pip
              pip install azure-ai-ml azure-identity mlflow torch torchvision transformers
            displayName: 'Install dependencies'

          - task: AzureCLI@2
            displayName: 'Azure Login'
            inputs:
              azureSubscription: 'guardian-azure-connection'
              scriptType: 'bash'
              scriptLocation: 'inlineScript'
              inlineScript: |
                az account set --subscription $(AZURE_SUBSCRIPTION_ID)
                az login --service-principal --username $(AZURE_CLIENT_ID) --password $(AZURE_CLIENT_SECRET) --tenant $(AZURE_TENANT_ID) || az login

          - script: |
              export AZURE_SUBSCRIPTION_ID="$(AZURE_SUBSCRIPTION_ID)"
              export AZURE_RESOURCE_GROUP="$(AZURE_RESOURCE_GROUP)"
              export AZURE_ML_WORKSPACE="$(AZURE_ML_WORKSPACE)"
              export MLFLOW_TRACKING_URI="azureml://$(AZURE_ML_WORKSPACE).api.azureml.ms/mlflow/v1.0/subscriptions/$(AZURE_SUBSCRIPTION_ID)/resourceGroups/$(AZURE_RESOURCE_GROUP)/providers/Microsoft.MachineLearningServices/workspaces/$(AZURE_ML_WORKSPACE)"
              
              cd mlops/training
              python train_nsfw_model.py
            displayName: 'Train NSFW Model'
            env:
              AZURE_SUBSCRIPTION_ID: $(AZURE_SUBSCRIPTION_ID)
              AZURE_RESOURCE_GROUP: $(AZURE_RESOURCE_GROUP)
              AZURE_ML_WORKSPACE: $(AZURE_ML_WORKSPACE)

      - job: TrainViolenceModel
        displayName: 'Train Violence Detection Model'
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '3.11'

          - script: |
              python -m pip install --upgrade pip
              pip install azure-ai-ml azure-identity mlflow torch torchvision transformers
            displayName: 'Install dependencies'

          - task: AzureCLI@2
            displayName: 'Azure Login'
            inputs:
              azureSubscription: 'guardian-azure-connection'
              scriptType: 'bash'
              scriptLocation: 'inlineScript'
              inlineScript: |
                az account set --subscription $(AZURE_SUBSCRIPTION_ID)

          - script: |
              export AZURE_SUBSCRIPTION_ID="$(AZURE_SUBSCRIPTION_ID)"
              export AZURE_RESOURCE_GROUP="$(AZURE_RESOURCE_GROUP)"
              export AZURE_ML_WORKSPACE="$(AZURE_ML_WORKSPACE)"
              export MLFLOW_TRACKING_URI="azureml://$(AZURE_ML_WORKSPACE).api.azureml.ms/mlflow/v1.0/subscriptions/$(AZURE_SUBSCRIPTION_ID)/resourceGroups/$(AZURE_RESOURCE_GROUP)/providers/Microsoft.MachineLearningServices/workspaces/$(AZURE_ML_WORKSPACE)"
              
              cd mlops/training
              python train_nsfw_model.py  # Modify to train violence model
            displayName: 'Train Violence Model'
            env:
              AZURE_SUBSCRIPTION_ID: $(AZURE_SUBSCRIPTION_ID)
              AZURE_RESOURCE_GROUP: $(AZURE_RESOURCE_GROUP)
              AZURE_ML_WORKSPACE: $(AZURE_ML_WORKSPACE)
```

4. **Important**: Replace `your-subscription-id` with your actual Azure subscription ID
5. Click **"Commit"**

#### Step 2.3.3: Create ML Training Pipeline
1. Go to **Pipelines** → **Pipelines**
2. Click **"Create Pipeline"**
3. Select your repository
4. Select **"Existing Azure Pipelines YAML file"**
5. Path: `azure-pipelines-ml-training.yml`
6. Click **"Continue"** → **"Run"** (or save for manual trigger)

---

### Phase 2.4: Create ML Pipeline for Deployment

This pipeline deploys trained models to Azure ML endpoints.

#### Step 2.4.1: Create Deployment Pipeline YAML
1. Create new file: `azure-pipelines-ml-deployment.yml`
2. Copy the following content:

```yaml
# Azure DevOps Pipeline: ML Model Deployment
# Trigger: After training pipeline completes or manual

trigger: none  # Manual trigger

pool:
  vmImage: 'ubuntu-latest'

variables:
  - group: guardian-variables
  - name: AZURE_SUBSCRIPTION_ID
    value: 'your-subscription-id'  # Replace
  - name: AZURE_RESOURCE_GROUP
    value: 'guardian-ai-prod'
  - name: AZURE_ML_WORKSPACE
    value: 'guardian-ml-workspace'

stages:
  - stage: DeployModels
    displayName: 'Deploy Models to Azure ML'
    jobs:
      - job: DeployModels
        displayName: 'Deploy All Models'
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '3.11'

          - script: |
              python -m pip install --upgrade pip
              pip install azure-ai-ml azure-identity mlflow
            displayName: 'Install dependencies'

          - task: AzureCLI@2
            displayName: 'Azure Login'
            inputs:
              azureSubscription: 'guardian-azure-connection'
              scriptType: 'bash'
              scriptLocation: 'inlineScript'
              inlineScript: |
                az account set --subscription $(AZURE_SUBSCRIPTION_ID)

          - script: |
              export AZURE_SUBSCRIPTION_ID="$(AZURE_SUBSCRIPTION_ID)"
              export AZURE_RESOURCE_GROUP="$(AZURE_RESOURCE_GROUP)"
              export AZURE_ML_WORKSPACE="$(AZURE_ML_WORKSPACE)"
              
              cd mlops/deployment
              python deploy_model.py
            displayName: 'Deploy Models'
            env:
              AZURE_SUBSCRIPTION_ID: $(AZURE_SUBSCRIPTION_ID)
              AZURE_RESOURCE_GROUP: $(AZURE_RESOURCE_GROUP)
              AZURE_ML_WORKSPACE: $(AZURE_ML_WORKSPACE)

          - script: |
              echo "Getting endpoint information..."
              bash scripts/get-model-endpoints.sh nsfw-detector
              bash scripts/get-model-endpoints.sh violence-detector
            displayName: 'Get Endpoint Information'
            env:
              AZURE_RESOURCE_GROUP: $(AZURE_RESOURCE_GROUP)
              AZURE_ML_WORKSPACE: $(AZURE_ML_WORKSPACE)
            continueOnError: true
```

3. Click **"Commit"**

#### Step 2.4.2: Create Deployment Pipeline
1. Go to **Pipelines** → **Pipelines**
2. Click **"Create Pipeline"**
3. Select your repository
4. Select **"Existing Azure Pipelines YAML file"**
5. Path: `azure-pipelines-ml-deployment.yml`
6. Click **"Continue"** → **"Save"** (don't run yet)

---

## Part 3: Integration & Automation (1 hour)

### Phase 3.1: Connect Training → Deployment Pipeline

#### Step 3.1.1: Update Training Pipeline to Trigger Deployment
1. Edit `azure-pipelines-ml-training.yml`
2. Add at the end (after TrainViolenceModel job):

```yaml
  - stage: TriggerDeployment
    displayName: 'Trigger Model Deployment'
    dependsOn: TrainModels
    condition: succeeded()
    jobs:
      - job: TriggerDeploy
        displayName: 'Trigger Deployment Pipeline'
        steps:
          - task: TriggerPipeline@1
            displayName: 'Trigger ML Deployment Pipeline'
            inputs:
              serviceConnection: 'guardian-azure-connection'
              project: 'guardian-ai-mlops'
              pipelineId: <deployment-pipeline-id>  # Get from deployment pipeline URL
              branch: 'main'
```

**Note**: To get pipeline ID:
1. Go to your deployment pipeline
2. Click on it
3. Look at the URL: `https://dev.azure.com/org/project/_build?definitionId=<ID>`
4. Copy the `<ID>` number

#### Step 3.1.2: Alternative: Use Pipeline Completion Trigger
Instead of TriggerPipeline task, you can use Azure DevOps UI:
1. Go to **Pipelines** → **Pipelines**
2. Click on your **deployment pipeline**
3. Click **"..."** → **"Edit"**
4. Click **"Triggers"** (top right)
5. Enable **"Build completion"**
6. Select your **training pipeline**
7. Click **"Save"**

---

### Phase 3.2: Update Application After Model Deployment

When models are deployed, update the ConfigMap with new endpoint URLs.

#### Step 3.2.1: Create Update ConfigMap Script
1. Create new file: `scripts/update-model-endpoints-in-k8s.sh`
2. Copy the following:

```bash
#!/bin/bash
set -e

# Script to update Kubernetes ConfigMap with Azure ML endpoint URLs
# Usage: ./scripts/update-model-endpoints-in-k8s.sh

echo "🔍 Getting Azure ML endpoint information..."

# Get NSFW endpoint
NSFW_ENDPOINT=$(az ml online-endpoint show \
  --name nsfw-detector-endpoint \
  --resource-group guardian-ai-prod \
  --workspace-name guardian-ai-ml-workspace-prod \
  --query scoring_uri -o tsv 2>/dev/null || echo "")

# Get Violence endpoint
VIOLENCE_ENDPOINT=$(az ml online-endpoint show \
  --name violence-detector-endpoint \
  --resource-group guardian-ai-prod \
  --workspace-name guardian-ai-ml-workspace-prod \
  --query scoring_uri -o tsv 2>/dev/null || echo "")

# Get endpoint key (same for both endpoints)
ENDPOINT_KEY=$(az ml online-endpoint get-credentials \
  --name nsfw-detector-endpoint \
  --resource-group guardian-ai-prod \
  --workspace-name guardian-ai-ml-workspace-prod \
  --query primaryKey -o tsv 2>/dev/null || echo "")

if [ -z "$NSFW_ENDPOINT" ] || [ -z "$VIOLENCE_ENDPOINT" ]; then
  echo "❌ Could not retrieve endpoint information"
  exit 1
fi

echo "✅ Updating ConfigMap..."
kubectl create configmap guardian-config \
  --from-literal=NSFW_MODEL_ENDPOINT="$NSFW_ENDPOINT" \
  --from-literal=VIOLENCE_MODEL_ENDPOINT="$VIOLENCE_ENDPOINT" \
  --from-literal=MODEL_ENDPOINT_KEY="$ENDPOINT_KEY" \
  --dry-run=client -o yaml | \
  kubectl apply -f - -n production

echo "✅ Restarting deep-vision pods..."
kubectl rollout restart deployment/deep-vision -n production

echo "✅ ConfigMap updated and pods restarted!"
```

3. Make it executable: `chmod +x scripts/update-model-endpoints-in-k8s.sh`
4. Commit the file

#### Step 3.2.2: Add to Deployment Pipeline
Edit `azure-pipelines-ml-deployment.yml`, add after "Get Endpoint Information" step:

```yaml
          - task: Kubernetes@1
            displayName: 'Update ConfigMap with endpoints'
            inputs:
              connectionType: 'Kubernetes Service Connection'
              kubernetesServiceEndpoint: 'guardian-aks-connection'
              namespace: 'production'
              command: 'apply'
              arguments: '-f k8s/configmap.yaml'
            continueOnError: true

          - script: |
              bash scripts/update-model-endpoints-in-k8s.sh
            displayName: 'Update Model Endpoints in K8s'
            env:
              AZURE_RESOURCE_GROUP: $(AZURE_RESOURCE_GROUP)
              AZURE_ML_WORKSPACE: $(AZURE_ML_WORKSPACE)
```

---

## Part 4: Testing & Validation (30 minutes)

### Phase 4.1: Test Application CI/CD Pipeline

#### Step 4.1.1: Trigger Build
1. Make a small change to any service file (e.g., add a comment)
2. Commit and push to `main` branch
3. Go to **Pipelines** → **Pipelines**
4. Watch the pipeline run
5. Verify:
   - ✅ Build stage completes
   - ✅ Images pushed to ACR
   - ✅ Deploy stage completes
   - ✅ Services updated in AKS

#### Step 4.1.2: Verify Deployment
```bash
# Check pods are running
kubectl get pods -n production

# Check deployment images
kubectl get deployment -n production -o jsonpath='{.items[*].spec.template.spec.containers[*].image}'

# Check logs
kubectl logs -l app=deep-vision -n production --tail=20
```

---

### Phase 4.2: Test ML Training Pipeline

#### Step 4.2.1: Manual Trigger
1. Go to **Pipelines** → **Pipelines**
2. Click on your **ML Training Pipeline**
3. Click **"Run pipeline"**
4. Select branch: `main`
5. Click **"Run"**

#### Step 4.2.2: Monitor Training
1. In Azure Portal, go to **Azure ML Workspace**
2. Go to **Jobs** (or **Experiments**)
3. Watch the training job progress
4. Check metrics and logs
5. Verify model is registered in **Models** section

---

### Phase 4.3: Test ML Deployment Pipeline

#### Step 4.3.1: Trigger Deployment
1. After training completes, go to **ML Deployment Pipeline**
2. Click **"Run pipeline"**
3. Click **"Run"**

#### Step 4.3.2: Verify Deployment
1. In Azure Portal, go to **Azure ML Workspace**
2. Go to **Endpoints**
3. Verify endpoints are created:
   - `nsfw-detector-endpoint`
   - `violence-detector-endpoint`
4. Check endpoint status: **Healthy**
5. Test endpoint (optional):
   ```bash
   # Get endpoint URL and key
   az ml online-endpoint show --name nsfw-detector-endpoint --resource-group guardian-ai-prod --workspace-name guardian-ai-ml-workspace-prod --query scoring_uri -o tsv
   
   # Test with curl (replace with actual values)
   curl -X POST <endpoint-url> \
     -H "Authorization: Bearer <key>" \
     -H "Content-Type: application/json" \
     -d '{"image": "<base64-encoded-image>"}'
   ```

---

## Part 5: Advanced Configuration (Optional)

### Phase 5.1: Schedule Model Retraining

#### Step 5.1.1: Add Scheduled Trigger
1. Edit `azure-pipelines-ml-training.yml`
2. Add trigger section:

```yaml
trigger: none

schedules:
  - cron: "0 2 * * 0"  # Every Sunday at 2 AM UTC
    displayName: 'Weekly Model Retraining'
    branches:
      include:
        - main
    always: true
```

This will retrain models every Sunday at 2 AM UTC.

---

### Phase 5.2: Model Versioning & Rollback

#### Step 5.2.1: Tag Models in Pipeline
Add to training pipeline after training:

```yaml
- script: |
    # Tag model with version
    az ml model create \
      --name nsfw-detector \
      --version $(Build.BuildId) \
      --resource-group $(AZURE_RESOURCE_GROUP) \
      --workspace-name $(AZURE_ML_WORKSPACE) \
      --tags "pipeline_run=$(Build.BuildId)" "date=$(Build.BuildDate)"
  displayName: 'Tag Model Version'
```

#### Step 5.2.2: Rollback Script
Your `mlops/deployment/rollback_model.py` script is ready. You can trigger it manually or add to pipeline.

---

### Phase 5.3: Monitoring & Alerts

#### Step 5.3.1: Set Up Pipeline Notifications
1. In Azure DevOps, go to **Project Settings** → **Notifications**
2. Click **"+ New subscription"**
3. Select **"A build completes"**
4. Choose your pipelines
5. Add email/Slack webhook
6. Click **"Save"**

#### Step 5.3.2: Monitor Model Performance
1. In Azure ML Workspace, go to **Endpoints**
2. Click on an endpoint
3. Go to **Metrics** tab
4. Monitor:
   - Request latency
   - Request count
   - Error rate
   - CPU/Memory usage

---

## Troubleshooting

### Common Issues

#### Issue 1: Pipeline Fails with "Service Connection Not Found"
**Solution**: 
1. Go to **Project Settings** → **Service connections**
2. Verify connection names match pipeline YAML
3. Check connection has proper permissions

#### Issue 2: Docker Build Fails
**Solution**:
1. Check Dockerfile syntax
2. Verify build context paths are correct
3. Check ACR connection is working: `az acr login --name guardianacr58206`

#### Issue 3: Kubernetes Deployment Fails
**Solution**:
1. Verify AKS connection
2. Check namespace exists: `kubectl get namespace production`
3. Verify service account permissions

#### Issue 4: ML Training Fails
**Solution**:
1. Check compute cluster is running
2. Verify Python dependencies in requirements.txt
3. Check Azure ML workspace permissions
4. Review training job logs in Azure ML Studio

#### Issue 5: Model Deployment Fails
**Solution**:
1. Verify model exists in registry: `az ml model list --workspace-name guardian-ai-ml-workspace-prod`
2. Check endpoint quota limits
3. Verify compute instance type is available in your region

---

## Cost Optimization Tips

### Azure DevOps
- **Free tier**: 1,800 minutes/month (usually enough for learning)
- **Paid**: $0.008/minute after free tier
- **Tip**: Use manual triggers for ML pipelines to save minutes

### Azure ML
- **Compute clusters**: Pay only when running (scale to zero)
- **Endpoints**: Pay per hour when receiving traffic
- **Tip**: Delete endpoints when not testing to save costs
- **Tip**: Use CPU clusters instead of GPU for learning (10x cheaper)

### Estimated Monthly Costs
- **Azure DevOps**: $0-20/month (depending on usage)
- **Azure ML Compute**: $0-50/month (only when training)
- **Azure ML Endpoints**: $0-100/month (only when receiving traffic)
- **Total**: $0-170/month (mostly pay-per-use)

---

## Next Steps After Setup

### Immediate Next Steps
1. ✅ Test application CI/CD pipeline (make a code change, verify auto-deploy)
2. ✅ Test ML training pipeline (manual trigger)
3. ✅ Test ML deployment pipeline (after training)
4. ✅ Verify endpoints are updated in ConfigMap
5. ✅ Test video upload with new models

### Future Enhancements
- **A/B Testing**: Deploy challenger models alongside champion
- **Drift Detection**: Monitor model performance over time
- **Automated Retraining**: Trigger retraining when accuracy drops
- **Multi-Region Deployment**: Deploy to multiple Azure regions
- **Advanced Monitoring**: Set up Application Insights dashboards

---

## Summary Checklist

### Azure DevOps Setup
- [ ] Organization created
- [ ] Project created
- [ ] Repository imported/connected
- [ ] Service connections created (Azure, ACR, AKS)
- [ ] Self-hosted agent configured and online
- [ ] Application CI/CD pipeline created and tested
- [ ] ML training pipeline created
- [ ] ML deployment pipeline created
- [ ] Pipelines integrated (training → deployment)

### Azure ML Setup
- [ ] Workspace created/verified
- [ ] CPU compute cluster created
- [ ] GPU compute cluster created (optional)
- [ ] Training pipeline tested
- [ ] Models registered in workspace
- [ ] Endpoints deployed and healthy
- [ ] ConfigMap updated with endpoint URLs

### Validation
- [ ] Application CI/CD works (code change → auto-deploy)
- [ ] ML training pipeline works (manual trigger)
- [ ] ML deployment pipeline works (after training)
- [ ] Endpoints accessible and responding
- [ ] Application using new models (check logs)

---

## Quick Reference

### Pipeline Files Created
- `azure-pipelines-app-ci-cd.yml` - Application services CI/CD
- `azure-pipelines-ml-training.yml` - ML model training
- `azure-pipelines-ml-deployment.yml` - ML model deployment

### Service Connections
- `guardian-azure-connection` - Azure Resource Manager
- `guardian-acr-connection` - Azure Container Registry
- `guardian-aks-connection` - Azure Kubernetes Service

### Key URLs
- **Azure DevOps**: `https://dev.azure.com/<org>/<project>`
- **Azure ML Studio**: `https://ml.azure.com`
- **Azure Portal**: `https://portal.azure.com`

---

**Status**: ✅ Complete MLOps Integration Guide
**Time**: 4-6 hours (first-time setup)
**Cost**: $0-170/month (pay-per-use)

🚀 **Your complete MLOps workflow is now ready!**
