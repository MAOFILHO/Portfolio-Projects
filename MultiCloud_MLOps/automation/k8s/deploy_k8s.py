"""
MultiCloud MLOps - Kubernetes Deployment
Automates Sections 10–11 of the manual guide.

  10.1  Write ConfigMap with live AWS resource URLs
  10.2  Patch ACR references in all k8s YAMLs
  10.3  Ensure ACR attached to AKS
  10.4  Create 'production' namespace
  10.5  Create aws-secrets Kubernetes Secret
  11.x  Deploy: ConfigMap → Redis → CPU services → Frontend → Ingress
  11.1  End-to-end health-check
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.config import config
from automation.utils.shell import aws, get_logger, run, run_or_skip, step

log = get_logger("k8s")


# ─── 10.1 ConfigMap ───────────────────────────────────────────────────────────

def write_configmap(aws_resources: dict) -> None:
    """Generate k8s/configmap.yaml with live AWS resource values."""
    step("10.1 Update Kubernetes ConfigMap")

    region     = aws_resources.get("AWS_REGION",        config.aws.region)
    bucket     = aws_resources.get("S3_BUCKET_NAME",    config.aws.s3_bucket_name)
    sqs_url    = aws_resources.get("SQS_QUEUE_URL",     config.aws.sqs_queue_url)
    gpu_url    = aws_resources.get("SQS_GPU_QUEUE_URL", config.aws.sqs_gpu_queue_url)

    yaml_content = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: guardian-config
  namespace: {config.k8s.namespace}
data:
  # AWS Configuration
  AWS_REGION: "{region}"
  S3_BUCKET_NAME: "{bucket}"

  # SQS Queues
  SQS_QUEUE_URL: "{sqs_url}"
  SQS_GPU_QUEUE_URL: "{gpu_url}"

  # DynamoDB Tables (PK: video_id / event_id)
  DYNAMODB_VIDEOS_TABLE: "guardian-videos"
  DYNAMODB_EVENTS_TABLE: "guardian-events"

  # Service Configuration
  LOG_LEVEL: "INFO"
  AUTO_APPROVE_THRESHOLD: "0.2"
  AUTO_REJECT_THRESHOLD: "0.8"

  # Redis
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"

  # Azure OpenAI (set to true and add key secret to enable)
  AZURE_OPENAI_ENABLED: "false"

  # Internal service URLs
  NOTIFICATION_SERVICE_URL: "http://notification:8005"
  HUMAN_REVIEW_SERVICE_URL: "http://human-review:8004"
  POLICY_ENGINE_SERVICE_URL: "http://policy-engine-service:80"
"""
    configmap_path = config.project_root / "k8s" / "configmap.yaml"
    configmap_path.write_text(yaml_content)
    log.info("✅ ConfigMap written: %s", configmap_path)


# ─── 10.2 ACR refs ────────────────────────────────────────────────────────────

def patch_acr_in_manifests() -> None:
    """Replace hardcoded ACR server in k8s YAMLs with current ACR login server."""
    step("10.2 Patch ACR References in k8s Manifests")
    k8s_dir    = config.project_root / "k8s"
    acr_server = config.azure.acr_login_server or f"{config.azure.acr_name}.azurecr.io"

    import platform
    if platform.system() == "Darwin":
        sed_flag = "sed -i ''"
    else:
        sed_flag = "sed -i"

    run(
        f"find {k8s_dir} -name '*.yaml' -exec "
        f"{sed_flag} 's|[a-z0-9]*\\.azurecr\\.io|{acr_server}|g' {{}} +",
        description="Replace ACR server in k8s YAMLs",
    )
    log.info("✅ k8s manifests patched: %s", acr_server)


# ─── 10.3 ACR ↔ AKS ──────────────────────────────────────────────────────────

def ensure_acr_attached() -> None:
    step("10.3 Ensure ACR Attached to AKS")
    attached = run(
        ["az", "aks", "check-acr",
         "--name", config.azure.aks_cluster,
         "--resource-group", config.azure.resource_group,
         "--acr", f"{config.azure.acr_name}.azurecr.io"],
        capture=True, check=False,
    ).returncode == 0

    if attached:
        log.info("✅ ACR already attached to AKS")
    else:
        run(
            ["az", "aks", "update",
             "--name", config.azure.aks_cluster,
             "--resource-group", config.azure.resource_group,
             "--attach-acr", config.azure.acr_name],
            description="Attach ACR to AKS",
        )
        log.info("✅ ACR attached to AKS")


# ─── 10.4 Namespace ───────────────────────────────────────────────────────────

def create_namespace() -> None:
    step("10.4 Create Kubernetes Namespace")
    ns = config.k8s.namespace
    # Apply namespace.yaml if it exists (repo has one)
    ns_yaml = config.project_root / "k8s" / "namespace.yaml"
    if ns_yaml.exists():
        run_or_skip(
            ["kubectl", "apply", "-f", str(ns_yaml)],
            description="Apply namespace.yaml",
        )
    else:
        run_or_skip(
            ["kubectl", "create", "namespace", ns],
            description=f"Create namespace {ns}",
        )
    run(["kubectl", "get", "namespaces"])
    log.info("✅ Namespace ready: %s", ns)


# ─── 10.5 AWS Secrets ────────────────────────────────────────────────────────

def create_aws_secrets() -> None:
    step("10.5 Create AWS Credentials Secret")
    ns          = config.k8s.namespace
    access_key  = aws("configure", "get", "aws_access_key_id")
    secret_key  = aws("configure", "get", "aws_secret_access_key")

    run_or_skip(
        ["kubectl", "delete", "secret", "aws-secrets", "-n", ns],
        description="Delete old aws-secrets",
    )
    run(
        ["kubectl", "create", "secret", "generic", "aws-secrets",
         f"--from-literal=AWS_ACCESS_KEY_ID={access_key}",
         f"--from-literal=AWS_SECRET_ACCESS_KEY={secret_key}",
         "-n", ns],
        description="Create aws-secrets",
    )
    run(["kubectl", "get", "secrets", "-n", ns], description="List secrets")
    log.info("✅ aws-secrets created in namespace: %s", ns)


# ─── 11. Deploy services ──────────────────────────────────────────────────────

def _apply(path: str, label: str = "") -> None:
    full = config.project_root / path
    if not full.exists():
        log.warning("⚠  Not found, skipping: %s", full)
        return
    run(["kubectl", "apply", "-f", str(full)],
        description=label or f"Apply {path}")


def deploy_all() -> None:
    step("11 Deploy All Services to Kubernetes")
    ns = config.k8s.namespace

    _apply("k8s/configmap.yaml",                            "Deploy ConfigMap")
    run(["kubectl", "get", "configmap", "-n", ns])

    _apply("k8s/cpu-services/redis.yaml",                   "Deploy Redis")
    _apply("k8s/cpu-services/ingestion-deployment.yaml",    "Deploy ingestion")
    _apply("k8s/cpu-services/fast-screening.yaml",          "Deploy fast-screening")
    _apply("k8s/cpu-services/policy-engine.yaml",           "Deploy policy-engine")
    _apply("k8s/cpu-services/human-review-deployment.yaml", "Deploy human-review")
    _apply("k8s/cpu-services/api-gateway.yaml",             "Deploy api-gateway")
    _apply("k8s/cpu-services/deep-vision.yaml",             "Deploy deep-vision")
    _apply("k8s/frontend/frontend-deployment.yaml",         "Deploy frontend")
    _apply("k8s/ingress.yaml",                              "Deploy Ingress")

    log.info("Waiting 30 s for pods to schedule…")
    time.sleep(30)

    run(["kubectl", "get", "pods",        "-n", ns], description="All pods")
    run(["kubectl", "get", "svc",         "-n", ns], description="All services")
    run(["kubectl", "get", "deployments", "-n", ns], description="All deployments")
    run(["kubectl", "get", "ingress",     "-n", ns], description="Ingress")

    log.info("✅ All manifests applied")


# ─── 11.1 Health check ───────────────────────────────────────────────────────

def health_check() -> None:
    step("11.1 End-to-End Health Check")
    ip = config.azure.external_ip
    if not ip:
        r = run(
            ["kubectl", "get", "svc", "-n", "ingress-nginx",
             "ingress-nginx-controller",
             "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"],
            capture=True, check=False,
        )
        ip = r.stdout.strip()
        config.azure.external_ip = ip

    if ip:
        log.info("Application URL: http://%s", ip)
        run_or_skip(["curl", "-sI", f"http://{ip}"],
                    description="HTTP health check")
    else:
        log.warning("⚠  External IP not yet available — "
                    "run: kubectl get svc -n ingress-nginx")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def deploy_kubernetes(aws_resources: dict | None = None) -> None:
    log.info("=" * 62)
    log.info("  Kubernetes Deployment  (Sections 10–11)")
    log.info("=" * 62)

    aws_resources = aws_resources or {}

    write_configmap(aws_resources)
    patch_acr_in_manifests()
    ensure_acr_attached()
    create_namespace()
    create_aws_secrets()
    deploy_all()
    health_check()

    log.info("=" * 62)
    log.info("  ✅ Kubernetes deployment complete")
    log.info("  App URL: http://%s", config.azure.external_ip or "(pending)")
    log.info("=" * 62)


if __name__ == "__main__":
    deploy_kubernetes()
