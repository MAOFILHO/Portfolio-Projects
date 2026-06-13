# Guardian AI — MultiCloud MLOps Video Content Moderation

A production-grade, end-to-end MLOps application for automated video content moderation. Built on **Azure AKS** (Kubernetes) + **AWS** (S3, SQS, DynamoDB) with **Azure ML** for NSFW and Violence detection model training and deployment to a fully automated Python/CLI deployment pipeline.

---

## Business Scenario

**Problem:** You are working with a content moderation team that must review large volumes of video uploads
for **policy compliance**. Manually reviewing every video is **slow and inconsistent**. 

**The Challenge:** To scale and standardize decisions, you need to **automate model training and deployment**: 
train NSFW and violence-detection models on scalable compute, register and version them, deploy to managed
inference endpoints, and have application services (which store videos and metadata on AWS)
call those endpoints for real-time scoring. 

**The Solution:** You will use **Azure** for the ML platform and **AWS** for data
and messaging, with **Azure DevOps** pipelines orchestrating training and deployment so that new
model versions flow from code commit to production endpoints.

---

## Project Description

In this project, you will learn how to orchestrate a **Multi-Cloud MLOps Workflow**. Azure ML provides
the workspace, compute clusters for training, a model registry for versioning, and managed
online endpoints for inference. **Azure DevOps runs CI/CD pipelines** that submit training jobs to the
cluster (instead of the pipeline agent), register trained models automatically, and deploy them to
online endpoints. MLflow tracks experiments and metrics with an Azure ML backend. 

Application microservices (e.g., Deep-Vision) run on **Azure Kubernetes Service (AKS)**, read
video references from **AWS S3** and metadata from **AWS DynamoDB**, process messages from SQS,
and call **Azure ML endpoints** for model scoring. You will push code to the repository, run the
training pipeline to train on the compute cluster, see models appear in the registry, run the
deployment pipeline, create or update endpoints, and update Kubernetes ConfigMaps
so application pods use the new scoring URIs. This end-to-end flow demonstrates automated,
reproducible model training and deployment across **AWS (data/messaging)** and **Azure (ML
platform and CI/CD)**.

---

## Cross-Cloud Integration – Data on AWS, ML on Azure

**The Architecture:** Keeps data and messaging on **AWS** and ML training, registry, and inference on **Azure**. Application services (on AKS or elsewhere) use AWS for S3, SQS, and DynamoDB, and use Azure only for calling the ML endpoints and for CI/CD (Azure DevOps and Azure ML).

**Definition**: Separation of responsibilities: **AWS** for storage, queues, and application metadata; **Azure** for ML workspace, compute, registry, endpoints, and pipeline orchestration; application code connects both via configuration (endpoint URLs, keys, and AWS credentials).

**Use Case**: Optimize cost and capability, use **AWS** for high-scale object storage and queues, and **Azure** for a full-featured ML platform and managed endpoints; keep a single application codebase that talks to both clouds via environment variables and SDKs.

**Example**: Video upload → **S3 + DynamoDB (AWS)**; processing triggered by SQS (AWS); **Deep-Vision** runs on AKS, reads from S3/DynamoDB, calls Azure ML endpoints for scores, writes results back to DynamoDB; training and deployment are fully on Azure via **Azure DevOps** and **Azure ML**.


---

## Architecture


<img width="1536" height="1024" alt="image (7)" src="https://github.com/user-attachments/assets/39e3f683-7fe2-4e2c-b6e4-6749a2d754e4" />

```
Upload → API Gateway → Ingestion (S3) → SQS → Fast Screening
                                                     ↓
                                              Deep Vision (ML)
                                                     ↓
                                         Policy Engine → Decision
                                                     ↓
                                    Auto-Approve / Auto-Reject / Human Review
```

**AWS** (us-east-1):
- S3: video storage (`guardian-videos-*`)
- SQS: `guardian-video-processing`, `guardian-gpu-processing`
- DynamoDB: `guardian-videos`, `guardian-events`

**Azure** (East US):
- AKS: 4-node cluster (`Standard_D2s_v3`) running 8 microservices
- ACR: Docker image registry
- Azure ML: NSFW + Violence detection model training & deployment
- Azure DevOps: CI/CD pipelines (3 pipelines)


---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://python.org) |
| AWS CLI | v2 | `brew install awscli` |
| Azure CLI | latest | `brew install azure-cli` |
| kubectl | latest | `brew install kubectl` |
| Helm | 3+ | `brew install helm` |
| Docker Desktop | latest | [docker.com](https://docker.com) |
| Node.js | 20+ | `brew install node` |
| git | any | pre-installed on macOS |

---


## Project Structure

```
MultiCloud_MLOps/
├── setup.py                          # Main orchestrator (run this)
├── .env.example                      # Environment variables template
├── requirements.txt                  # Python dependencies
│
├── automation/                       # Stage automation scripts
│   ├── config.py                     # Central config, reads .env
│   ├── aws/setup_aws.py             # Stage: aws
│   ├── azure/
│   │   ├── setup_azure.py           # Stage: azure
│   │   └── build_images.py          # Stage: images
│   ├── k8s/deploy_k8s.py            # Stage: k8s
│   ├── devops/setup_devops.py       # Stage: devops
│   ├── ml/setup_ml.py               # Stage: ml
│   └── utils/shell.py               # CLI runner, logging
│
├── scripts/
│   └── setup-aws.sh                 # AWS resource creation (called by aws stage)
│
├── services/                        # Microservice source code
│   ├── ingestion/                   # Video upload & S3 storage
│   ├── fast-screening/              # Quick ML screening
│   ├── deep-vision/                 # Deep learning analysis
│   ├── policy-engine/               # Decision logic
│   ├── human-review/                # Manual review interface
│   ├── notification/                # Alerting service
│   └── api-gateway/                 # REST API gateway
│
├── frontend/                        # React TypeScript UI
├── k8s/                             # Kubernetes manifests
├── mlops/
│   ├── training/                    # Model training scripts
│   └── deployment/                  # Model deployment scripts
│
├── azure-pipelines-app-ci-cd.yml    # App CI/CD pipeline
├── azure-pipelines-ml-training.yml  # ML training pipeline
├── azure-pipelines-ml-deployment.yml # ML deployment pipeline
│
├── tests/smoke/test_smoke.py        # 69 smoke tests
└── aws_resource_cleanup.sh          # AWS teardown script
```


---

## Cost Estimates

| Resource | Monthly Cost |
|----------|-------------|
| AKS (4x Standard_D2s_v3) | ~$280 |
| Azure ML compute (cpu-training-cluster, 0 min instances) | ~$0 (scales to 0) |
| ACR Standard | ~$5 |
| S3 + SQS + DynamoDB (light usage) | ~$5 |
| **Total** | **~$290/month** |

> ⚠️ **Cost Warning**: AKS nodes run 24/7. Stop the cluster when not in use:
> ```bash
> az aks stop --name guardian-ai-aks --resource-group guardian-ai-prod
> az aks start --name guardian-ai-aks --resource-group guardian-ai-prod
> ```

---


## Quick Start

### 1. Clone and Configure


```bash
# If using as a standalone project:
git clone https://github.com/MAOFILHO/Portfolio-Projects.git
cd Portfolio-Projects/MultiCloud_MLOps

# Install Python dependencies
python3.11 -m venv .venv
source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env with your values (see CONFIGURATION section below)
```

### 2. Configure AWS

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region: us-east-1, Output: json
```

### 3. Configure Azure

```bash
az login
az account set --subscription <YOUR_SUBSCRIPTION_ID>
```

### 4. Run Automated Setup (Stages)

```bash
python setup.py --stage aws      # ~2 min:   S3, SQS, DynamoDB
python setup.py --stage azure    # ~15 min:  RG, ACR, AKS, NGINX
python setup.py --stage images   # ~20 min:  Docker build & push (8 images)
python setup.py --stage k8s      # ~5 min:   Deploy all services to AKS
python setup.py --stage devops   # ~5 min:   Azure DevOps pipelines
python setup.py --stage ml       # ~45 min:  Azure ML training + deployment
```

After `--stage k8s` completes, the app is live at: `http://<EXTERNAL_IP>`

---

## Configuration

Copy `.env.example` to `.env` and fill in all `<YOUR_VALUE>` placeholders:

<img width="1290" height="760" alt="Screenshot 2026-06-13 at 10 49 25 AM" src="https://github.com/user-attachments/assets/f7cf65f9-4795-43ff-b305-03ae79f0bfda" />


### AWS Credentials
```bash
AWS_ACCESS_KEY_ID=<from IAM user>
AWS_SECRET_ACCESS_KEY=<from IAM user>
AWS_REGION=us-east-1
```

### Azure Credentials
```bash
AZURE_SUBSCRIPTION_ID=<az account show --query id -o tsv>
```

### Azure Service Principal (required for DevOps)
```bash
# Create SP:
az ad sp create-for-rbac \
  --name guardian-ai-sp \
  --role Contributor \
  --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>

# Fill in output values:
AZURE_SP_APP_ID=<appId>
AZURE_SP_SECRET=<password>
AZURE_TENANT_ID=<tenant>
```

### Azure DevOps
```bash
AZDO_ORG_NAME=<your-org-name>     # from dev.azure.com/<ORG>
AZDO_PAT_TOKEN=<personal-access-token>
```
Generate PAT at: `https://dev.azure.com → Profile → Personal access tokens`  
Required scopes: Agent Pools, Build, Code, Project & Team, Service Connections, Variable Groups



## Stage Details

### Stage 1: AWS (`--stage aws`)
Creates: S3 bucket, 2 SQS queues, 2 DynamoDB tables  
Duration: ~2 minutes  
Region: **us-east-1** (hardcoded guard — will error if unconfigured)

<img width="970" height="716" alt="Screenshot 2026-06-12 at 6 19 28 PM" src="https://github.com/user-attachments/assets/0634cbd6-c7c1-4a47-bcee-4d6176ae524d" />


### Stage 2: Azure (`--stage azure`)
Creates: Resource group, ACR, AKS cluster (4 nodes), NGINX Ingress  
Duration: ~15 minutes (AKS is the long step)  
Output: External IP for the app

<img width="1009" height="710" alt="Screenshot 2026-06-12 at 6 21 24 PM" src="https://github.com/user-attachments/assets/8e7ab388-598d-48ba-b3c0-0a0d43b92cfb" />


### Stage 3: Docker Images (`--stage images`)
Builds and pushes 8 Docker images to ACR:
- `ingestion`, `fast-screening`, `deep-vision`, `policy-engine`
- `human-review`, `notification`, `api-gateway`, `frontend`  
Duration: ~20 minutes (first run; subsequent runs use layer cache)

<img width="1067" height="708" alt="Screenshot 2026-06-12 at 6 31 52 PM" src="https://github.com/user-attachments/assets/9562f432-7155-46c1-8dc5-661fa0398137" />

<img width="1069" height="710" alt="Screenshot 2026-06-12 at 6 32 32 PM" src="https://github.com/user-attachments/assets/060640bc-ee71-4d33-8b72-65afcf15b19c" />

### Stage 4: Kubernetes (`--stage k8s`)
Deploys: Namespace, ConfigMap, AWS secrets, all 8 services + Redis, Ingress  
Duration: ~5 minutes  
✅ App is live after this stage

<img width="987" height="698" alt="Screenshot 2026-06-13 at 11 37 43 AM" src="https://github.com/user-attachments/assets/89e41772-5888-4db3-bd57-765976054416" />

<img width="967" height="698" alt="Screenshot 2026-06-13 at 11 42 07 AM" src="https://github.com/user-attachments/assets/bc63b387-e617-45a4-9d42-1ea5445ed287" />


### Stage 5: DevOps (`--stage devops`)
Creates: Azure DevOps project, 3 service connections, variable group, 3 pipelines  
Duration: ~5 minutes  
Requires: `AZDO_PAT_TOKEN`, `AZURE_SP_APP_ID`, `AZURE_SP_SECRET`, `AZURE_TENANT_ID`

<img width="1027" height="717" alt="Screenshot 2026-06-12 at 9 56 33 PM" src="https://github.com/user-attachments/assets/b95000c8-d8ff-431a-8a5c-0c30fc30b1f8" />

<img width="1020" height="712" alt="Screenshot 2026-06-12 at 9 56 49 PM" src="https://github.com/user-attachments/assets/8cf77e36-c1e6-419b-aec6-205745805b9e" />



### Stage 6: ML (`--stage ml`)
Creates: Azure ML workspace, compute cluster, triggers training pipeline  
Duration: ~45 minutes (training on `cpu-training-cluster`)  
Output: NSFW + Violence detection endpoints; patches Kubernetes ConfigMap

<img width="993" height="401" alt="Screenshot 2026-06-13 at 11 44 25 AM" src="https://github.com/user-attachments/assets/09b45678-d46d-46f0-9a17-6571e1b2e296" />


---

## Running Tests

```bash
# Smoke tests (no cloud credentials required)
python -m pytest tests/smoke/test_smoke.py -v

# Expected: 69 tests passing
```

<img width="997" height="696" alt="Screenshot 2026-06-13 at 11 27 52 AM" src="https://github.com/user-attachments/assets/1363d851-7ab6-4d79-98f2-19fe55d9bcce" />


---

## The Video Moderation Application (Screenshots)

<img width="1425" height="749" alt="Screenshot 2026-06-12 at 7 14 59 PM" src="https://github.com/user-attachments/assets/21b47b9c-a765-410d-b884-e6ddeeee3e1e" />

<img width="1425" height="748" alt="Screenshot 2026-06-12 at 7 15 30 PM" src="https://github.com/user-attachments/assets/e3108378-abd4-4731-b7d1-bc896244c114" />

<img width="1423" height="738" alt="Screenshot 2026-06-12 at 7 21 29 PM" src="https://github.com/user-attachments/assets/b9641869-4736-4a23-a368-198d3fd7d64f" />

<img width="947" height="633" alt="Screenshot 2026-06-12 at 7 21 45 PM" src="https://github.com/user-attachments/assets/b9089802-cc87-4b84-8c0e-63c8291fe623" />

<img width="1106" height="747" alt="Screenshot 2026-06-12 at 7 22 09 PM" src="https://github.com/user-attachments/assets/0fc48727-5094-4ddd-8f40-5788ce14bbaa" />

<img width="955" height="644" alt="Screenshot 2026-06-12 at 7 24 39 PM" src="https://github.com/user-attachments/assets/f46df4af-4e39-4aae-a657-88d2af545359" />

<img width="1130" height="745" alt="Screenshot 2026-06-12 at 7 29 56 PM" src="https://github.com/user-attachments/assets/b2051f61-7e64-4ea2-8255-de98af82b185" />

<img width="1424" height="742" alt="Screenshot 2026-06-12 at 7 29 38 PM" src="https://github.com/user-attachments/assets/e9454af0-e98a-42c2-97de-9e5e6a17762d" />



---

## GitHub Actions CI/CD

A GitHub Actions workflow at `.github/workflows/guardian-ai-deploy.yml` automatically builds and deploys service images to AKS on every push to `MultiCloud_MLOps/services/**`.

### Required GitHub Secrets

Add at: `github.com/MAOFILHO/Portfolio-Projects → Settings → Secrets → Actions`

- `ACR_USERNAME` — run: `az acr credential show --name guardianacr03211 --query username -o tsv`
- `ACR_PASSWORD` — run: `az acr credential show --name guardianacr03211 --query 'passwords[0].value' -o tsv`
- `AZURE_CREDENTIALS` — run: `az ad sp create-for-rbac --name guardian-github-actions --role Contributor --scopes /subscriptions/960936b9-ecde-465b-be8d-776ca077dcd0 --sdk-auth`

<img width="1396" height="747" alt="Screenshot 2026-06-13 at 11 01 23 AM" src="https://github.com/user-attachments/assets/f5ba4661-b796-427f-936a-11d5bb19ac2f" />


### Trigger Automatically

Push any change to a service file and the workflow runs automatically.

<img width="1695" height="886" alt="Screenshot 2026-06-13 at 12 25 18 PM" src="https://github.com/user-attachments/assets/f027fb76-c835-4ea8-b54a-6cef2f71eda9" />


### Trigger Manually

GitHub UI: Actions tab → Guardian AI — Deploy to AKS → Run workflow

<img width="1432" height="379" alt="Screenshot 2026-06-13 at 9 51 23 AM" src="https://github.com/user-attachments/assets/31ea7939-2283-455c-afed-b1f098de4228" />


### Important Notes

- AKS must be running before deployment: `az aks start --name guardian-ai-aks --resource-group guardian-ai-prod`
- Workflow only fires on changes under `MultiCloud_MLOps/services/**`, `k8s/**`, or `frontend/**`
- Rotate the `guardian-github-actions` SP secret annually


---

## Project Key Benefits - Summary

**Automation**: Code commit triggers or manually run pipelines that train on the cluster, register models, and deploy to endpoints, no manual promotion or server management.

**Consistency**: Every deployment uses the same pipeline and the same registry versions; rollbacks can target a previous model version.

**Explainability and traceability**: MLflow and Azure ML Studio provide run history, metrics, and model lineage; registry versions tie deployments to specific training runs.

**Scalability**: Training scales on Azure ML compute clusters; inference scales via managed endpoints; application layer scales independently on AWS and AKS.

**Speed**: New model versions move from code to production in one pipeline run; application pods pick up new endpoints via ConfigMap updates and restarts.
Multi-cloud flexibility: Use AWS for data and messaging and Azure for ML and CI/CD, with clear boundaries and minimal coupling.


---

## Teardown / Cleanup

### AWS Resources
```bash
chmod +x aws_resource_cleanup.sh
./aws_resource_cleanup.sh
```

### Azure Resources
```bash
python automation/cleanup.py
# OR manually:
az group delete --name guardian-ai-prod --yes --no-wait
```

### Verify cleanup
```bash
# AWS
echo "S3:"; aws s3 ls | grep guardian
echo "SQS:"; aws sqs list-queues --region us-east-1
echo "DDB:"; aws dynamodb list-tables --region us-east-1

# Azure
az resource list --resource-group guardian-ai-prod --output table
```

---

## Lessons Learned

This lab required significant troubleshooting beyond the original manual. Key lessons:

1. **Always set `AWS_REGION` explicitly** — never rely on CLI defaults in scripts
2. **S3 in us-east-1 is special** — it's the default region and rejects `LocationConstraint`
3. **Azure DevOps CLI has gaps** — some service connection types (AKS Kubeconfig, Token) require the REST API
4. **ACR must be attached to AKS** after creation via `az aks update --attach-acr`
5. **Portfolio-Projects repo structure matters** — pipeline YAML paths must include the subfolder prefix when the pipeline YAML isn't at repo root
6. **Self-hosted agents require network access** — Microsoft-hosted `ubuntu-latest` is simpler for labs
7. **Never commit secrets** — use `.env` + `.gitignore`, rotate credentials immediately if exposed


---

## Troubleshooting - Known Issues & Workarounds

### 1. AWS Region Mismatch (CRITICAL)
**Symptom**: Resources created in wrong region despite `AWS_REGION=us-east-1`  
**Root cause**: Original `setup-aws.sh` had `REGION="ap-south-1"` hardcoded  
**Fix**: Already patched — script now reads `${AWS_REGION:-$(aws configure get region)}`

### 2. S3 Bucket Creation Fails in us-east-1
**Symptom**: `An error occurred (InvalidLocationConstraint)`  
**Root cause**: us-east-1 is S3's default region and rejects `LocationConstraint`  
**Fix**: Already patched — script uses conditional creation without `LocationConstraint` for us-east-1

### 3. S3 Bucket "OperationAborted" After Deletion
**Symptom**: `A conflicting conditional operation is currently in progress`  
**Root cause**: AWS enforces a ~10-minute cooldown before a deleted bucket name can be reused  
**Workaround**: Add `S3_BUCKET_OVERRIDE=guardian-videos-yourname-dev` to `.env`

### 4. ACR Credentials Lost Between Stages
**Symptom**: `username is empty` when running `--stage images` standalone  
**Root cause**: ACR credentials were only held in-memory during `--stage azure`  
**Fix**: Already patched — `build_images.py` fetches credentials from Azure CLI when not in config; `setup_azure.py` persists `AZURE_ACR_NAME` to `.env`

### 5. Pods in ErrImagePull After k8s Deployment
**Symptom**: All pods stuck in `ErrImagePull`  
**Root cause**: New ACR not attached to AKS cluster  
**Fix**: Run manually after `--stage k8s` if pods fail:
```bash
az aks update \
  --name guardian-ai-aks \
  --resource-group guardian-ai-prod \
  --attach-acr <YOUR_ACR_NAME>
kubectl rollout restart deployment -n production
```

### 6. Azure DevOps Service Connection — Interactive Prompt
**Symptom**: `Azure RM service principal key:` prompt during `--stage devops`  
**Root cause**: `az devops service-endpoint azurerm create` prompts for SP key interactively  
**Fix**: Set these in `.env` before running `--stage devops`:
```bash
AZURE_SP_APP_ID=<appId>
AZURE_SP_SECRET=<password>
AZURE_TENANT_ID=<tenant>
```

### 7. Self-Hosted Agent Download Fails
**Symptom**: `socket.gaierror: nodename nor servname provided` downloading agent  
**Root cause**: `vstsagentpackage.azureedge.net` blocked or unavailable  
**Fix**: Already patched — setup skips self-hosted agent and uses Microsoft-hosted `ubuntu-latest` pool instead

### 8. Pipeline YAML "Could not find valid pipeline YAML file"
**Symptom**: Azure DevOps pipeline fails immediately with YAML not found  
**Root cause**: Azure Repos has the full Portfolio-Projects structure, so YAMLs are under `MultiCloud_MLOps/` subfolder, not at root  
**Fix**: Already patched — pipeline YAMLs reference correct paths. If you re-create pipelines, update the YAML path in Azure DevOps to `MultiCloud_MLOps/azure-pipelines-*.yml`

### 9. ML Training Pipeline "No agent found in pool Default"
**Symptom**: Training jobs fail immediately  
**Root cause**: Pipeline YAML had `pool: name: 'Default'` requiring self-hosted agent  
**Fix**: Already patched — all pipeline YAMLs use `pool: vmImage: 'ubuntu-latest'`

### 10. ML Training Path Error
**Symptom**: `Cannot find path '/home/vsts/work/1/s/mlops/training'`  
**Root cause**: Pipeline runs from Portfolio-Projects repo root, so MLOps scripts are under `MultiCloud_MLOps/mlops/`  
**Fix**: Already patched — pipeline YAMLs use `cd MultiCloud_MLOps/mlops/training`

### 11. Duplicate ACR Created on Each Azure Stage Run
**Symptom**: New `guardianacr*` created every time `--stage azure` runs  
**Root cause**: ACR name was timestamp-generated and not persisted  
**Fix**: Already patched — `setup_azure.py` saves `AZURE_ACR_NAME=` to `.env` after first creation

---

---
## Authors

- **Marcos Oliveira** — VP AI/ML Engineering   
  [github.com/MAOFILHO](https://github.com/MAOFILHO) | [Portfolio-Projects](https://github.com/MAOFILHO/Portfolio-Projects)

---

## License

MIT License — see [LICENSE](LICENSE)
