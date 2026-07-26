from __future__ import annotations

from datetime import datetime, timezone

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import run as run_command
from surveil_deploy.state import DeploymentState

STEP_NAME = "s05_build_backend"
STEP_TITLE = "Building and deploying the backend container image"

IMAGE_NAME = "surveil-backend"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(5, 12, STEP_TITLE)

    outputs = state.resource_outputs
    registry_name = outputs["CONTAINER_REGISTRY_NAME"]
    login_server = outputs["CONTAINER_REGISTRY_LOGIN_SERVER"]
    resource_group = outputs["AZURE_RESOURCE_GROUP"]
    container_app_name = outputs["CONTAINER_APP_NAME"]

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    image_tagged = f"{IMAGE_NAME}:{tag}"
    image_latest = f"{IMAGE_NAME}:latest"
    full_image = f"{login_server}/{image_latest}"
    # Deploy from the unique per-build tag, not `:latest` -- observed in
    # production (see s06_deploy_ingestor.py) that Container Apps can skip
    # creating a new revision when the image reference string in the
    # template is unchanged, even though the underlying digest behind
    # `:latest` did change: `containerapp update` reports success, but the
    # already-running replica is never restarted. `:latest` is still pushed
    # alongside this, for anyone pulling it manually.
    full_image_tagged = f"{login_server}/{image_tagged}"

    if config.image_build_mode == "local":
        log_info("IMAGE_BUILD_MODE=local — building with local Docker (cross-compile may be slow on Apple Silicon)")
        run_command(["docker", "build", "--platform", "linux/amd64", "-f", "backend/Dockerfile",
                     "-t", f"{login_server}/{image_tagged}", "-t", full_image, str(config.source_dir)],
                    cwd=config.source_dir)
        run_command(["az", "acr", "login", "--name", registry_name])
        run_command(["docker", "push", f"{login_server}/{image_tagged}"])
        run_command(["docker", "push", full_image])
    else:
        log_info(f"IMAGE_BUILD_MODE=acr — building {image_tagged} in Azure Container Registry (native amd64, no local cross-compile)")
        run_command(
            [
                "az", "acr", "build",
                "--registry", registry_name,
                "--image", image_tagged,
                "--image", image_latest,
                "--file", "backend/Dockerfile",
                ".",
            ],
            cwd=config.source_dir,
        )

    log_success(f"Image built: {full_image}")

    log_info(f"Updating Container App {container_app_name} to use the new image")
    run_command([
        "az", "containerapp", "update",
        "--name", container_app_name,
        "--resource-group", resource_group,
        "--image", full_image_tagged,
    ])
    # This Container App runs in `activeRevisionsMode: Single` (see
    # containerapp.bicep) -- Azure automatically routes 100% of traffic to
    # whatever revision `containerapp update` just created. Manually setting
    # a traffic weight is only valid (and only necessary) in Multiple
    # revisions mode, and errors out here.

    log_success(f"Backend deployed: {image_tagged}")
    return {"BACKEND_IMAGE": full_image_tagged}
