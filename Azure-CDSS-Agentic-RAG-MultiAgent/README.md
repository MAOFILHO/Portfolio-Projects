# Azure Agentic RAG Pipeline — Clinical Decision Support System

A production-grade, end-to-end automated deployment pipeline for a **Clinical Decision Support System** using **Agentic RAG** on Azure. Built with **Azure OpenAI** (GPT-5 + GPT-5-mini), **Azure AI Search**, **Cosmos DB**, **Container Apps**, and a **React** frontend — deployed via a fully automated **Python/CLI** pipeline with **zero Azure Portal clicks**.

![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-Cloud-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18.2-61DAFB?style=for-the-badge&logo=react&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

---

## Project Description

This project orchestrates a **Multi-Agent Clinical AI Workflow** on Azure. Azure OpenAI provides the inference engine (GPT-5 for orchestration and synthesis, GPT-5-mini for lightweight agent tasks), Azure AI Search handles hybrid retrieval across patient records, treatment protocols, and cached literature, and Cosmos DB persists patient profiles, audit trails, and agent state.

The **FastAPI backend** runs on **Azure Container Apps**, coordinates five specialized AI agents in parallel, and returns streaming clinical recommendations via SSE. The **React frontend** deploys to **Azure Static Web Apps** with Microsoft Entra ID (OAuth 2.0) authentication. Azure Bicep templates provision 56+ resources including VNet with private endpoints, Key Vault for secrets, Document Intelligence for PDF parsing, and Application Insights for distributed tracing.

The deployment pipeline wraps battle-tested infrastructure scripts with a Python CLI that handles everything from prerequisite checks through end-to-end validation — a single `cdss-deploy deploy` command replaces 20+ manual steps from the original project guide.

---

## The Business Case: Why This Matters

**Problem:** Clinical decision-making requires pulling information from multiple places at once: patient history, current medications, internal protocols, and external evidence. Manually reviewing all of this for every case is slow, inconsistent, and error-prone under real operational pressure.

**The Challenge:** To scale and standardize clinical decisions, you need an intelligent orchestration system that can retrieve patient data, search guideline/protocol evidence, evaluate medication risks, apply guardrails, and return grounded recommendations with citations — all in seconds, not hours.

**The Consequence:** Without automation, clinical teams either miss critical evidence, delay care decisions unacceptably, or burn through specialist capacity on routine cases that a well-designed AI system should handle. The gap between information volume and human review capacity is structural, not a staffing problem.

**The Solution:** This project deploys a **Clinical Decision Support System (CDSS)** that uses an **agentic RAG architecture** with five specialized AI agents. Instead of a single monolithic response, the system decomposes clinical queries, dispatches them to domain-specific agents in parallel, fuses evidence from multiple sources, and synthesizes a citation-backed recommendation — all validated by a guardrails agent before delivery.

---

## Cross-Cloud Integration — External APIs + Azure ML Platform

**The Architecture:** Keeps the ML platform, compute, data, and identity on **Azure**, and integrates with external clinical data sources (**PubMed**, **OpenFDA**, **RxNorm**, optional **DrugBank**) for real-time evidence enrichment.

**Definition:** Separation of responsibilities: **Azure** for OpenAI inference, vector search, document storage, identity, secrets, and container hosting; **External APIs** for live medical literature, drug safety signals, and medication normalization.

**Use Case:** The Medical Literature Agent queries PubMed's 36M+ biomedical citations in real time; the Drug Safety Agent normalizes drug names via RxNorm and checks interactions via OpenFDA adverse event data; all results are cached in Azure AI Search for subsequent retrieval.

**Example:** Clinician submits query → Orchestrator dispatches 5 agents in parallel → Patient History from Cosmos DB + AI Search, Literature from PubMed + cache, Protocols from Blob + Search index, Drug Safety from RxNorm + OpenFDA + DrugBank, Guardrails verifies citations → Synthesized recommendation with confidence score returned via SSE streaming.

---

## Design Decisions

- **Five-agent parallel orchestration** decomposes complex clinical queries into specialized tasks, each with its own model, tools, and data sources — reducing latency and improving source coverage vs. a single-prompt approach.
- **Hybrid RAG (BM25 + vector + semantic reranking)** ensures both keyword-exact matches and semantic similarity are captured, with Reciprocal Rank Fusion for cross-source deduplication.
- **Wrap existing infrastructure scripts, don't rewrite them** — the 6 bash scripts contain 2000+ lines of battle-tested Azure CLI logic (soft-delete recovery, network isolation handling, fingerprint-based idempotency). The Python CLI wraps them with real-time streaming and auto-confirmation.
- **Resumable deployment state** — a JSON checkpoint file tracks step completion. If deployment fails at step 8, re-running resumes from step 8 instead of re-provisioning infrastructure.
- **OpenTelemetry + Application Insights (non-optional)** — observability is built-in from deployment, not bolted on later. Every agent call, external API request, and inference operation is traced.

---

## Results and Impact

| Metric | Project result	| Comparable benchmark / business interpretation |
|--------|----------------|------------------------------------------------|
| Annual clinician-hours saved | ~12,740 hours/year | 200 complex queries/day × 365 days × 195.6 seconds saved per case, based on a comparable CDSS study that reduced chart-review time from 445.1s to 249.5s |
| Evidence‑gathering time reduction	| ~40–45% (project target; aligns with CDSS study 445.1s → 249.5s) | Benchmarked CDSS study reported ≈44% reduction in chart‑review time, preserving decision accuracy | 
| End‑to‑end decision latency	| < 10 seconds (streamed recommendation) | Significantly faster than minutes–hours for manual multi‑source reviews; enables near real‑time clinical support |
| Clinician throughput gain	| Minutes saved per case → hours reclaimed weekly	| Benchmarks translate per‑case savings into tens of hours per year per clinician for routine workflows |
| Recommendation consistency | Standardized, citation‑backed outputs with guardrails | Addresses variability and missed evidence inherent in manual review; aligns with best practices for auditable CDS | 



**Impact:** This project demonstrates how an automated agentic RAG pipeline can improve clinical decision speed, evidence coverage, and operational consistency. By orchestrating multiple specialized agents in parallel, the system provides comprehensive evidence-backed recommendations in seconds rather than the minutes-to-hours required for manual multi-source review.

**Business Value:** From an operational perspective, the system reduces the time clinicians spend searching across disparate systems, improves consistency of evidence-based recommendations, and provides full auditability through immutable Cosmos DB audit trails with HIPAA-compliant retention policies.

**Example:** For a clinical operations team handling **200 complex queries per day**, multi-agent orchestration provides evidence from **5 sources simultaneously** — patient records, medical literature, treatment protocols, drug safety databases, and guideline repositories — with citation provenance and confidence scoring on every response.

---

## Business Value Delivered

❌ Manual, fragmented, time-consuming, inconsistent evidence gathering across multiple systems, to:

✅ Automated, evidence-grounded, auditable, elastic, multi-agent clinical decision support

**Key outcomes:**
- 5-agent parallel orchestration: patient history + literature + protocols + drug safety + guardrails
- Sub-10-second response time for complex multi-source clinical queries via SSE streaming
- Zero-touch deployment: `cdss-deploy deploy` → 56+ Azure resources → live system
- Full HIPAA-compliant audit trail: every query, agent action, and recommendation logged
- Citation verification: every recommendation cross-referenced against PubMed and source databases
- Drug safety guardrails: automated contraindication and interaction checking before any recommendation
- 18/18 unit tests + pre/post-deploy smoke tests gate broken deployments
- Estimated ~$4-30 USD for short-lived deployment + testing

---

## Azure Architecture

<img width="642" height="948" alt="Screenshot 2026-06-30 at 11 45 42 PM" src="https://github.com/user-attachments/assets/7fa2be9e-c3c7-4986-95f7-5c2963b7f127" />

---

## CDSS Agentic Architecture

```
  Clinician Query
       |
       v
  +------------------------------------------------------------+
  |              Agentic AI Orchestrator (GPT-5)               |
  |  Decomposes query → delegates to agents → synthesizes      |
  +----+----------+----------+----------+----------+-----------+
       |          |          |          |          |
       v          v          v          v          v
  +---------+ +----------+ +---------+ +---------+ +-----------+
  | Patient | | Medical  | |Protocol | |  Drug   | |Guardrails |
  | History | |Literature| | Agent   | | Safety  | |  Agent    |
  +---------+ +----------+ +---------+ +---------+ +-----------+
       |          |            |          |          |
       v          v            v          v          v
  +---------+ +---------+ +---------+ +---------+ +------------+
  |Azure AI | | PubMed  | |Azure AI | |DrugBank | | Citation   |
  | Search  | |  API    | | Search  | |OpenFDA  | |Verification|
  |Cosmos DB| | Cache   | |  Blob   | | RxNorm  | |Safety Val. |
  +---------+ +---------+ +---------+ +---------+ +------------+
       |           |          |            |          |
       +-----------+----------+------------+----------+
                             |
                             v
                  +---------------------+
                  |   Agent Synthesis   |
                  |  (Fusion + Rerank)  |
                  +---------------------+
                             |
                             v
                  +---------------------+
                  | Clinical            |
                  | Recommendation      |
                  | + Citations         |
                  | + Drug Alerts       |
                  | + Confidence Score  |
                  | + Audit Trail       |
                  +---------------------+
```

**Azure** (East US):
- Container Apps: FastAPI backend (GPT-5 orchestrator + 5 agents)
- Static Web Apps: React 18 frontend with Entra ID auth
- OpenAI: GPT-5, GPT-5-mini, text-embedding-3-large deployments
- AI Search: 3 indexes (patient-records, treatment-protocols, medical-literature-cache)
- Cosmos DB: 5 containers (patient-profiles, conversation-history, embedding-cache, audit-log, agent-state)
- Document Intelligence: PDF/DOCX parsing for document ingestion
- Key Vault, ACR, Redis, Blob Storage, VNet + Private Endpoints, App Insights

**External APIs:**
- PubMed E-utilities: 36M+ biomedical citations
- OpenFDA: Drug adverse event reports and labelling
- RxNorm: Drug name normalization
- DrugBank: Drug-drug interaction data (optional)

---

## Prerequisites

| Tool | Version | Install (macOS) |
|------|---------|-----------------|
| **Python** | **3.12.x** (exact) | `brew install python@3.12` or `pyenv install 3.12` |
| Docker Desktop | 24+ | [docker.com](https://docker.com) |
| Azure CLI | 2.50+ | `brew install azure-cli` |
| Node.js | 20+ LTS | `brew install node` |
| Git | 2.40+ | `brew install git` |
| jq | 1.6+ | `brew install jq` |
| curl | 7.8+ | `brew install curl` |

**Azure subscription** with **Owner** role (required for RBAC role assignments during Bicep deployment). Contributor alone is not sufficient — the deployment creates managed identity role assignments on Key Vault, OpenAI, AI Search, Storage, and ACR resources.

> **Why Python 3.12 specifically?** The CDSS backend uses Python 3.12 features (modern type hints, `tomllib`, performance improvements) and the Docker container is built on `python:3.12-slim`. Python 3.11 or earlier will fail. Python 3.13+ has not been tested and may have dependency incompatibilities.

---

## Project Structure

```
azure-cdss-pipeline/
├── setup.py                          # (via pyproject.toml + cdss-deploy CLI)
├── pyproject.toml                    # Project metadata + dependencies
├── Makefile                          # Convenience: make deploy, make teardown, make test
├── .env.example                      # Environment variables template
├── README.md                         # This file
│
├── src/cdss_deploy/                  # Deployment automation
│   ├── cli.py                        # Typer CLI: deploy, teardown, status, smoke-test
│   ├── config.py                     # Pydantic settings, reads .env
│   ├── console.py                    # Rich terminal output formatting
│   ├── state.py                      # Deployment state persistence (resumable)
│   ├── runner.py                     # Subprocess wrapper for shell scripts
│   │
│   ├── steps/                        # Stage automation modules
│   │   ├── s00_preflight.py          # Stage: preflight checks
│   │   ├── s01_azure_login.py        # Stage: Azure login + subscription
│   │   ├── s02_collect_secrets.py    # Stage: PubMed API key collection
│   │   ├── s03_deploy_infra.py       # Stage: Bicep → 56+ Azure resources
│   │   ├── s04_resolve_names.py      # Stage: discover deployed resource names
│   │   ├── s05_health_check.py       # Stage: backend health validation
│   │   ├── s06_env_and_seed.py       # Stage: env files + sample data
│   │   ├── s07_entra_auth.py         # Stage: Entra ID app registrations
│   │   ├── s08_pubmed_config.py      # Stage: PubMed Key Vault wiring
│   │   ├── s09_frontend_env.py       # Stage: frontend .env.production
│   │   ├── s10_deploy_frontend.py    # Stage: React build + SWA deploy
│   │   ├── s11_cors_and_redirect.py  # Stage: CORS + redirect URIs
│   │   ├── s12_validate_e2e.py       # Stage: end-to-end validation
│   │   └── s13_teardown.py           # Stage: full resource cleanup
│   │
│   ├── observability/                # OpenTelemetry + Azure Monitor
│   │   ├── setup.py                  # Trace provider + exporter config
│   │   └── instrument.py             # Auto-instrument FastAPI + httpx
│   │
│   └── smoke/                        # Pre/post deploy checks
│       ├── pre_deploy.py             # Tool versions, Docker, Azure CLI, source dir
│       └── post_deploy.py            # Health, API docs, frontend, auth, PubMed
│
├── tests/                            # Test suite
│   ├── conftest.py                   # Shared fixtures
│   ├── test_preflight.py             # Prerequisite checking tests
│   ├── test_state.py                 # State persistence tests
│   ├── test_cli.py                   # CLI command tests
│   └── integration/
│       └── test_e2e.py               # Live Azure e2e tests
│
├── docs/
│   └── architecture.md               # Architecture diagrams
│
├── sample_data
|     ├── sample_lab_report.pdf        # import data to RAG
|     ├── sample_lab_literature.pdf    # import data to RAG
|     ├── sample_lab_protocol.pdf      # import data to RAG
|
├── scripts
      ├── purge-soft-deleted.sh        # delete script

```

---

## Cost Estimates

| Resource | Monthly Cost |
|----------|-------------|
| Azure OpenAI (GPT-5, GPT-5-mini, text-embedding-3-large) | ~$1-15 (token-based) |
| Azure AI Search (Standard S1) | ~$0.5-4 |
| Azure Container Apps (Consumption) | ~$0-3 |
| Azure Cosmos DB (Serverless) | ~$0.1-2 |
| Azure Document Intelligence (S0) | ~$0-2 |
| Azure Blob Storage | ~$0.01-0.25 |
| Azure Static Web Apps (Free/Standard) | Free-$1 |
| Azure Monitor + App Insights | ~$0.1-3 |
| Azure Managed Redis (Balanced B0/B1) | ~$0.2-2 |
| Azure Container Registry + Key Vault | ~$0.1-1 |
| **Total** | **~$4-30/deployment** |

> **Cost Warning:** Azure AI Search runs 24/7 when provisioned. Tear down resources when not in use:
> ```bash
> cdss-deploy teardown
> ```

---

## Quick Start

### 1. Clone and Configure

```bash
cd azure-cdss-pipeline

# Install Python dependencies
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,observability]"

# Configure credentials
cp .env.example .env
# Edit .env with your values (see CONFIGURATION section below)
```

### 2. Configure Azure

```bash
az login
az account set --subscription <YOUR_SUBSCRIPTION_ID>
```

### 3. Get PubMed API Key

1. Create account at https://www.ncbi.nlm.nih.gov/account/
2. Account Settings → API Key Management → Create API Key
3. Add to `.env`: `CDSS_PUBMED_API_KEY=<your-key>` and `CDSS_PUBMED_EMAIL=<your-email>`

### 4. Run Automated Deployment

```bash
cdss-deploy smoke-test --stage pre   # ~5s:     Verify prerequisites
cdss-deploy deploy                   # ~30-45 min: Full deployment (13 stages)
```

After deployment completes, the app is live at the URLs shown in the deployment summary.

> **Total deployment time: ~30-45 minutes** on first run. Breakdown: ACR cloud build (~5 min), Bicep infrastructure (~15-25 min), post-deploy config + frontend build (~10 min). Subsequent runs are faster if infrastructure already exists.

---

## Configuration

Copy `.env.example` to `.env` and fill in all values:

### Azure Credentials
```bash
AZURE_SUBSCRIPTION_ID=<az account show --query id -o tsv>
AZURE_LOCATION=eastus
AZURE_RESOURCE_GROUP=cdss-prod-rg
AZURE_ENVIRONMENT=prod
```

### PubMed Credentials
```bash
CDSS_PUBMED_API_KEY=<from NCBI account settings>
CDSS_PUBMED_EMAIL=<your email>
```

### Optional
```bash
CDSS_DRUGBANK_API_KEY=<optional, commercial license>
CDSS_SOURCE_DIR=../cdss-agentic-rag    # Path to source codebase
CDSS_IMAGE_BUILD_MODE=acr              # Use Azure cloud build (recommended for Apple Silicon)
```

---

## Stage Details

### Stage 0: Preflight (`s00_preflight`)
Checks: Docker, Python 3.12, Azure CLI 2.50+, Node.js 20+, jq, curl, git, Docker daemon, source directory  
Duration: ~5 seconds

### Stage 1: Azure Login (`s01_azure_login`)
Runs `az login` if needed, sets subscription, verifies account  
Duration: ~10 seconds

### Stage 2: Collect Secrets (`s02_collect_secrets`)
Prompts for PubMed API key and email (if not in `.env`)  
Duration: Interactive

### Stage 3: Deploy Infrastructure (`s03_deploy_infra`)
Builds Docker image via ACR cloud build (~5 min), then deploys Bicep template provisioning 65 Azure resources: VNet with 4 subnets, 4 NSGs, managed identity, Key Vault, Log Analytics, App Insights, Azure OpenAI (3 model deployments), AI Search, Document Intelligence, Cosmos DB (5 containers), Blob Storage (3 containers), Container Apps Environment + API container, 5 private endpoints + DNS zones, 6 RBAC role assignments, diagnostic settings  
Duration: **~20-30 minutes** (longest stage — ACR build ~5 min + Bicep provisioning ~15-25 min)

> **Apple Silicon note:** Set `CDSS_IMAGE_BUILD_MODE=acr` in `.env` to build Docker images in Azure cloud instead of locally. Local cross-compile (ARM → x86_64) via QEMU is extremely slow and may timeout.

### Stage 4: Resolve Names (`s04_resolve_names`)
Queries Azure for all deployed resource names, endpoints, and keys  
Duration: ~15 seconds

### Stage 5: Health Check (`s05_health_check`)
Validates backend `/api/v1/health` with exponential backoff retry (up to 5 minutes for cold start)  
Duration: ~30 seconds

### Stage 6: Env + Seed Data (`s06_env_and_seed`)
Generates `.env` files from deployed resources, seeds sample patient data via in-network execution  
Duration: ~2 minutes

### Stage 7: Entra Auth (`s07_entra_auth`)
Creates SPA + API app registrations, configures OAuth scopes, grants admin consent, aligns backend `CDSS_AUTH_AUDIENCE`  
Duration: ~30 seconds

### Stage 8: PubMed Config (`s08_pubmed_config`)
Stores PubMed credentials in Key Vault, wires Container App env vars via secretRef, handles Key Vault network isolation automatically  
Duration: ~2 minutes

### Stage 9: Frontend Env (`s09_frontend_env`)
Generates `frontend/.env.production` with API URL, Entra config, WebSocket endpoint; creates Static Web App if needed  
Duration: ~15 seconds

### Stage 10: Deploy Frontend (`s10_deploy_frontend`)
Runs `npm ci` + `npm run build`, deploys to Azure Static Web Apps  
Duration: ~3 minutes

### Stage 11: CORS + Redirects (`s11_cors_and_redirect`)
Configures backend CORS origins, sets Entra redirect URIs for production frontend  
Duration: ~15 seconds

### Stage 12: E2E Validation (`s12_validate_e2e`)
Validates: backend health, API docs, frontend reachability, auth configuration, CORS, PubMed env vars  
Duration: ~15 seconds

---

## Running Tests

```bash
# Unit tests (18 tests, no Azure required)
make test
# Expected: 18 passed

# Pre-deploy smoke test
make smoke-pre

# Post-deploy smoke test (requires deployed infrastructure)
make smoke-post

# Lint
make lint
```

---

## CLI Commands

```bash
cdss-deploy deploy              # Full deployment (resumable)
cdss-deploy deploy --fresh      # Start fresh (ignore previous state)
cdss-deploy deploy -g my-rg     # Override resource group
cdss-deploy deploy -l westus2   # Override Azure region
cdss-deploy deploy -s ../path   # Override source directory

cdss-deploy teardown            # Delete all Azure resources
cdss-deploy teardown -y         # Skip confirmation

cdss-deploy status              # Show deployment progress

cdss-deploy smoke-test --stage pre   # Pre-deploy checks
cdss-deploy smoke-test --stage post  # Post-deploy validation
```

---

## Observability

The pipeline automatically configures **OpenTelemetry** with **Azure Application Insights** for distributed tracing:

- FastAPI request/response tracing for all API endpoints
- Outbound HTTP tracing for PubMed, OpenFDA, RxNorm, DrugBank calls
- Agent execution spans with latency tracking
- Traces exported to the App Insights resource provisioned by Bicep

View traces in Azure Portal → Application Insights → Transaction search / Performance.

---

## Teardown / Cleanup

Duration: **~5-10 minutes** (Azure deletes resources in dependency order, then purges soft-deleted services)

### Azure Resources
```bash
cdss-deploy teardown              # Delete the resource group + Entra app registrations
cdss-deploy teardown -y           # Skip confirmation prompt
# OR manually:
az group delete --name cdss-prod-rg --yes --no-wait
```

### Verify Cleanup
```bash
az resource list --resource-group cdss-prod-rg --output table
# Expected: empty or "Resource group not found"
```

### Purge Soft-Deleted Resources
By default, teardown leaves Key Vault and Cognitive Services (OpenAI, Document Intelligence) in a **soft-deleted, recoverable** state — Key Vault for 90 days, Cognitive Services for 48h. This is intentional: it's a safety net against accidental deletion, and it's the reason we don't purge automatically on every teardown.

If you don't need that recovery window and want the resource *names* freed up immediately (e.g. for a same-name redeploy in the same region), pass `--purge`:
```bash
cdss-deploy teardown --purge          # Prompts twice: once for delete, once for purge
cdss-deploy teardown -y --purge       # Skips both confirmations
```
`--purge` is opt-in and irreversible. It waits briefly (up to 30 seconds, polling every 10s) for the resource group deletion to finish, then purges the Key Vault and Cognitive Services accounts. Resource group deletion normally takes several minutes, so purge will usually **not** complete on the first run — it prints a warning and skips rather than blocking until deletion finishes. Once the resource group is actually gone (check with `az group exists --name cdss-prod-rg`), re-run `cdss-deploy teardown --purge` to complete the purge, or purge manually:
```bash
az keyvault purge --name <kv-name> --location eastus
az cognitiveservices account purge -g cdss-prod-rg -n <openai-name> -l eastus
az cognitiveservices account purge -g cdss-prod-rg -n <docintel-name> -l eastus
```

Soft-deleted resources are discovered live from Azure (`az keyvault list-deleted` / `az cognitiveservices account list-deleted`), not from local state, so `--purge` still works correctly even on a re-run after `deployment_state.json` has been reset.

Each individual purge call is bounded to 30 seconds (`PURGE_CALL_TIMEOUT_SECONDS` in `s13_teardown.py`) so a single slow purge can't stall the rest of the run — if a call exceeds 30s, it prints a warning and moves on to the next resource rather than hanging.

**Orphaned resources from prior runs:** If you've redeployed to auto-incremented resource groups (`cdss-dev-rg2`, `cdss-dev-rg3`, etc. — see `_ensure_available_resource_group` in `cli.py`), their soft-deleted Key Vault/Cognitive Services resources won't be found by `--purge` once their original resource group is gone, since matching is scoped to the resource group passed to `teardown`. To clean these up, find the original resource group from the deleted resource's `id` field and purge manually:
```bash
az cognitiveservices account list-deleted -o json | python3 -c "
import json, sys
for a in json.load(sys.stdin):
    parts = a['id'].lower().split('/')
    rg = parts[parts.index('resourcegroups') + 1]
    print(a['name'], a['location'], rg)
"
az cognitiveservices account purge --name <name> --location eastus --resource-group <original-rg>
```

---

## Troubleshooting — Known Issues & Workarounds

### 1. RBAC Authorization Failed (CRITICAL)
**Symptom:** `Authorization failed for template resource of type Microsoft.Authorization/roleAssignments`  
**Root cause:** Your Azure account has Contributor but not Owner role  
**Fix:** Assign Owner role on the subscription:
```bash
az role assignment create --assignee "<your-object-id>" \
  --role "Owner" \
  --scope "/subscriptions/<subscription-id>"
```

### 2. Key Vault `ForbiddenByConnection`
**Symptom:** `configure-pubmed-prod.sh` fails with `Public network access is disabled`  
**Root cause:** Key Vault network rules blocking the caller IP  
**Fix:** Script auto-retries with temporary IP allowlist (`CDSS_KV_TEMP_IP_ALLOWLIST=true`, default)

### 3. OpenAI `403 Traffic Not From Approved Endpoint`
**Symptom:** Backend health check fails with OpenAI connectivity error  
**Root cause:** Private networking misconfiguration after Bicep deployment  
**Fix:** `CDSS_OPENAI_NETWORK_AUTOFIX=true` (default) — bootstrap script applies compatibility mode automatically

### 4. `401 Unauthorized` on API Calls
**Symptom:** Bearer token rejected by backend  
**Root cause:** `CDSS_AUTH_AUDIENCE` doesn't match the token's `aud` claim  
**Fix:** Run `./infra/scripts/fix-auth-config.sh --resource-group cdss-prod-rg`

### 5. GPT Model Deployment Fails — SKU Mismatch
**Symptom:** `The specified SKU 'Standard' is not supported by the model 'gpt-5'`  
**Root cause:** GPT-5 family requires `GlobalStandard` SKU, not `Standard`  
**Fix:** Already patched in Bicep template. If using older version, update `sku.name` from `'Standard'` to `'GlobalStandard'`

### 6. Docker Build Timeout on Apple Silicon
**Symptom:** Local Docker build hangs during cross-compile to linux/amd64  
**Root cause:** QEMU emulation for cross-platform builds is slow on ARM64  
**Fix:** Set `CDSS_IMAGE_BUILD_MODE=acr` in `.env` to use Azure cloud build instead

### 7. CORS Preflight Fails
**Symptom:** Frontend gets CORS errors calling backend API  
**Root cause:** Frontend origin not in allowed origins list  
**Fix:** Step 11 configures this automatically. Manual fix:
```bash
az containerapp ingress cors update -g cdss-prod-rg -n <app-name> \
  --allowed-origins "https://<swa-hostname>"
```

### 8. Frontend Build Fails
**Symptom:** `npm run build` fails with syntax errors  
**Root cause:** Node.js version too old (requires 20+ LTS)  
**Fix:** `brew install node` or `nvm install --lts`

### 9. Empty `CDSS_AUTH_AUDIENCE`
**Symptom:** 503 Service Unavailable after Entra auth enabled  
**Root cause:** Bicep default is empty string; Entra auth step should set it  
**Fix:** Entra auth step (s07) sets this automatically. Manual fix:
```bash
az containerapp update -g cdss-prod-rg -n <app-name> \
  --set-env-vars "CDSS_AUTH_AUDIENCE=<API app client ID>"
```

### 10. Deployment Fails Mid-Way
**Symptom:** Any step fails and deployment stops  
**Root cause:** Various (network, permissions, timeouts)  
**Fix:** Re-run `cdss-deploy deploy` — it automatically resumes from the failed step. Use `cdss-deploy status` to see progress.

### 11. Azure Cache for Redis — Service Retired
**Symptom:** Bicep deployment fails with `Azure Cache for Redis is retiring, create Azure Managed Redis instance instead`  
**Root cause:** Microsoft retired the `Microsoft.Cache/redis` resource type. The original Bicep template used this now-deprecated service for rate limiting, response caching, and embedding caching.  
**Impact:** The entire Bicep deployment (65 resources) rolls back when a single resource fails, so this blocked everything.  
**Fix:** Already patched — replaced with **Azure Managed Redis** (`Microsoft.Cache/redisEnterprise`) using the `Balanced_B0/B1` SKU. The runtime used in-memory caching as the active path, so Redis was provisioned but not required. With the new Managed Redis, the option to use distributed caching is available if needed.

### 12. Key Vault Name Collision After Region Change
**Symptom:** `VaultAlreadyExists: The vault name 'xyz' is already in use`  
**Root cause:** Key Vault names are globally unique and have purge protection (90-day soft-delete retention). If you deploy to region A, delete the resource group, then redeploy to region B, the old Key Vault name is reserved in region A and cannot be reused.  
**Fix:** Already patched — the Bicep `uniqueSuffix` now includes the `location` parameter, so deploying to a different region generates different resource names automatically.

### 13. Admin Consent Fails — `Auth enabled: False` in Final Validation
**Symptom:** Stage 7 (Entra Auth) logs `[WARN] Admin consent step failed. Ask a tenant admin to grant consent in Entra ID.`, and the final E2E validation (Stage 12) reports `Auth enabled: False`.  
**Root cause:** Stage 7 calls `az ad app permission admin-consent` automatically, but this Microsoft Graph operation requires the deploying account to hold **Global Administrator**, **Privileged Role Administrator**, or **Cloud Application Administrator** in the Entra ID tenant. If the account only has Owner/Contributor on the subscription (sufficient for Stages 0–6 and 8–12), this call fails with `Authorization_RequestDenied`. This is an Entra ID tenant permission boundary, not a deploy script bug — it cannot be fully automated for accounts without one of those directory roles, including for anyone who clones this repo from GitHub and deploys into their own tenant.  
**Impact:** The API does not enforce bearer token validation until consent is granted — fine for initial smoke-testing, but should be resolved before treating the deployment as production-ready.  
**Fix — Option A (CLI, if you hold one of the required directory roles):**
```bash
az ad app permission admin-consent --id <SPA_APP_CLIENT_ID>
# SPA app client ID is printed in Stage 7 output and stored in
# frontend/.env.local as VITE_AZURE_CLIENT_ID
```
**Fix — Option B (Azure Portal, if a different account holds tenant admin rights):**
1. Sign in to the [Azure Portal](https://portal.azure.com) with an account that holds Global Administrator, Privileged Role Administrator, or Cloud Application Administrator.
2. Go to **Microsoft Entra ID → App registrations** and open the SPA app (name: `cdss-frontend-spa`).
3. Open **API permissions** → click **"Grant admin consent for \<tenant name\>"** → confirm.
4. Re-run `cdss-deploy deploy` (or just Stage 12 validation) to confirm `Auth enabled: True`.

If neither account has the required role, ask your tenant's Global Administrator to perform Option B, or request that role be temporarily assigned to your account.

### 14. Seed Data Step Fails with `Inappropriate ioctl for device`
**Symptom:** Stage 6 (Env + Seed Data) logs `termios.error: (25, 'Inappropriate ioctl for device')` inside `az containerapp exec`, retries 3 times, then logs a non-fatal `Seeding warning` and moves on.
**Root cause:** `az containerapp exec` always tries to allocate an interactive pseudo-terminal (`tty.setcbreak(sys.stdin.fileno())`). The deploy tool invokes `seed-data-infra-network.sh` via `subprocess.Popen(stdout=PIPE, stderr=PIPE)` ([runner.py](src/cdss_deploy/runner.py)), which has no real TTY on stdin, so the call fails deterministically every time it's run through automation (not just occasionally).
**Fix:** Patched — `seed-data-infra-network.sh` now wraps the `az containerapp exec` call with `script -q /dev/null` (macOS) / `script -qec ... /dev/null` (Linux) to allocate a pseudo-terminal, so seeding succeeds automatically during `cdss-deploy deploy --fresh` without requiring a manual follow-up step. If you're on an older checkout without this fix, run seeding manually from a real terminal:
```bash
az containerapp exec --resource-group cdss-dev-rg --name cdss-dev-api \
  --command "python -m cdss.tools.seed_sample_data"
```

### 15. Dashboard Crashes with `Minified React error #310` After Login
**Symptom:** Frontend shows "This page encountered an error" on the Dashboard page immediately after signing in, with `Error: Minified React error #310` in the browser console (Rendered more hooks than during the previous render).
**Root cause:** [Dashboard.tsx](../cdss-agentic-rag/frontend/src/pages/Dashboard.tsx) had an early `return` (unauthenticated state) positioned *before* several `React.useMemo` calls. Before login, the component skipped those hooks entirely; after login, it suddenly called them — violating React's Rules of Hooks, which require the same hooks to be called in the same order on every render.
**Fix:** Already patched — all `useMemo` calls (audit entries, query entries, trend data, agent latency data) were moved above both early-return checks so hooks are always called unconditionally, regardless of auth or loading state.

### 16. Orchestration Fails with `QueryPlan sub_queries.parallel_dispatch` Validation Error
**Symptom:** Query streaming stalls at "planning progress 15%" then shows `Orchestrator failed to process query: 1 validation error for QueryPlan sub_queries.parallel_dispatch Input should be a valid string [type=string_type, input_value=True, input_type=bool]`.
**Root cause:** GPT-5's structured JSON output for the orchestration plan occasionally nests `"parallel_dispatch": true` *inside* the `"sub_queries"` object instead of as a sibling field. [orchestrator.py](../cdss-agentic-rag/src/cdss/agents/orchestrator.py) passed the raw `sub_queries` dict straight into `QueryPlan` (typed `dict[str, str]`) with no filtering, so the stray boolean value failed Pydantic validation.
**Fix:** Already patched — `sub_queries` is now filtered to only include known agent keys (`patient_history`, `literature`, `protocol`, `drug_safety`) with string values before constructing `QueryPlan`, defensively discarding any unexpected keys the LLM includes. Requires rebuilding and redeploying the backend container image (see "Rebuilding after a backend code change" below).

### 17. Slow Query Orchestration in Dev Environment (Expected, Not a Bug)
**Symptom:** Clinical queries take noticeably longer than expected to complete; "planning progress" appears to sit at low percentages for a while.
**Root cause:** Intentional dev-tier cost optimization — the Container App uses `cpu: 0.5, memory: 1Gi` and `minReplicas: 0` (scale-to-zero) in dev vs. `cpu: 2.0, memory: 4Gi` and `minReplicas: 2` in prod ([main.bicep](../cdss-agentic-rag/infra/bicep/main.bicep), see `environment == 'prod'` conditionals). Requests after any idle period pay a cold-start penalty on top of reduced compute for the 5-agent orchestration.
**Fix:** Not a bug — expected behavior for the dev tier to minimize cost. If faster response times are needed, increase `cpu`/`memory`/`minReplicas` for the dev environment or test against the `prod` parameter file, understanding this increases running cost.

### 18. `--purge` Fails with Key Vault `MethodNotAllowed`
**Symptom:** `cdss-deploy teardown --purge` prints `ERROR: (MethodNotAllowed) Operation 'DeletedVaultPurge' is not allowed.`
**Root cause:** The Key Vault has **purge protection** enabled (separate from soft-delete). Purge protection is an intentional Azure safeguard that blocks manual purge entirely — no CLI flag, script change, or retry can bypass it. The vault is only released once its 90-day soft-delete retention period expires naturally.
**Fix:** Not something this tool can fix — it's an Azure-enforced restriction. If you need the Key Vault *name* freed up sooner, choose a different name (the Bicep `uniqueSuffix` already does this per-region, see #12) rather than waiting on purge.

### 19. `--purge` Appears to Hang on Cognitive Services Purge
**Symptom:** `cdss-deploy teardown --purge` sits at `Purging soft-deleted Cognitive Services account: ...` for what looks like forever.
**Root cause:** `az cognitiveservices account purge` can genuinely take 1-2 minutes to return, and the original implementation used the same 120-second timeout as all other `az` calls in `run_az`, so a slow purge could stall the whole teardown run.
**Fix:** Already patched — purge calls now use a dedicated 30-second timeout (`PURGE_CALL_TIMEOUT_SECONDS` in `s13_teardown.py`, passed via a new `timeout` parameter on `run_az`). If a purge call exceeds 30s, teardown prints a warning and moves on to the next resource instead of blocking; re-run `--purge` later to confirm/retry.

### Rebuilding After a Backend Code Change
If you edit anything under `cdss-agentic-rag/src/`, the running Container App won't pick it up until you rebuild and redeploy the image, then shift traffic to the new revision:
```bash
az acr build --registry <acr-name> --image cdss-api:$(date +%Y.%m.%d.%H%M%S) --image cdss-api:latest .
az containerapp update -g cdss-dev-rg -n cdss-dev-api --image <acr-name>.azurecr.io/cdss-api:<new-tag>
# az containerapp update creates a new revision but does NOT automatically shift traffic to it:
az containerapp revision list -g cdss-dev-rg -n cdss-dev-api -o table
az containerapp ingress traffic set -g cdss-dev-rg -n cdss-dev-api --revision-weight <new-revision-name>=100
```

---

## Lessons Learned

1. **Always use Owner role** — Contributor cannot create RBAC role assignments needed by Bicep
2. **Use ACR cloud build on Apple Silicon** — local Docker cross-compile (ARM → x86_64) uses QEMU emulation which is extremely slow (15-30+ min) and may timeout. ACR cloud build runs on native linux/amd64 hardware and finishes in ~5 minutes
3. **GPT-5 family requires GlobalStandard SKU** — unlike GPT-4o which used Standard. The Bicep template must specify `GlobalStandard` in the deployment SKU
4. **Azure Cache for Redis is retired** — replaced with Azure Managed Redis (`Microsoft.Cache/redisEnterprise`). If you see Redis-related deployment failures, ensure the Bicep template uses the new resource type
5. **Azure RBAC propagation takes 5-10 minutes** — re-login with `az login` after role changes to refresh tokens
6. **Key Vault purge protection prevents name reuse across regions** — include `location` in the `uniqueString()` hash to avoid naming collisions when changing regions
7. **Key Vault network isolation is aggressive** — scripts must temporarily allowlist caller IP, then restore restrictions
8. **All Bicep parameter files must match your target region** — check `parameters.prod.json`, `parameters.dev.json`, and `parameters.staging.json` for hardcoded region values
9. **Never commit `.env`** — use `.env.example` + `.gitignore`, rotate credentials immediately if exposed
10. **Deployment state enables resumability** — JSON checkpoint file means you never re-provision what already succeeded
11. **Admin consent for Entra app registrations requires a tenant admin role** — Owner/Contributor on the subscription is not enough; `az ad app permission admin-consent` needs Global Administrator, Privileged Role Administrator, or Cloud Application Administrator on the directory. Automation can attempt it but cannot guarantee success for arbitrary accounts
12. **Automated subprocess calls to `az containerapp exec` need a pseudo-terminal** — the command always tries to allocate a TTY (`tty.setcbreak`), which fails under `subprocess.Popen(stdout=PIPE)`. Wrap with `script -q /dev/null <cmd>` when invoking from non-interactive automation
13. **React hooks must be called unconditionally, even across auth-loading states** — an early `return` for an unauthenticated view before some (but not all) `useMemo`/`useState` calls will throw "Rendered more hooks than during the previous render" the moment auth state changes. Always place all hooks above any conditional early return
14. **Don't trust LLM structured output to match your schema shape exactly** — GPT-5's JSON plan output nested an unrelated boolean field inside a dict meant to hold only strings. Defensively filter/validate LLM-generated dict/list fields before passing them into strict Pydantic models
15. **`az containerapp update --image` does not shift traffic to the new revision automatically** — always follow up with `az containerapp ingress traffic set --revision-weight <new-revision>=100`, or the old image keeps serving requests silently
16. **Dev-tier `minReplicas: 0` and reduced CPU/memory are intentional, not bugs** — expect slower orchestration and cold-start latency in dev; this is a deliberate cost tradeoff, not a defect to chase
17. **Give each individual purge/long-running `az` call its own bounded timeout, not just the overall loop** — a single slow `az cognitiveservices account purge` sharing the generic 120s `run_az` timeout can make automation look "stuck" for two minutes. Add a per-call `timeout` override for genuinely slow operations so the caller sees the actual behavior sooner
18. **Key Vault purge protection cannot be bypassed by any script** — unlike soft-delete alone, purge protection is an Azure-enforced guarantee. Don't add retry/timeout logic expecting it to eventually succeed; treat `MethodNotAllowed` as terminal and surface it as-is
19. **Discover soft-deleted resources live from Azure APIs, not local state, for any cleanup operation that might run standalone** — local state (JSON checkpoints, etc.) gets reset after teardown completes, so a later `--purge`-only run needs to rediscover what to purge by querying Azure directly, filtered by resource ID/name rather than a cached list
20. **Auto-incremented resource group names (e.g. `cdss-dev-rg2`, `cdss-dev-rg3`) leave orphaned soft-deleted resources that scoped cleanup logic won't find** — when a script only searches within one named resource group, resources from prior auto-incremented runs need their original resource group name extracted from the deleted resource's `id` field and purged individually

---

## Authors

- **Marcos Oliveira** — VP AI/ML Engineering  
  [github.com/MAOFILHO](https://github.com/MAOFILHO)

---

## Disclaimer

> This system is for research and educational purposes only. It is not approved for clinical use. The recommendations generated should not be used as the sole basis for clinical decisions. Always consult qualified healthcare professionals. The authors assume no liability for actions taken based on system output.

---

## License

MIT License — see [LICENSE](LICENSE)
