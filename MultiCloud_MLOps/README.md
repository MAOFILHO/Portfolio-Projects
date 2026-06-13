# Guardian AI — MultiCloud MLOps Video Content Moderation

A production-grade, end-to-end MLOps application for automated video content moderation. Built on **Azure AKS** (Kubernetes) + **AWS** (S3, SQS, DynamoDB) with **Azure ML** for NSFW and Violence detection model training and deployment.

> **K21 Academy Lab** — Real-World MultiCloud MLOps Track  
> Converted from manual GUI steps to a fully automated Python/CLI deployment pipeline.

---

## Architecture

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

## Quick Start

### 1. Clone and Configure

```bash
# If using as a standalone project:
git clone https://github.com/MAOFILHO/Portfolio-Projects.git
cd Portfolio-Projects/MultiCloud_MLOps

# Install Python dependencies
python -m venv .venv
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

---

## Known Issues & Workarounds

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

## Stage Details

### Stage 1: AWS (`--stage aws`)
Creates: S3 bucket, 2 SQS queues, 2 DynamoDB tables  
Duration: ~2 minutes  
Region: **us-east-1** (hardcoded guard — will error if unconfigured)

### Stage 2: Azure (`--stage azure`)
Creates: Resource group, ACR, AKS cluster (4 nodes), NGINX Ingress  
Duration: ~15 minutes (AKS is the long step)  
Output: External IP for the app

### Stage 3: Docker Images (`--stage images`)
Builds and pushes 8 Docker images to ACR:
- `ingestion`, `fast-screening`, `deep-vision`, `policy-engine`
- `human-review`, `notification`, `api-gateway`, `frontend`  
Duration: ~20 minutes (first run; subsequent runs use layer cache)

### Stage 4: Kubernetes (`--stage k8s`)
Deploys: Namespace, ConfigMap, AWS secrets, all 8 services + Redis, Ingress  
Duration: ~5 minutes  
✅ App is live after this stage

### Stage 5: DevOps (`--stage devops`)
Creates: Azure DevOps project, 3 service connections, variable group, 3 pipelines  
Duration: ~5 minutes  
Requires: `AZDO_PAT_TOKEN`, `AZURE_SP_APP_ID`, `AZURE_SP_SECRET`, `AZURE_TENANT_ID`

### Stage 6: ML (`--stage ml`)
Creates: Azure ML workspace, compute cluster, triggers training pipeline  
Duration: ~45 minutes (training on `cpu-training-cluster`)  
Output: NSFW + Violence detection endpoints; patches Kubernetes ConfigMap

---

## Running Tests

```bash
# Smoke tests (no cloud credentials required)
python -m pytest tests/smoke/test_smoke.py -v

# Expected: 69 tests passing
```

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

## Authors

- **Marcos Oliveira** — Senior AI/ML Engineering Leader  
  [github.com/MAOFILHO](https://github.com/MAOFILHO) | [Portfolio-Projects](https://github.com/MAOFILHO/Portfolio-Projects)

---

## License

MIT License — see [LICENSE](LICENSE)
