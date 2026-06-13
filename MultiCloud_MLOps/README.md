# Guardian AI — MultiCloud MLOps

**End-to-End MLOps Pipeline: Multi-Cloud Video Content Moderation**

This project automates the complete K21Academy Multi-Cloud Video Content Moderation MLOps guide.
Every step that the manual asks you to perform through the Azure Portal, Azure DevOps UI,
or Azure ML Studio GUI has been replaced with a single command:

```bash
python setup.py
```

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                       Application Layer (AKS)                      │
│  Ingestion → Fast-Screening → Deep-Vision → Policy Engine         │
└──────────────────────────┬────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   ┌──────────────────┐      ┌──────────────────────────┐
   │     AWS Cloud    │      │       Azure Cloud          │
   │  S3  (videos)    │      │  Azure ML Workspace        │
   │  SQS (queues)    │◄────►│  Compute Cluster           │
   │  DynamoDB (meta) │      │  Model Registry            │
   └──────────────────┘      │  Online Endpoints (NSFW,   │
                              │  Violence detection)       │
                              │  Azure DevOps CI/CD        │
                              │  AKS + ACR                 │
                              └────────────────────────────┘
```

---

## Automated setup stages

| Stage | Section | What runs | Time |
|---|---|---|---|
| `aws` | §7 | S3, SQS, DynamoDB | ~2 min |
| `azure` | §8 | RG, ACR, AKS, NGINX | ~15 min |
| `images` | §9 | Docker build & push (8 images) | ~20 min |
| `k8s` | §10–11 | ConfigMap, secrets, deploy all services | ~5 min |
| `devops` | §12.1–12.4 | DevOps project, 3 service connections, agent, pipelines | ~5 min |
| `ml` | §12.5–12.7 | ML workspace, compute cluster, train, deploy, endpoint patch | ~30 min |

---

## Quick start

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | https://www.python.org |
| Azure CLI | 2.50+ | https://learn.microsoft.com/cli/azure |
| AWS CLI | 2.13+ | https://aws.amazon.com/cli |
| Docker Desktop | 24+ | https://www.docker.com/products/docker-desktop |
| kubectl | 1.28+ | https://kubernetes.io/docs/tasks/tools |
| Helm | 3.12+ | https://helm.sh/docs/intro/install |
| Node.js | 20+ | https://nodejs.org |

**macOS:**  `brew install kubectl awscli azure-cli helm node python@3.11`

**Windows (PowerShell):**
```powershell
winget install Docker.DockerDesktop Kubernetes.kubectl Python.Python.3.11 Amazon.AWSCLI Microsoft.AzureCLI Kubernetes.Helm OpenJS.NodeJS
```

### Setup

```bash
# 1. Clone
git clone https://github.com/k21academyuk/MultiCloud_MLOps.git
cd MultiCloud_MLOps

# 2. Python environment
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env — minimum required:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#   AZURE_SUBSCRIPTION_ID
#   AZDO_ORG_NAME, AZDO_PAT_TOKEN   ← generate PAT below

# 4. Verify tools
python setup.py --check

# 5. Full setup (~75 min)
python setup.py
```

**Generate Azure DevOps PAT:**
https://dev.azure.com → User Settings (top-right) → Personal Access Tokens → New Token
Scopes: Agent Pools (R&M), Build (R&E), Code (R), Project+Team (R&W),
Service Connections (R,Q,M), Variable Groups (R,C,M)

### Individual stages

```bash
python setup.py --stage aws       # AWS infra only
python setup.py --stage azure     # Azure infra only
python setup.py --stage images    # Docker build & push
python setup.py --stage k8s       # Deploy to Kubernetes
python setup.py --stage devops    # Azure DevOps + agent + pipelines
python setup.py --stage ml        # ML workspace + train + deploy

python setup.py --resume-from k8s # Resume from a specific stage after a failure
python setup.py --cleanup         # Teardown all resources
```

---

## Project structure

```
MultiCloud_MLOps/
├── setup.py                          ← Main orchestrator (start here)
├── .env.example                      ← Credentials template
├── requirements.txt
│
├── automation/                       ← Automation layer
│   ├── config.py                     ← Central configuration
│   ├── cleanup.py                    ← Resource teardown (§14)
│   ├── aws/setup_aws.py              ← §7: S3, SQS, DynamoDB
│   ├── azure/setup_azure.py          ← §8: RG, ACR, AKS, NGINX
│   ├── azure/build_images.py         ← §9: Docker build & push
│   ├── k8s/deploy_k8s.py             ← §10–11: ConfigMap + deploy
│   ├── devops/setup_devops.py        ← §12.1–12.4: DevOps pipelines
│   ├── ml/setup_ml.py                ← §12.5–12.7: ML workspace + train + deploy
│   └── utils/shell.py                ← Shared CLI runner + logging
│
├── services/                         ← Application microservices
│   ├── ingestion/                    ← Video upload (S3 + DynamoDB)
│   ├── fast-screening/               ← Quick heuristic scoring
│   ├── deep-vision/                  ← ML model inference (Azure ML endpoints)
│   ├── policy-engine/                ← Allow/block/review decisions
│   ├── human-review/                 ← Manual review queue
│   ├── notification/                 ← Event notifications
│   └── api-gateway/                  ← Frontend API proxy
│
├── k8s/                              ← Kubernetes manifests
├── mlops/                            ← ML training & deployment scripts
├── frontend/                         ← React dashboard
├── scripts/                          ← Helper bash scripts
├── tests/
│   └── smoke/test_smoke.py           ← Smoke tests (run without cloud creds)
└── azure-pipelines-*.yml             ← Azure DevOps pipeline definitions
```

---

## Two browser-only steps

1. **DevOps organization** — Create at https://dev.azure.com (one time)
2. **PAT token** — Generate in DevOps UI (User Settings → Personal Access Tokens)

Everything else is automated.

---

## End-to-end test

After setup:
1. Open `http://<EXTERNAL_IP>` (printed at end of setup)
2. Upload a video → Dashboard shows "Processing"
3. After 2–5 min: "Pending Review" (high risk) or "Approved" (low risk)
4. Use "Review Queue" to manually approve/reject

---

## Cleanup

```bash
python setup.py --cleanup
```

Deletes Azure resource group (AKS, ACR, ML workspace, endpoints) and AWS resources
(S3 bucket, SQS queues, DynamoDB tables). Requires explicit `yes` confirmation per cloud.

Estimated cost: $2–15 USD for a 3–6 hour lab session.

---

## Smoke tests

```bash
pytest tests/smoke/test_smoke.py -v
```

64 tests covering module imports, config, YAML validity, bash syntax, service structure.
All run without cloud credentials.

---

## MLOps pipeline overview

**Training:** `azure-pipelines-ml-training.yml`
→ Agent calls `mlops/training/submit_training_job.py`
→ Submits NSFW + Violence training jobs to `cpu-training-cluster`
→ MLflow tracks metrics; models auto-register in Azure ML Model Registry

**Deployment:** `azure-pipelines-ml-deployment.yml`
→ Agent calls `mlops/deployment/deploy_model.py`
→ Creates/updates `nsfw-detector-endpoint` and `violence-detector-endpoint`
→ Updates Kubernetes ConfigMap with scoring URIs
→ Restarts `deep-vision` deployment to pick up new endpoints

**Application CI/CD:** `azure-pipelines-app-ci-cd.yml`
→ Builds all 8 Docker images → pushes to ACR → deploys to AKS

---

*K21Academy Multi-Cloud Video Content Moderation MLOps Application*
*Automation layer: replaces all Azure Portal / Azure DevOps / Azure ML Studio GUI steps*
