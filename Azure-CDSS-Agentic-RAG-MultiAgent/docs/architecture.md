# Architecture Overview

## Deployment Pipeline

```
cdss-deploy deploy
       |
       v
  [Preflight] → [Azure Login] → [Collect Secrets]
       |
       v
  [bootstrap-deploy.sh]  ← wraps existing battle-tested scripts
       |
       ├── Docker build + push to ACR
       ├── Bicep deployment (56+ Azure resources)
       ├── Search index bootstrap (3 indexes)
       ├── Cosmos DB vector policy fix
       └── OpenAI network compatibility
       |
       v
  [Resolve Names] → [Health Check] → [Env + Seed Data]
       |
       v
  [Entra Auth] → [PubMed Config] → [Frontend Build + Deploy]
       |
       v
  [CORS + Redirects] → [E2E Validation]
       |
       v
  DEPLOYMENT COMPLETE
```

## Azure Resource Topology

```
Resource Group (cdss-prod-rg)
├── VNet (10.0.0.0/16)
│   ├── app-subnet (10.0.1.0/24) → Container Apps
│   ├── data-subnet (10.0.2.0/24) → Cosmos DB, Storage (private endpoints)
│   ├── ai-subnet (10.0.3.0/24) → OpenAI, Doc Intelligence (private endpoints)
│   └── integration-subnet (10.0.4.0/24) → Reserved
│
├── Compute
│   ├── Container Apps Environment
│   ├── Container App (FastAPI backend, port 8000)
│   └── Container Registry (ACR)
│
├── AI / ML
│   ├── Azure OpenAI (GPT-4o, GPT-4o-mini, text-embedding-3-large)
│   ├── Azure AI Search (patient-records, treatment-protocols, medical-literature-cache)
│   └── Azure Document Intelligence
│
├── Data
│   ├── Cosmos DB (patient-profiles, conversation-history, embedding-cache, audit-log, agent-state)
│   ├── Blob Storage (staging-documents, treatment-protocols, processed)
│   └── Redis Cache
│
├── Security
│   ├── Managed Identity (user-assigned, RBAC to all services)
│   ├── Key Vault (API keys, connection strings)
│   └── NSGs (4 subnet-level security groups)
│
├── Monitoring
│   ├── Log Analytics Workspace
│   └── Application Insights
│
├── Frontend
│   └── Static Web App (React SPA)
│
└── Identity
    ├── Entra App Registration (SPA - frontend)
    └── Entra App Registration (API - backend)
```

## Agent Execution Flow

```
Clinical Query → Orchestrator (GPT-4o)
                     |
          ┌──────────┼──────────────┐
          |          |              |
     Query Plan     Task          Task
     Generation    Assignment    Assignment
          |          |              |
          v          v              v
  ┌─────────────────────────────────────┐
  │       asyncio.gather (parallel)     │
  │                                     │
  │  Patient History  Medical Lit.      │
  │  Protocol Agent   Drug Safety       │
  │                   Guardrails        │
  └────────────────┬────────────────────┘
                   |
              Fusion + Rerank
                   |
              Final Synthesis
                   |
         ClinicalResponse + Citations
```
