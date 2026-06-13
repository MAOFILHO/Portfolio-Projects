# Minimal MLOps Implementation Guide

**🎯 Goal**: Wire up existing MLOps scripts with your application (minimal, learner-friendly approach)

**💰 Cost**: ~$0-50/month (only if using Azure ML endpoints)

**⏱️ Time**: 30 minutes

---

## Overview

This guide explains how to connect your existing MLOps scripts (`mlops/training/` and `mlops/deployment/`) with your running application. This is a **minimal implementation** designed for learning purposes.

### What This Guide Covers
- ✅ Wiring model endpoints into the application
- ✅ Using trained models alongside CLIP detection
- ✅ Helper scripts for endpoint management
- ✅ Configuration updates (ConfigMap, docker-compose)

### What This Guide Does NOT Cover
- ❌ Automated CI/CD pipelines (see separate Azure DevOps guide)
- ❌ Advanced MLOps features (A/B testing, drift detection)
- ❌ Model retraining automation
- ❌ Complex ML pipelines

---

## Current State

### What's Already Working
- ✅ Deep-vision service has code to call Azure ML endpoints (lines 249-259 in `app.py`)
- ✅ MLOps training scripts exist (`mlops/training/train_nsfw_model.py`)
- ✅ MLOps deployment scripts exist (`mlops/deployment/deploy_model.py`)
- ✅ System works with CLIP-only detection (default, no configuration needed)

### What Was Missing (Now Fixed)
- ✅ Model endpoint environment variables added to ConfigMap
- ✅ Model endpoint environment variables added to docker-compose.yml
- ✅ Helper script to get endpoints after deployment
- ✅ Fixed rollback script to use environment variables

---

## Quick Start: 4-Step Process

### Step 1: Setup Azure ML Workspace (One-time)
```bash
bash scripts/setup-mlops.sh
```

### Step 2: Train Models (Optional)
```bash
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_RESOURCE_GROUP="rg-guardian-ai-prod"
export AZURE_ML_WORKSPACE="guardian-ml-workspace"
export MLFLOW_TRACKING_URI="azureml://your-workspace"

cd mlops/training
python train_nsfw_model.py
```

### Step 3: Deploy Models
```bash
cd mlops/deployment
python deploy_model.py
```

### Step 4: Update Configuration & Redeploy
```bash
# Get endpoint information
bash scripts/get-model-endpoints.sh nsfw-detector
bash scripts/get-model-endpoints.sh violence-detector

# Update ConfigMap (for Kubernetes) or .env (for local)
# Then restart deep-vision service
```

---

## Detailed Steps

### Step 1: Setup Azure ML Workspace

**Purpose**: Create Azure ML workspace for model registry and endpoints.

```bash
# Run setup script
bash scripts/setup-mlops.sh

# Verify
az ml workspace show \
  --name guardian-ml-workspace \
  --resource-group rg-guardian-ai-prod
```

**What it creates**:
- Azure ML workspace
- Application Insights component (optional)

**Cost**: ~$8/month (workspace base cost)

---

### Step 2: Train Models

**Purpose**: Train custom NSFW and violence detection models.

```bash
# Set environment variables
export AZURE_SUBSCRIPTION_ID="your-subscription-id"
export AZURE_RESOURCE_GROUP="rg-guardian-ai-prod"
export AZURE_ML_WORKSPACE="guardian-ml-workspace"
export MLFLOW_TRACKING_URI="azureml://your-workspace"

# Train models
cd mlops/training
python train_nsfw_model.py
```

**What happens**:
- Models are trained using PyTorch
- Models are registered in Azure ML model registry
- Training metrics are logged to MLflow

**Note**: The training script uses simulated data. Replace with your actual dataset for production use.

---

### Step 3: Deploy Models to Azure ML

**Purpose**: Deploy trained models as online endpoints.

```bash
cd mlops/deployment
python deploy_model.py
```

**Output**:
```
🎯 Guardian AI - Model Deployment Pipeline
==================================================
🚀 Deploying nsfw-detector to Azure ML...
🔧 Creating endpoint: nsfw-detector-endpoint
📊 Using model version: 1
🏆 Deploying champion model...
✅ Deployment successful!
🔗 Scoring URI: https://xxx.azureml.net/score
📊 Traffic split: {'champion': 90}

🎉 Deployment Summary:
  nsfw-detector: https://xxx.azureml.net/score
  violence-detector: https://xxx.azureml.net/score
```

**What happens**:
- Creates Azure ML online endpoints
- Deploys models to endpoints
- Returns scoring URIs and keys

**Cost**: ~$0.50-2/hour per endpoint (only when receiving traffic)

---

### Step 4: Get Endpoint Information

**Purpose**: Retrieve endpoint URIs and keys for configuration.

```bash
# Use helper script
bash scripts/get-model-endpoints.sh nsfw-detector

# Output:
# ✅ Endpoint Information:
# Scoring URI: https://xxx.azureml.net/score
# Endpoint Key: xxx
# 
# 📝 To update your ConfigMap or .env file, use these values:
# ...
```

**Alternative (manual)**:
```bash
az ml online-endpoint show \
  --name nsfw-detector-endpoint \
  --resource-group rg-guardian-ai-prod \
  --workspace-name guardian-ml-workspace \
  --query scoring_uri -o tsv

az ml online-endpoint get-credentials \
  --name nsfw-detector-endpoint \
  --resource-group rg-guardian-ai-prod \
  --workspace-name guardian-ml-workspace \
  --query primaryKey -o tsv
```

---

### Step 5: Update Configuration

#### Option A: Local Development (docker-compose.yml)

**Update `.env` file**:
```bash
NSFW_MODEL_ENDPOINT="https://xxx.azureml.net/score"
VIOLENCE_MODEL_ENDPOINT="https://xxx.azureml.net/score"
MODEL_ENDPOINT_KEY="your-endpoint-key"
```

**Restart service**:
```bash
docker-compose restart deep-vision
```

#### Option B: Kubernetes (ConfigMap)

**Update ConfigMap**:
```bash
kubectl edit configmap guardian-config -n production
```

**Add these lines**:
```yaml
  # Azure ML Model Endpoints (Optional - leave empty to use CLIP only)
  NSFW_MODEL_ENDPOINT: "https://xxx.azureml.net/score"
  VIOLENCE_MODEL_ENDPOINT: "https://xxx.azureml.net/score"
  MODEL_ENDPOINT_KEY: "your-endpoint-key"
```

**Restart deployment**:
```bash
kubectl rollout restart deployment/deep-vision -n production
```

---

### Step 6: Verify Integration

**Check logs**:
```bash
# Kubernetes
kubectl logs -l app=deep-vision -n production --tail=50 | grep -i "model endpoint"

# Local
docker-compose logs deep-vision | grep -i "model endpoint"
```

**Expected behavior**:
- If endpoints are set: Deep-vision combines CLIP (30%) + custom models (70%)
- If endpoints are empty: Deep-vision uses CLIP-only (default)
- If endpoints fail: System gracefully falls back to CLIP-only

---

## How It Works

### Without Azure ML Endpoints (Default)
```
Video Frame → CLIP Analysis → Scores → Policy Engine
```
- Uses CLIP model directly (loaded from HuggingFace)
- No external API calls
- Works immediately after deployment

### With Azure ML Endpoints (Optional)
```
Video Frame → CLIP Analysis (30%) + Azure ML Models (70%) → Combined Scores → Policy Engine
```
- Combines CLIP scores with custom model scores
- Custom models provide improved accuracy
- Falls back to CLIP-only if endpoints unavailable

### Code Flow (deep-vision/app.py)
```python
# Lines 249-259: Check if endpoints are available
if NSFW_ENDPOINT:
    nsfw_custom = await call_model_endpoint(NSFW_ENDPOINT, img)
    
# Lines 263-271: Combine scores
if nsfw_custom > 0 or violence_custom > 0:
    # Custom models available - combine with CLIP
    nsfw_score = (nsfw_custom * 0.7 + clip_nsfw * 0.3)
else:
    # No custom models - use CLIP only
    nsfw_score = clip_nsfw * 0.85
```

---

## Helper Scripts

### get-model-endpoints.sh
**Purpose**: Get endpoint URIs and keys after deployment.

**Usage**:
```bash
bash scripts/get-model-endpoints.sh nsfw-detector
bash scripts/get-model-endpoints.sh violence-detector
```

**Output**: Prints scoring URI and key, plus instructions for updating ConfigMap/.env

### rollback_model.py
**Purpose**: Rollback to previous model version if new version has issues.

**Usage**:
```bash
python mlops/deployment/rollback_model.py nsfw-detector
python mlops/deployment/rollback_model.py violence-detector
```

**What it does**: Switches traffic from current deployment to previous deployment

---

## Troubleshooting

### Endpoints Not Found
**Error**: `Endpoint 'nsfw-detector-endpoint' not found`

**Solution**: Make sure you've deployed models first:
```bash
cd mlops/deployment
python deploy_model.py
```

### Endpoints Not Being Called
**Symptom**: Logs show CLIP-only scores, no "Model endpoint" messages

**Solution**: 
1. Check ConfigMap/.env has endpoint URLs set
2. Verify endpoints are accessible (test with curl)
3. Check endpoint keys are correct
4. Restart deep-vision service

### Endpoint Calls Failing
**Symptom**: Logs show "Model endpoint error"

**Solution**:
1. Verify endpoint is running: `az ml online-endpoint show --name nsfw-detector-endpoint`
2. Check endpoint key is correct
3. Verify network connectivity (if using Kubernetes)
4. System will fall back to CLIP-only automatically

---

## Cost Considerations

### Without Azure ML Endpoints
- **Cost**: $0/month (uses CLIP only)
- **Accuracy**: Good (CLIP is pre-trained and effective)

### With Azure ML Endpoints
- **Workspace**: ~$8/month (base cost)
- **Endpoints**: ~$0.50-2/hour when receiving traffic
- **Training**: Pay-per-use compute (only when training)
- **Total**: ~$20-50/month (depending on traffic)

**Recommendation**: Start with CLIP-only (free), add Azure ML endpoints when you need improved accuracy.

---

## Next Steps

### For Production CI/CD
See separate documentation for:
- Azure DevOps pipelines (automated builds/deployments)
- Azure ML Pipelines (automated training/deployment)
- Model monitoring and drift detection
- A/B testing workflows

### For Advanced MLOps
- Automated retraining triggers
- Model versioning strategies
- Performance monitoring dashboards
- Cost optimization techniques

---

## Summary

This minimal MLOps implementation provides:
- ✅ **Simple**: 4-step process to connect models
- ✅ **Optional**: Works without Azure ML (CLIP-only)
- ✅ **Learner-friendly**: No complex pipelines or automation
- ✅ **Production-ready**: Can be extended with CI/CD later

**Key Takeaway**: The system works great with CLIP-only detection. Azure ML endpoints are optional enhancements for improved accuracy.

---

**Status**: ✅ Minimal MLOps Integration Complete
**Time**: 30 minutes
**Cost**: $0-50/month (optional)
