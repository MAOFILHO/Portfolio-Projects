from __future__ import annotations

from datetime import datetime, timezone

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import run as run_command
from surveil_deploy.state import DeploymentState

STEP_NAME = "s06_deploy_ingestor"
STEP_TITLE = "Deploying the Nest doorbell ingestor (opt-in)"

IMAGE_NAME = "surveil-nest-ingestor"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(6, 12, STEP_TITLE)

    outputs = state.resource_outputs
    if not config.nest_ingestor_enabled or outputs.get("NEST_INGESTOR_ENABLED") != "True":
        log_info("NEST_INGESTOR_ENABLED is false -- skipping (see .env.example to opt in)")
        return {}

    registry_name = outputs["CONTAINER_REGISTRY_NAME"]
    login_server = outputs["CONTAINER_REGISTRY_LOGIN_SERVER"]
    resource_group = outputs["AZURE_RESOURCE_GROUP"]
    container_app_name = outputs["NEST_INGESTOR_CONTAINER_APP_NAME"]

    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    image_tagged = f"{IMAGE_NAME}:{tag}"
    image_latest = f"{IMAGE_NAME}:latest"
    full_image = f"{login_server}/{image_latest}"
    # Deploy from the unique per-build tag, not `:latest` -- Container Apps
    # decides whether to create a new revision by diffing the *image
    # reference string* in the template, not the underlying image digest.
    # Pointing at `:latest` on every deploy leaves that string unchanged,
    # so `az containerapp update` silently no-ops: the command succeeds,
    # but the already-running replica is never restarted and keeps serving
    # the old code indefinitely. `:latest` is still pushed alongside this,
    # for anyone pulling it manually.
    full_image_tagged = f"{login_server}/{image_tagged}"

    if config.image_build_mode == "local":
        log_info("IMAGE_BUILD_MODE=local — building with local Docker (cross-compile may be slow on Apple Silicon)")
        run_command(["docker", "build", "--platform", "linux/amd64", "-f", "ingestors/nest/Dockerfile",
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
                "--file", "ingestors/nest/Dockerfile",
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

    log_success(f"Nest ingestor deployed: {image_tagged}")
    return {"NEST_INGESTOR_IMAGE": full_image_tagged}
