# Compute Cluster Training Workflow Guide

**🎯 Goal**: Complete workflow from committing code changes to monitoring training jobs in Azure ML workspace

---

## Step 1: Git Workflow (Commit & Push Changes)

### 1.1 Review Changes
```bash
cd /Users/chenkonsam/Projects/MLOps_Project

# Check what files have changed
git status

# Review the changes
git diff azure-pipelines-ml-training.yml
git diff mlops/training/submit_training_job.py
```

### 1.2 Stage Changes
```bash
# Add the new job submission script
git add mlops/training/submit_training_job.py

# Add the updated pipeline file
git add azure-pipelines-ml-training.yml

# Verify staged files
git status
```

### 1.3 Commit Changes
```bash
git commit -m "Refactor training pipeline to use Azure ML compute clusters

- Add submit_training_job.py for job submission to compute cluster
- Update azure-pipelines-ml-training.yml to submit jobs instead of running locally
- Training now executes on cpu-training-cluster instead of pipeline agent
- Improved scalability and resource isolation"
```

### 1.4 Push to Both Remotes
```bash
# Push to GitHub (origin)
git push origin main

# Push to Azure DevOps (azure-devops)
git push azure-devops main
```

**Note**: If you have a git alias configured (`git pushall`), you can use:
```bash
git pushall
```

---

## Step 2: Verify Compute Cluster is Ready

### 2.1 Check Compute Cluster Status (Azure Portal)
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **Azure Machine Learning** → Your workspace (`guardian-ai-ml-workspace-prod`)
3. Go to **Compute** → **Compute clusters**
4. Verify `cpu-training-cluster` exists and is in **Running** state
5. If not running, click on the cluster → **Start**

### 2.2 Verify via Azure CLI (Alternative)
```bash
# Login to Azure (if not already)
az login

# Set subscription
az account set --subscription <your-subscription-id>

# Check compute cluster status
az ml compute show \
  --name cpu-training-cluster \
  --workspace-name guardian-ai-ml-workspace-prod \
  --resource-group guardian-ai-prod \
  --query "provisioningState"
```

Expected output: `"Succeeded"`

---

## Step 3: Run the Training Pipeline in Azure DevOps

### 3.1 Navigate to Pipeline
1. Go to [Azure DevOps Portal](https://dev.azure.com)
2. Select your organization → project (`guardian-ai-mlops`)
3. Go to **Pipelines** → **Pipelines**
4. Find `azure-pipelines-ml-training.yml` pipeline

### 3.2 Run Pipeline
1. Click on the pipeline
2. Click **"Run pipeline"** button (top right)
3. Select branch: `main` (or your branch)
4. Click **"Run"**

### 3.3 Monitor Pipeline Execution
The pipeline will:
1. ✅ **Setup Python** - Detect and configure Python on agent
2. ✅ **Install dependencies** - Install `azure-ai-ml` and `azure-identity`
3. ✅ **Azure Login** - Authenticate with Azure
4. ✅ **Submit NSFW Training Job** - Call `submit_training_job.py` for NSFW model
5. ✅ **Submit Violence Training Job** - Call `submit_training_job.py` for violence model

**Expected Timeline**:
- Pipeline agent steps: ~2-5 minutes
- Job submission: ~30 seconds per job
- Job execution on compute cluster: ~10-30 minutes (depending on training duration)

---

## Step 4: Monitor Jobs in Azure ML Workspace

### 4.1 View Jobs in Azure Portal
1. Go to **Azure Machine Learning** → Your workspace
2. Navigate to **Jobs** (left sidebar)
3. You should see two new jobs:
   - `nsfw-training-<timestamp>`
   - `violence-training-<timestamp>`

### 4.2 Job Status Indicators
- 🟡 **Queued** - Job is waiting for compute resources
- 🔵 **Running** - Job is executing on compute cluster
- 🟢 **Completed** - Job finished successfully
- 🔴 **Failed** - Job encountered an error

### 4.3 View Job Details
1. Click on a job name
2. View tabs:
   - **Overview** - Job summary, status, duration
   - **Outputs + logs** - Training logs, stdout, stderr
   - **Metrics** - MLflow metrics (loss, accuracy, etc.)
   - **Code** - Uploaded training code
   - **Environment** - Docker environment used

### 4.4 Monitor Training Progress
In the **Outputs + logs** tab:
- Look for MLflow logging messages
- Check for "✅ Training complete!" messages
- Verify model registration success

---

## Step 5: Verify MLflow Tracking

### 5.1 View Experiments in Azure ML Studio
1. Go to **Azure Machine Learning Studio**: `https://ml.azure.com`
2. Select your workspace
3. Navigate to **Experiments** (left sidebar)
4. You should see:
   - `nsfw-detection` experiment
   - `violence-detection` experiment

### 5.2 View Runs
1. Click on an experiment name
2. View all runs (training jobs)
3. Click on a run to see:
   - **Metrics** - Training metrics over time
   - **Parameters** - Hyperparameters used
   - **Artifacts** - Saved models
   - **Tags** - Model metadata

### 5.3 Verify Model Registration
1. Go to **Models** (left sidebar)
2. Look for registered models:
   - `nsfw-detector`
   - `violence-detector`
3. Check model versions and metadata

---

## Step 6: Troubleshooting (If Jobs Fail)

### 6.1 Common Issues

#### Issue: "Compute cluster not found"
**Solution**:
- Verify cluster name matches `COMPUTE_CLUSTER` variable in pipeline
- Check cluster exists in Azure ML workspace
- Ensure cluster is in "Succeeded" provisioning state

#### Issue: "Environment not found"
**Solution**:
- The script tries to use curated PyTorch environments
- Falls back to base Python environment if not found
- Check job logs for environment details

#### Issue: "Import errors" (train_violence_model.py)
**Solution**:
- Both training scripts are uploaded together
- Import should work since files are in same directory
- Check job logs for specific import error

#### Issue: "MLflow authentication failed"
**Solution**:
- Environment variables are passed correctly to job
- `DefaultAzureCredential` should work on compute cluster
- Check job logs for authentication errors

### 6.2 View Detailed Logs
1. In Azure ML Studio → **Jobs** → Select failed job
2. Go to **Outputs + logs** tab
3. Check:
   - `user_logs/std_log.txt` - Standard output
   - `user_logs/std_err.txt` - Error output
   - `system_logs/execution.log` - System logs

### 6.3 Re-run Failed Jobs
- Option 1: Re-run from Azure DevOps pipeline
- Option 2: Re-submit manually:
  ```bash
  cd mlops/training
  python submit_training_job.py \
    --model-type nsfw \
    --subscription-id <your-sub-id> \
    --resource-group guardian-ai-prod \
    --workspace-name guardian-ai-ml-workspace-prod \
    --compute-cluster cpu-training-cluster
  ```

---

## Step 7: Next Steps After Successful Training

### 7.1 Verify Models are Registered
- Check Azure ML Studio → **Models**
- Verify both models are registered with latest versions

### 7.2 Run Deployment Pipeline
Once training is successful:
1. Go to Azure DevOps → **Pipelines**
2. Run `azure-pipelines-ml-deployment.yml`
3. This will deploy models to Azure ML endpoints

### 7.3 Test Model Endpoints
- Use the deployment pipeline or manually deploy:
  ```bash
  cd mlops/deployment
  python deploy_model.py --model-name nsfw-detector
  python deploy_model.py --model-name violence-detector
  ```

---

## Summary Checklist

- [ ] ✅ Committed changes to Git
- [ ] ✅ Pushed to GitHub (origin)
- [ ] ✅ Pushed to Azure DevOps (azure-devops)
- [ ] ✅ Verified compute cluster is running
- [ ] ✅ Ran training pipeline in Azure DevOps
- [ ] ✅ Monitored pipeline execution
- [ ] ✅ Verified jobs submitted to Azure ML
- [ ] ✅ Checked job status in Azure ML Studio
- [ ] ✅ Viewed training logs and metrics
- [ ] ✅ Verified models registered in MLflow
- [ ] ✅ Ready for deployment pipeline

---

## Key Differences: Before vs After

### Before (Local Execution)
- Training runs on Azure DevOps agent
- Agent must have all dependencies installed
- Limited compute resources
- Agent tied up during training

### After (Compute Cluster)
- Training runs on dedicated Azure ML compute cluster
- Scalable compute resources
- Agent only submits jobs (fast)
- Better resource isolation
- Jobs visible in Azure ML Studio
- Better monitoring and logging

---

## Additional Resources

- [Azure ML Compute Clusters Documentation](https://learn.microsoft.com/en-us/azure/machine-learning/concept-compute-target#azure-machine-learning-compute-cluster)
- [Azure ML Jobs Documentation](https://learn.microsoft.com/en-us/azure/machine-learning/concept-azure-machine-learning-architecture#jobs)
- [MLflow with Azure ML](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-mlflow)
