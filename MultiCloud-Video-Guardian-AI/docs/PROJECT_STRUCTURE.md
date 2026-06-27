# Project Structure

```
MLOps_Project/
├── README.md                          # Main documentation
├── ARCHITECTURE_CORRECTED.md          # System architecture diagrams
├── QUICKSTART.md                      # Quick start guide
├── LICENSE                            # MIT License
├── .gitignore                         # Git ignore rules
├── .env.example                       # Environment variables template
├── docker-compose.yml                 # Local development setup
│
├── .github/
│   └── workflows/
│       └── deploy.yml                 # CI/CD pipeline
│
├── services/                          # Microservices
│   ├── ingestion/                     # Video upload service
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── fast-screening/                # CPU-based screening
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── deep-vision/                   # GPU-based analysis
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── policy-engine/                 # Decision logic
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── human-review/                  # Review queue
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── notification/                  # Webhook delivery
│       ├── app.py
│       ├── requirements.txt
│       └── Dockerfile
│
├── k8s/                               # Kubernetes manifests
│   ├── namespace.yaml
│   ├── cpu-services/
│   │   ├── fast-screening.yaml
│   │   ├── policy-engine.yaml
│   │   └── redis.yaml
│   ├── gpu-services/
│   │   └── deep-vision.yaml
│   └── overlays/
│       ├── staging/
│       └── production/
│
├── mlops/                             # MLOps platform
│   ├── training/
│   │   └── train_nsfw_model.py
│   ├── deployment/
│   │   ├── deploy_model.py
│   │   └── rollback_model.py
│
├── infrastructure/                    # Infra assets
│   ├── helm/
│   └── aws-lifecycle.json
│
├── scripts/                           # Automation scripts
│   ├── init-project.sh
│   ├── setup-azure.sh
│   ├── setup-aws.sh
│   ├── update-k8s-config.sh           # Auto-populate K8s ConfigMap with AWS values
│   ├── update-acr-in-manifests.sh     # Replace ACR_PLACEHOLDER in k8s manifests with $ACR_NAME
│   ├── setup-aks.sh
│   ├── setup-mlops.sh
│   ├── build-services.sh
│   ├── production-hardening.sh
│   ├── load-test.sh
│   └── setup-cicd-secrets.sh
│
├── tests/                             # Testing
│   ├── unit/
│   ├── integration/
│   └── load/
│       └── load-test.js
│
└── docs/                              # Additional documentation
```

## Service Ports

| Service | Port | Type |
|---------|------|------|
| Ingestion | 8000 | CPU |
| Fast Screening | 8001 | CPU |
| Deep Vision | 8002 | GPU |
| Policy Engine | 8003 | CPU |
| Human Review | 8004 | CPU |
| Notification | 8005 | CPU |
| Redis | 6379 | Cache |

## Key Files

- **docker-compose.yml**: Local development environment
- **k8s/cpu-services/**: Always-on CPU workloads
- **k8s/gpu-services/**: Scale-to-zero GPU workloads
- **mlops/**: Model training and deployment
- **scripts/**: Infrastructure automation
