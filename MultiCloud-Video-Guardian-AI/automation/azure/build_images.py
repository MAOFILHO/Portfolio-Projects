"""
MultiCloud MLOps - Docker Build & Push
Automates Section 9 of the manual guide.

Builds and pushes all 8 images (7 backend microservices + React frontend)
to ACR using Docker Buildx for linux/amd64.

The pipeline (azure-pipelines-app-ci-cd.yml) uses Docker@2 task with
tags: $(Build.BuildId) and latest.  We tag locally as :v1 and :latest
so both pipeline tags and manual runs are present in ACR.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.config import config
from automation.utils.shell import az, get_logger, run, step

log = get_logger("docker")

BUILDER_NAME = "guardian-builder"
PLATFORM     = "linux/amd64"


# ─── 9.1 Buildx ───────────────────────────────────────────────────────────────

def setup_buildx() -> None:
    step("9.1 Setup Docker Buildx")
    run(
        f"docker buildx create --name {BUILDER_NAME} --use 2>/dev/null "
        f"|| docker buildx use {BUILDER_NAME} 2>/dev/null "
        f"|| true",
        description="Create/use guardian-builder",
    )
    run(["docker", "buildx", "inspect", "--bootstrap"],
        description="Bootstrap buildx")
    log.info("✅ Buildx ready: %s", BUILDER_NAME)


# ─── 9.2 Build and push ───────────────────────────────────────────────────────

def _ensure_acr_credentials() -> None:
    """
    If ACR credentials are not in config (e.g. running images stage standalone),
    fetch them from Azure CLI using the ACR name from config/.env.
    """
    if config.azure.acr_username and config.azure.acr_login_server:
        return  # Already loaded

    acr = config.azure.acr_name
    if not acr:
        import sys
        log.error(
            "AZURE_ACR_NAME not set.\n"
            "Fix: add AZURE_ACR_NAME=<your-acr-name> to .env\n"
            "Then run: python setup.py --stage images"
        )
        sys.exit(1)

    from automation.utils.shell import az
    config.azure.acr_login_server = az(
        "acr", "show", "--name", acr, "--query", "loginServer", "--output", "tsv"
    )
    config.azure.acr_username = az(
        "acr", "credential", "show", "--name", acr, "--query", "username", "--output", "tsv"
    )
    config.azure.acr_password = az(
        "acr", "credential", "show", "--name", acr,
        "--query", "passwords[0].value", "--output", "tsv"
    )
    log.info("✅ ACR credentials loaded from CLI: %s", config.azure.acr_login_server)


def _docker_login() -> None:
    _ensure_acr_credentials()
    run(
        ["docker", "login",
         config.azure.acr_login_server,
         "-u", config.azure.acr_username,
         "-p", config.azure.acr_password],
        description="Docker login to ACR",
    )


def _build_service(service: str) -> str:
    context = config.project_root / "services" / service
    if not context.exists():
        log.warning("⚠  services/%s not found — skipping", service)
        return ""

    # Two tags: versioned (:v1) and :latest
    tag_v1     = f"{config.azure.acr_login_server}/guardian-ai-{service}:{config.image_tag}"
    tag_latest = f"{config.azure.acr_login_server}/guardian-ai-{service}:latest"

    run(
        ["docker", "buildx", "build",
         "--platform", PLATFORM,
         "-t", tag_v1,
         "-t", tag_latest,
         "--push",
         str(context)],
        description=f"Build & push {service}",
    )
    log.info("✅ Pushed: %s", tag_v1)
    return tag_v1


def _build_frontend() -> str:
    step("9.2 Build Frontend (npm install → build → push)")
    frontend_dir = config.project_root / "frontend"
    if not frontend_dir.exists():
        log.warning("⚠  frontend/ not found — skipping")
        return ""

    tag_v1     = f"{config.azure.acr_login_server}/guardian-ai-frontend:{config.image_tag}"
    tag_latest = f"{config.azure.acr_login_server}/guardian-ai-frontend:latest"

    run(["npm", "install"], cwd=frontend_dir, description="npm install")
    run(["npm", "run", "build"], cwd=frontend_dir, description="npm run build")
    run(
        ["docker", "buildx", "build",
         "--platform", PLATFORM,
         "-t", tag_v1,
         "-t", tag_latest,
         "--push",
         str(frontend_dir)],
        description="Build & push frontend",
    )
    log.info("✅ Pushed: %s", tag_v1)
    return tag_v1


def build_and_push_all() -> list[str]:
    step("9.2 Build and Push All Service Images")
    _docker_login()

    pushed = []
    for svc in config.services:
        tag = _build_service(svc)
        if tag:
            pushed.append(tag)

    frontend_tag = _build_frontend()
    if frontend_tag:
        pushed.append(frontend_tag)

    return pushed


# ─── 9.3 Verify ───────────────────────────────────────────────────────────────

def verify_images() -> None:
    step("9.3 Verify Images in ACR")
    run(
        ["az", "acr", "repository", "list",
         "--name", config.azure.acr_name, "--output", "table"],
        description="List ACR repos",
    )


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def build_images() -> list[str]:
    log.info("=" * 62)
    log.info("  Docker Build & Push  (Section 9)")
    log.info("  Note: ~15–20 min depending on bandwidth")
    log.info("=" * 62)

    setup_buildx()
    pushed = build_and_push_all()
    verify_images()

    log.info("=" * 62)
    log.info("  ✅ All images built and pushed")
    for t in pushed:
        log.info("  • %s", t)
    log.info("=" * 62)
    return pushed


if __name__ == "__main__":
    build_images()
