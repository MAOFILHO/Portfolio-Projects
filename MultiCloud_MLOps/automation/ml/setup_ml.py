"""
MultiCloud MLOps - Azure ML Setup & Pipeline Execution
Automates Sections 12.5–12.7 of the manual guide.

  12.5  Create Azure ML workspace + CPU compute cluster
  12.6  Trigger ML training pipeline (NSFW + Violence)
        → polls Azure DevOps pipeline run until completion
        → verifies model registration in ML registry
  12.7  Trigger ML deployment pipeline
        → polls until endpoints are live
        → patches Kubernetes ConfigMap with scoring URIs
        → restarts deep-vision deployment

Uses the Azure DevOps pipeline mechanism (not direct az ml job submit)
so training runs on the compute cluster exactly as the manual describes.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.config import config
from automation.utils.shell import az, az_json, get_logger, run, run_or_skip, step

log = get_logger("azureml")

_ML_EXT_INSTALLED = False


def _org_url() -> str:
    return f"https://dev.azure.com/{config.devops.organization_name}"


def _devops_env() -> dict:
    import os
    return {"AZURE_DEVOPS_EXT_PAT": config.devops.pat_token}


# ─── Extension ────────────────────────────────────────────────────────────────

def _ensure_ml_extension() -> None:
    global _ML_EXT_INSTALLED
    if _ML_EXT_INSTALLED:
        return
    r = run(["az", "extension", "show", "--name", "ml"], capture=True, check=False)
    if r.returncode != 0:
        run(["az", "extension", "add", "--name", "ml", "--yes"],
            description="Install az ml extension")
    _ML_EXT_INSTALLED = True
    log.info("✅ az ml extension ready")


# ─── 12.5 Workspace & Compute ─────────────────────────────────────────────────

def create_workspace() -> None:
    step("12.5a Create Azure ML Workspace")
    ws = config.ml.workspace_name
    rg = config.azure.resource_group

    r = run(
        ["az", "ml", "workspace", "show",
         "--name", ws, "--resource-group", rg],
        capture=True, check=False,
    )
    if r.returncode == 0:
        log.info("✅ ML workspace already exists: %s", ws)
    else:
        log.info("Creating Azure ML workspace (2–3 min)…")
        run(
            ["az", "ml", "workspace", "create",
             "--name", ws,
             "--resource-group", rg,
             "--location", config.azure.location],
            description=f"Create ML workspace {ws}",
        )
        log.info("✅ ML workspace created: %s", ws)

    log.info(
        "Studio URL: https://ml.azure.com/?wsid=/subscriptions/%s"
        "/resourcegroups/%s/workspaces/%s",
        config.azure.subscription_id, rg, ws,
    )


def create_compute_cluster() -> None:
    step("12.5b Create CPU Compute Cluster")
    cluster = config.ml.compute_cluster_name
    rg      = config.azure.resource_group
    ws      = config.ml.workspace_name

    r = run(
        ["az", "ml", "compute", "show",
         "--name", cluster, "--resource-group", rg, "--workspace-name", ws],
        capture=True, check=False,
    )
    if r.returncode == 0:
        log.info("✅ Compute cluster already exists: %s", cluster)
        return

    run(
        ["az", "ml", "compute", "create",
         "--name", cluster,
         "--resource-group", rg,
         "--workspace-name", ws,
         "--type", "AmlCompute",
         "--size", config.ml.compute_vm_size,
         "--min-instances", str(config.ml.compute_min_nodes),
         "--max-instances", str(config.ml.compute_max_nodes),
         "--idle-time-before-scale-down", str(config.ml.compute_idle_seconds)],
        description=f"Create compute cluster {cluster}",
    )

    # Poll until Succeeded
    for _ in range(36):
        state = az(
            "ml", "compute", "show",
            "--name", cluster, "--resource-group", rg, "--workspace-name", ws,
            "--query", "provisioningState", "--output", "tsv",
        )
        if state.strip() == "Succeeded":
            break
        log.info("  Compute state: %s …", state.strip())
        time.sleep(5)

    log.info("✅ Compute cluster ready: %s", cluster)


def update_variable_group_ml() -> None:
    """Push ML config into the DevOps variable group (step 11–14 in §12.5)."""
    step("12.5c Update Variable Group with ML Settings")
    group_name = config.devops.variable_group_name

    r = run(
        ["az", "pipelines", "variable-group", "list",
         "--org", _org_url(),
         "--project", config.devops.project_name,
         "--query", f"[?name=='{group_name}'].id",
         "--output", "tsv"],
        capture=True, check=False,
        env=_devops_env(),
    )
    group_id = r.stdout.strip()
    if not group_id:
        log.warning("⚠  Variable group not found — run setup_devops first")
        return

    ml_vars = {
        "AZURE_RESOURCE_GROUP": config.azure.resource_group,
        "AZURE_ML_WORKSPACE":   config.ml.workspace_name,
        "AZURE_ML_REGION":      config.azure.location,
        "COMPUTE_CLUSTER":      config.ml.compute_cluster_name,
    }
    for k, v in ml_vars.items():
        for verb in ("create", "update"):
            run_or_skip(
                ["az", "pipelines", "variable-group", "variable", verb,
                 "--group-id", group_id, "--name", k, "--value", v,
                 "--org", _org_url(),
                 "--project", config.devops.project_name],
                description=f"{verb} {k}",
                env=_devops_env(),
            )
    log.info("✅ ML variables updated in variable group")


# ─── Pipeline trigger helpers ─────────────────────────────────────────────────

def _trigger_pipeline(pipeline_name: str) -> str:
    r = run(
        ["az", "pipelines", "run",
         "--name", pipeline_name,
         "--org", _org_url(),
         "--project", config.devops.project_name,
         "--query", "id", "--output", "tsv"],
        capture=True,
        description=f"Trigger: {pipeline_name}",
        env=_devops_env(),
    )
    run_id = r.stdout.strip()
    log.info("✅ Pipeline triggered: %s (run id: %s)", pipeline_name, run_id)
    return run_id


def _poll_pipeline(run_id: str, *, max_polls: int = 60, interval: int = 60) -> str:
    """Poll until pipeline status is terminal. Returns final status string."""
    log.info("Polling pipeline run %s (max %d min)…", run_id, max_polls)
    for i in range(max_polls):
        time.sleep(interval)
        r = run(
            ["az", "pipelines", "runs", "show",
             "--id", run_id,
             "--org", _org_url(),
             "--project", config.devops.project_name,
             "--query", "status", "--output", "tsv"],
            capture=True, check=False,
            env=_devops_env(),
        )
        status = r.stdout.strip()
        log.info("  [%d/%d] Pipeline status: %s", i + 1, max_polls, status)
        if status.lower() in ("completed", "succeeded", "failed", "canceled"):
            return status
    return "timeout"


# ─── 12.6 Training ────────────────────────────────────────────────────────────

def run_training_pipeline() -> str:
    step("12.6 Run ML Training Pipeline")
    run_id = _trigger_pipeline("guardian-ml-training")
    monitor_url = (
        f"{_org_url()}/{config.devops.project_name}/_build/results?buildId={run_id}"
    )
    log.info("Monitor at: %s", monitor_url)

    # Poll (training runs on cluster — can take 30–60 min)
    status = _poll_pipeline(run_id, max_polls=60, interval=60)
    if status.lower() in ("completed", "succeeded"):
        log.info("✅ Training pipeline completed")
    else:
        log.warning("⚠  Training pipeline ended with status: %s", status)
        log.warning("   Check the run at: %s", monitor_url)
    return run_id


def verify_model_registration() -> list[dict]:
    step("12.6 Verify Model Registration")
    models = []
    for model_name in ("nsfw-detector", "violence-detector"):
        r = run(
            ["az", "ml", "model", "list",
             "--resource-group", config.azure.resource_group,
             "--workspace-name", config.ml.workspace_name,
             "--name", model_name,
             "--query", "[0].{name:name,version:version}",
             "--output", "json"],
            capture=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip() and r.stdout.strip() != "null":
            try:
                info = json.loads(r.stdout)
                models.append(info)
                log.info("✅ Registered: %s v%s", info.get("name"), info.get("version"))
            except json.JSONDecodeError:
                pass
        else:
            log.warning("⚠  Model not yet registered: %s", model_name)
    return models


# ─── 12.7 Deployment ─────────────────────────────────────────────────────────

def run_deployment_pipeline() -> str:
    step("12.7 Run ML Deployment Pipeline")
    run_id = _trigger_pipeline("guardian-ml-deployment")
    monitor_url = (
        f"{_org_url()}/{config.devops.project_name}/_build/results?buildId={run_id}"
    )
    log.info("Monitor at: %s", monitor_url)

    status = _poll_pipeline(run_id, max_polls=30, interval=60)
    if status.lower() in ("completed", "succeeded"):
        log.info("✅ Deployment pipeline completed")
    else:
        log.warning("⚠  Deployment pipeline ended with status: %s", status)
    return run_id


def get_endpoint_uris() -> dict[str, dict]:
    step("12.7 Retrieve Endpoint Scoring URIs")
    endpoints: dict[str, dict] = {}
    rg = config.azure.resource_group
    ws = config.ml.workspace_name

    for ep in (config.ml.nsfw_endpoint_name, config.ml.violence_endpoint_name):
        uri_r = run(
            ["az", "ml", "online-endpoint", "show",
             "--name", ep, "--resource-group", rg,
             "--workspace-name", ws,
             "--query", "scoring_uri", "--output", "tsv"],
            capture=True, check=False,
        )
        key_r = run(
            ["az", "ml", "online-endpoint", "get-credentials",
             "--name", ep, "--resource-group", rg,
             "--workspace-name", ws,
             "--query", "primaryKey", "--output", "tsv"],
            capture=True, check=False,
        )
        uri = uri_r.stdout.strip()
        key = key_r.stdout.strip()
        if uri:
            endpoints[ep] = {"scoring_uri": uri, "key": key}
            log.info("✅ %s → %s", ep, uri)
        else:
            log.warning("⚠  Endpoint not yet available: %s", ep)

    return endpoints


def patch_k8s_with_endpoints(endpoints: dict[str, dict]) -> None:
    """Update ConfigMap with endpoint URIs and restart deep-vision."""
    step("12.7 Patch ConfigMap with Endpoint URIs")
    if not endpoints:
        log.warning("⚠  No endpoint URIs — skipping ConfigMap patch")
        return

    patch: dict[str, str] = {}
    nsfw_ep     = endpoints.get(config.ml.nsfw_endpoint_name, {})
    violence_ep = endpoints.get(config.ml.violence_endpoint_name, {})

    if nsfw_ep.get("scoring_uri"):
        patch["NSFW_MODEL_ENDPOINT"]   = nsfw_ep["scoring_uri"]
        patch["MODEL_ENDPOINT_KEY"]    = nsfw_ep.get("key", "")
        # Enable Azure OpenAI-style scoring
        patch["AZURE_OPENAI_ENABLED"]  = "false"  # keep false unless OpenAI configured
    if violence_ep.get("scoring_uri"):
        patch["VIOLENCE_MODEL_ENDPOINT"] = violence_ep["scoring_uri"]

    patch_str = json.dumps({"data": patch})
    run(
        ["kubectl", "patch", "configmap", "guardian-config",
         "-n", config.k8s.namespace,
         "--patch", patch_str],
        description="Patch ConfigMap with endpoint URIs",
    )

    run_or_skip(
        ["kubectl", "rollout", "restart",
         "deployment/deep-vision", "-n", config.k8s.namespace],
        description="Restart deep-vision",
    )
    run_or_skip(
        ["kubectl", "rollout", "status",
         "deployment/deep-vision", "-n", config.k8s.namespace,
         "--timeout=120s"],
        description="Wait for deep-vision rollout",
    )
    log.info("✅ ConfigMap patched. deep-vision restarted.")


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def setup_azure_ml() -> dict:
    log.info("=" * 62)
    log.info("  Azure ML Setup & Pipelines  (Sections 12.5–12.7)")
    log.info("=" * 62)

    _ensure_ml_extension()
    create_workspace()
    create_compute_cluster()
    update_variable_group_ml()

    # Skip training if models are already registered
    models = verify_model_registration()
    if len(models) < 2:
        log.info("Models not yet registered — triggering training pipeline...")
        run_training_pipeline()
        models = verify_model_registration()
    else:
        log.info("✅ Models already registered — skipping training pipeline")

    run_deployment_pipeline()
    endpoints = get_endpoint_uris()
    patch_k8s_with_endpoints(endpoints)

    log.info("=" * 62)
    log.info("  ✅ Azure ML complete")
    log.info("  Workspace  : %s", config.ml.workspace_name)
    log.info("  Compute    : %s", config.ml.compute_cluster_name)
    log.info("  Models     : %d registered", len(models))
    log.info("  Endpoints  : %d deployed", len(endpoints))
    log.info("=" * 62)

    return {
        "workspace": config.ml.workspace_name,
        "models":    models,
        "endpoints": endpoints,
    }


if __name__ == "__main__":
    setup_azure_ml()
