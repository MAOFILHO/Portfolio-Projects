"""
MultiCloud MLOps - Central Configuration
Reads from .env file and environment variables.
All module-level constants are derived from here — nothing is hardcoded elsewhere.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# .env lives at project root (parent of automation/)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)


# ─── Sub-configs ──────────────────────────────────────────────────────────────

@dataclass
class AWSConfig:
    access_key_id: str     = field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID", ""))
    secret_access_key: str = field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY", ""))
    region: str            = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    # Populated at runtime
    account_id: str        = ""
    s3_bucket_name: str    = field(default_factory=lambda: os.getenv("S3_BUCKET_NAME", ""))
    sqs_queue_url: str     = field(default_factory=lambda: os.getenv("SQS_QUEUE_URL", ""))
    sqs_gpu_queue_url: str = field(default_factory=lambda: os.getenv("SQS_GPU_QUEUE_URL", ""))
    # DynamoDB — keys must match actual table primary key names in the service code
    dynamodb_videos_table: str = "guardian-videos"    # PK: video_id
    dynamodb_events_table: str = "guardian-events"    # PK: event_id


@dataclass
class AzureConfig:
    subscription_id: str = field(default_factory=lambda: os.getenv("AZURE_SUBSCRIPTION_ID", ""))
    resource_group: str  = field(default_factory=lambda: os.getenv("AZURE_RESOURCE_GROUP", "guardian-ai-prod"))
    location: str        = field(default_factory=lambda: os.getenv("AZURE_LOCATION", "eastus"))
    # ACR — auto-generated from timestamp if blank
    acr_name: str        = field(default_factory=lambda: os.getenv("AZURE_ACR_NAME", ""))
    aks_cluster: str     = field(default_factory=lambda: os.getenv("AZURE_AKS_CLUSTER", "guardian-ai-aks"))
    # Populated after ACR creation
    acr_login_server: str = ""
    acr_username: str     = ""
    acr_password: str     = ""
    external_ip: str      = ""


@dataclass
class AzureDevOpsConfig:
    organization_name: str    = field(default_factory=lambda: os.getenv("AZDO_ORG_NAME", "guardian-ai-org"))
    project_name: str         = field(default_factory=lambda: os.getenv("AZDO_PROJECT_NAME", "guardian-ai-mlops"))
    pat_token: str            = field(default_factory=lambda: os.getenv("AZDO_PAT_TOKEN", ""))
    github_repo_url: str      = "https://github.com/k21academyuk/MultiCloud_MLOps.git"
    # Service connection names — must match what the pipeline YAMLs reference
    azure_sc_name: str        = "guardian-azure-connection"
    acr_sc_name: str          = "guardian-acr-connection"
    aks_sc_name: str          = "guardian-aks-connection"
    # Variable group name — must match `- group:` in pipeline YAMLs
    variable_group_name: str  = "guardian-variables"
    # Pipeline YAML paths (relative to repo root) — must match actual files in repo
    app_pipeline_yaml: str    = "/azure-pipelines-app-ci-cd.yml"
    ml_training_yaml: str     = "/azure-pipelines-ml-training.yml"
    ml_deployment_yaml: str   = "/azure-pipelines-ml-deployment.yml"


@dataclass
class AzureMLConfig:
    workspace_name: str       = field(default_factory=lambda: os.getenv("AZURE_ML_WORKSPACE", "guardian-ai-ml-workspace-prod"))
    compute_cluster_name: str = field(default_factory=lambda: os.getenv("AZURE_ML_COMPUTE_CLUSTER", "cpu-training-cluster"))
    compute_vm_size: str      = "Standard_DS1_v2"
    compute_min_nodes: int    = 0
    compute_max_nodes: int    = 2
    compute_idle_seconds: int = 120
    nsfw_endpoint_name: str   = "nsfw-detector-endpoint"
    violence_endpoint_name: str = "violence-detector-endpoint"


@dataclass
class KubernetesConfig:
    namespace: str = "production"
    k8s_dir: str   = "k8s"


@dataclass
class ProjectConfig:
    aws:    AWSConfig          = field(default_factory=AWSConfig)
    azure:  AzureConfig        = field(default_factory=AzureConfig)
    devops: AzureDevOpsConfig  = field(default_factory=AzureDevOpsConfig)
    ml:     AzureMLConfig      = field(default_factory=AzureMLConfig)
    k8s:    KubernetesConfig   = field(default_factory=KubernetesConfig)
    project_root: Path         = field(default_factory=lambda: Path(__file__).parent.parent)
    # Microservices to build — matches services/ subdirectory names in repo
    services: list = field(default_factory=lambda: [
        "ingestion",
        "fast-screening",
        "deep-vision",
        "policy-engine",
        "human-review",
        "notification",
        "api-gateway",
    ])
    image_tag: str = "v1"


# Singleton — import this everywhere
config = ProjectConfig()
