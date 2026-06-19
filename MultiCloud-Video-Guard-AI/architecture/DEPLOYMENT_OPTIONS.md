# Guardian AI - Deployment Options Comparison

## Overview

This document compares three deployment options for the Guardian AI MLOps platform, helping you choose the right setup for your learning goals and budget.

---

## Quick Comparison Table

| Feature | **Minimal** (Recommended) | **Standard** | **Full-Featured** |
|---------|---------------------------|--------------|-------------------|
| **Target Audience** | Learners, Students | Small Teams | Enterprise |
| **Monthly Cost** | $10-25 | $125-190 | $250-500 |
| **Setup Time** | 30 min | 2-3 hours | 1-2 days |
| **AWS Services** | 3 (S3, 2 SQS, 2 DynamoDB) | 3 (S3, 2 SQS, 2 DynamoDB) | 5 (S3, 4 SQS, 4 DynamoDB, CloudWatch, Glacier) |
| **Azure Services** | 0 (Local only) | 2-3 (AKS, ACR, Azure ML) | 7+ (AKS, ACR, Azure ML, OpenAI, Front Door, WAF, APIM) |
| **Deployment** | Docker Compose (Local) | Kubernetes (AKS) | Multi-Region Kubernetes |
| **Monitoring** | Docker logs | Prometheus + Grafana | Prometheus + Grafana + App Insights |
| **Azure OpenAI** | ❌ Disabled | ⚠️ Optional | ✅ Enabled |
| **MLOps** | ❌ Basic scripts | ⚠️ Azure ML Registry | ✅ Full Azure ML (A/B, Drift) |
| **GPU Autoscaling** | ❌ N/A | ✅ KEDA | ✅ KEDA + Advanced |
| **High Availability** | ❌ Single instance | ⚠️ Single region | ✅ Multi-region |
| **Learning Value** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

---

## Deployment Option 1: Minimal (Recommended for Learning)

### 🎯 Best For
- Students learning MLOps
- Individual developers
- Proof-of-concept projects
- Budget-conscious learners

### 💰 Cost Breakdown (Monthly)
| Component | Cost |
|-----------|------|
| AWS S3 (100GB) | $3-5 |
| AWS SQS (2 queues) | $0.50-1 |
| AWS DynamoDB (2 tables) | $5-10 |
| Docker Desktop | Free |
| Redis (local) | Free |
| **Total** | **$10-25/month** |

### 🏗️ Architecture
```
Local Machine (Docker Compose)
├── Redis (caching)
├── 6 Microservices (ingestion, fast-screening, deep-vision, policy-engine, human-review, notification)
└── AWS Resources
    ├── S3 (video storage)
    ├── SQS (2 queues)
    └── DynamoDB (2 tables)
```

### ✅ What's Included
- All 6 microservices running locally
- AWS S3 for video storage
- AWS SQS for async processing (2 queues)
- AWS DynamoDB for data storage (2 tables)
- Redis for caching
- Docker Compose orchestration

### ❌ What's Not Included
- Kubernetes deployment
- Azure services
- GPU autoscaling (KEDA)
- Azure OpenAI features
- Production monitoring
- High availability

### 📝 Setup Instructions
```bash
# 1. Setup AWS resources
bash scripts/setup-aws.sh

# 2. Configure environment
cp .env.example .env
# Edit .env with AWS credentials

# 3. Start services
docker-compose up --build

# 4. Test
curl http://localhost:8000/health
```

### 🎓 Learning Outcomes
- ✅ Microservices architecture
- ✅ Docker containerization
- ✅ AWS S3, SQS, DynamoDB basics
- ✅ Async processing with queues
- ✅ NoSQL database design
- ✅ API development with FastAPI
- ✅ Video processing pipelines

### ⏱️ Time Investment
- **Setup**: 30 minutes
- **Learning**: 1-2 weeks
- **Total**: ~20 hours

---

## Deployment Option 2: Standard (Recommended for Production Learning)

### 🎯 Best For
- Teams learning Kubernetes
- Production-like environments
- Portfolio projects
- Job interview preparation

### 💰 Cost Breakdown (Monthly)
| Component | Cost |
|-----------|------|
| AWS S3 (100GB) | $3-5 |
| AWS SQS (2 queues) | $0.50-1 |
| AWS DynamoDB (2 tables) | $10-20 |
| Azure AKS (3 nodes) | $100-150 |
| Azure ACR | $5 |
| Prometheus + Grafana | Free |
| **Total** | **$125-190/month** |

### 🏗️ Architecture
```
Azure AKS Cluster
├── CPU Node Pool
│   ├── Ingestion (3-10 replicas)
│   ├── Fast Screening (5-15 replicas)
│   ├── Policy Engine (3 replicas)
│   ├── Human Review (2 replicas)
│   ├── Notification (2 replicas)
│   └── Redis (1 replica)
├── GPU Node Pool
│   └── Deep Vision (0-5 replicas, KEDA autoscaling)
├── NGINX Ingress Controller
└── Prometheus + Grafana (monitoring)

AWS Resources
├── S3 (video storage)
├── SQS (2 queues)
└── DynamoDB (2 tables)
```

### ✅ What's Included
- Everything from Minimal, plus:
- Kubernetes deployment (AKS)
- Azure Container Registry (ACR)
- GPU autoscaling with KEDA
- NGINX Ingress controller
- Prometheus + Grafana monitoring
- Horizontal Pod Autoscaling (HPA)
- Azure ML Model Registry (optional)

### ❌ What's Not Included
- Azure OpenAI (optional, can enable)
- Multi-region deployment
- Azure Front Door + CDN
- WAF + DDoS protection
- Application Insights
- Advanced Azure ML features

### 📝 Setup Instructions
```bash
# 1. Setup AWS resources
bash scripts/setup-aws.sh

# 2. Setup Azure AKS
bash scripts/setup-aks.sh

# 3. Build and push images
bash scripts/build-services.sh

# 4. Deploy to Kubernetes
kubectl apply -f k8s/

# 5. Verify deployment
kubectl get pods -n production
```

### 🎓 Learning Outcomes
- ✅ Everything from Minimal, plus:
- ✅ Kubernetes deployment and management
- ✅ Container registry (ACR)
- ✅ GPU autoscaling with KEDA
- ✅ Ingress controllers
- ✅ Monitoring with Prometheus + Grafana
- ✅ Horizontal Pod Autoscaling
- ✅ Multi-cloud architecture
- ✅ Production-ready deployments

### ⏱️ Time Investment
- **Setup**: 2-3 hours
- **Learning**: 3-4 weeks
- **Total**: ~60 hours

---

## Deployment Option 3: Full-Featured (Enterprise)

### 🎯 Best For
- Enterprise production deployments
- High-traffic applications
- Multi-region requirements
- Advanced MLOps workflows

### 💰 Cost Breakdown (Monthly)
| Component | Cost |
|-----------|------|
| AWS S3 (1TB + Glacier) | $20-30 |
| AWS SQS (4 queues) | $2-4 |
| AWS DynamoDB (4 tables) | $40-80 |
| AWS CloudWatch | $10-20 |
| Azure AKS (5 nodes) | $200-300 |
| Azure ACR | $5 |
| Azure ML Workspace | $50-100 |
| Azure OpenAI | $20-100 |
| Azure Front Door + CDN | $35-100 |
| Azure WAF | $20-50 |
| Azure API Management | $50-500 |
| Application Insights | $20-50 |
| **Total** | **$500-1500/month** |

### 🏗️ Architecture
```
Multi-Region Deployment
├── Azure Front Door + CDN (global)
├── WAF + DDoS Protection
├── API Management
└── Region 1 (Primary)
    ├── AKS Cluster (5 nodes)
    │   ├── CPU Node Pool (all services)
    │   ├── GPU Node Pool (KEDA autoscaling)
    │   └── Monitoring Stack
    ├── Azure ML Workspace
    │   ├── Model Training
    │   ├── Model Registry
    │   ├── A/B Testing
    │   └── Drift Detection
    └── Azure OpenAI (GPT-4o)
        ├── Human Review Copilot
        ├── Policy Interpretation
        └── Explanation Generation

AWS Resources (Multi-Region)
├── S3 (primary + replication)
├── SQS (4 queues)
├── DynamoDB (4 tables + global tables)
└── CloudWatch (monitoring)
```

### ✅ What's Included
- Everything from Standard, plus:
- Azure Front Door + CDN
- WAF + DDoS protection
- API Management
- Azure Durable Functions
- Application Insights + Log Analytics
- Azure OpenAI (enabled by default)
- Full Azure ML platform (A/B testing, drift detection)
- S3 Glacier lifecycle
- 4 SQS queues (all features)
- 4 DynamoDB tables (full schema)
- Multi-region deployment
- Advanced security features

### ❌ What's Not Included
- Nothing - this is the full enterprise setup

### 📝 Setup Instructions
```bash
# 1. Setup AWS resources (full)
bash scripts/setup-aws-full.sh

# 2. Setup Azure resources (full)
bash scripts/setup-azure-full.sh

# 3. Setup multi-region
bash scripts/setup-multi-region.sh

# 4. Deploy services
bash scripts/deploy-production.sh

# 5. Configure monitoring
bash scripts/setup-monitoring.sh
```

### 🎓 Learning Outcomes
- ✅ Everything from Standard, plus:
- ✅ Multi-region architecture
- ✅ CDN and edge computing
- ✅ WAF and DDoS protection
- ✅ API Management
- ✅ Advanced MLOps (A/B testing, drift detection)
- ✅ LLM integration (Azure OpenAI)
- ✅ Enterprise security
- ✅ Advanced monitoring and alerting

### ⏱️ Time Investment
- **Setup**: 1-2 days
- **Learning**: 2-3 months
- **Total**: ~200 hours

---

## Feature Comparison Matrix

| Feature | Minimal | Standard | Full-Featured |
|---------|---------|----------|---------------|
| **Infrastructure** |
| Docker Compose | ✅ | ❌ | ❌ |
| Kubernetes (AKS) | ❌ | ✅ | ✅ |
| Multi-Region | ❌ | ❌ | ✅ |
| **AWS Services** |
| S3 | ✅ | ✅ | ✅ |
| SQS Queues | 2 | 2 | 4 |
| DynamoDB Tables | 2 | 2 | 4 |
| CloudWatch | ❌ | ❌ | ✅ |
| S3 Glacier | ❌ | ⚠️ Optional | ✅ |
| **Azure Services** |
| AKS | ❌ | ✅ | ✅ |
| ACR | ❌ | ✅ | ✅ |
| Azure ML | ❌ | ⚠️ Basic | ✅ Full |
| Azure OpenAI | ❌ | ⚠️ Optional | ✅ |
| Front Door + CDN | ❌ | ❌ | ✅ |
| WAF + DDoS | ❌ | ❌ | ✅ |
| API Management | ❌ | ❌ | ✅ |
| App Insights | ❌ | ❌ | ✅ |
| **Features** |
| Video Upload | ✅ | ✅ | ✅ |
| CPU Screening | ✅ | ✅ | ✅ |
| GPU Analysis | ✅ Local | ✅ KEDA | ✅ KEDA + Advanced |
| Human Review | ✅ | ✅ | ✅ + AI Copilot |
| Notifications | ✅ HTTP | ✅ HTTP | ✅ SQS + HTTP |
| Caching (Redis) | ✅ | ✅ | ✅ |
| **Monitoring** |
| Docker Logs | ✅ | ✅ | ✅ |
| Prometheus + Grafana | ❌ | ✅ | ✅ |
| Application Insights | ❌ | ❌ | ✅ |
| CloudWatch | ❌ | ❌ | ✅ |
| **MLOps** |
| Model Training | ✅ Local | ✅ Azure ML | ✅ Azure ML |
| Model Registry | ❌ | ⚠️ Optional | ✅ |
| A/B Testing | ❌ | ❌ | ✅ |
| Drift Detection | ❌ | ❌ | ✅ |
| Auto Rollback | ❌ | ❌ | ✅ |
| **Security** |
| Basic Auth | ✅ | ✅ | ✅ |
| Network Policies | ❌ | ✅ | ✅ |
| WAF | ❌ | ❌ | ✅ |
| DDoS Protection | ❌ | ❌ | ✅ |
| **Scalability** |
| Manual Scaling | ✅ | ❌ | ❌ |
| HPA (CPU) | ❌ | ✅ | ✅ |
| KEDA (GPU) | ❌ | ✅ | ✅ |
| Multi-Region | ❌ | ❌ | ✅ |

---

## Recommendation by Use Case

### For Learning MLOps Basics
**Choose: Minimal**
- Lowest cost ($10-25/month)
- Fastest setup (30 minutes)
- Focus on core concepts
- Perfect for students

### For Job Interview Preparation
**Choose: Standard**
- Production-like environment
- Kubernetes experience
- Reasonable cost ($125-190/month)
- Portfolio-worthy project

### For Enterprise Production
**Choose: Full-Featured**
- All enterprise features
- High availability
- Advanced security
- Full MLOps lifecycle

---

## Migration Path

### From Minimal → Standard
```bash
# 1. Setup Azure AKS
bash scripts/setup-aks.sh

# 2. Build and push images
bash scripts/build-services.sh

# 3. Deploy to Kubernetes
kubectl apply -f k8s/

# 4. Migrate data (if needed)
bash scripts/migrate-data.sh
```

**Time**: 2-3 hours
**Additional Cost**: +$100-165/month

### From Standard → Full-Featured
```bash
# 1. Setup additional AWS resources
bash scripts/setup-aws-full.sh

# 2. Setup Azure Front Door + WAF
bash scripts/setup-azure-full.sh

# 3. Enable Azure OpenAI
# Edit .env: AZURE_OPENAI_ENABLED=true

# 4. Setup Azure ML advanced features
bash scripts/setup-mlops-advanced.sh

# 5. Configure multi-region
bash scripts/setup-multi-region.sh
```

**Time**: 1-2 days
**Additional Cost**: +$300-1000/month

---

## Cost Optimization Tips

### For All Deployments
1. **Delete old videos**: Setup S3 lifecycle policies
2. **Purge SQS queues**: When not in use
3. **Monitor DynamoDB usage**: Switch to provisioned capacity if predictable
4. **Use spot instances**: For GPU nodes (70% cost savings)

### For Standard & Full-Featured
5. **Scale down AKS**: During off-hours
6. **Use Azure Reserved Instances**: 30-50% savings
7. **Disable Azure OpenAI**: When not needed
8. **Use single region**: Unless HA required

---

## Summary

| Deployment | Best For | Cost | Time | Learning Value |
|------------|----------|------|------|----------------|
| **Minimal** | Students, POC | $10-25/mo | 30 min | ⭐⭐⭐⭐⭐ |
| **Standard** | Production Learning | $125-190/mo | 2-3 hrs | ⭐⭐⭐⭐ |
| **Full-Featured** | Enterprise | $500-1500/mo | 1-2 days | ⭐⭐⭐ |

**Recommendation for Learners**: Start with **Minimal**, then upgrade to **Standard** when ready for Kubernetes.

---

**Last Updated**: 2026
**Version**: 2.0 (Simplified)
