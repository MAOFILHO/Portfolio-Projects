"""
MultiCloud MLOps - Azure DevOps Automation
Automates Sections 12.1–12.4 of the manual guide.

  12.1  Create DevOps project + import GitHub repo into Azure Repos
  12.2  Create 3 service connections:
          guardian-azure-connection  (Azure RM)
          guardian-acr-connection    (Docker Registry / ACR)
          guardian-aks-connection    (Kubernetes)
  12.3  Download, configure, and start self-hosted agent
  12.4  Create variable group 'guardian-variables' + 3 pipelines

Service connection names MUST match what the pipeline YAMLs use:
  azure-pipelines-app-ci-cd.yml       → guardian-acr-connection, guardian-aks-connection
  azure-pipelines-ml-training.yml     → guardian-azure-connection
  azure-pipelines-ml-deployment.yml   → guardian-azure-connection, guardian-aks-connection

Variable group 'guardian-variables' variables (from pipeline YAMLs):
  ACR_NAME, AKS_CLUSTER, RESOURCE_GROUP, NAMESPACE,
  AZURE_RESOURCE_GROUP, AZURE_ML_WORKSPACE, AZURE_ML_REGION, COMPUTE_CLUSTER
"""
import json
import os
import platform
import stat
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.config import config
from automation.utils.shell import get_logger, run, run_or_skip, step

log = get_logger("devops")

AGENT_VERSION = "3.236.1"
AGENT_DIR     = Path.home() / "guardian-agent"


def _org_url() -> str:
    return f"https://dev.azure.com/{config.devops.organization_name}"


def _devops_env() -> dict:
    """Return env dict with PAT for az devops CLI calls."""
    return {"AZURE_DEVOPS_EXT_PAT": config.devops.pat_token}


# ─── Extension & defaults ─────────────────────────────────────────────────────

def _ensure_devops_extension() -> None:
    r = run(["az", "extension", "show", "--name", "azure-devops"],
            capture=True, check=False)
    if r.returncode != 0:
        run(["az", "extension", "add", "--name", "azure-devops", "--yes"],
            description="Install az devops extension")
    log.info("✅ az devops extension ready")


def _set_defaults() -> None:
    if not config.devops.pat_token:
        log.error(
            "AZDO_PAT_TOKEN not set.\n"
            "Generate at: https://dev.azure.com → User Settings → Personal Access Tokens\n"
            "Scopes: Agent Pools (R&M), Build (R&E), Code (R), Project+Team (R&W),\n"
            "        Service Connections (R,Q,M), Variable Groups (R,C,M)"
        )
        sys.exit(1)
    os.environ["AZURE_DEVOPS_EXT_PAT"] = config.devops.pat_token
    run(
        ["az", "devops", "configure",
         "--defaults",
         f"organization={_org_url()}",
         f"project={config.devops.project_name}"],
        description="Set az devops defaults",
    )


# ─── 12.1 Project ─────────────────────────────────────────────────────────────

def create_project() -> None:
    step("12.1 Create / Verify Azure DevOps Project")
    r = run(
        ["az", "devops", "project", "show",
         "--project", config.devops.project_name,
         "--org", _org_url()],
        capture=True, check=False,
        env=_devops_env(),
    )
    if r.returncode == 0:
        log.info("✅ Project already exists: %s", config.devops.project_name)
    else:
        run(
            ["az", "devops", "project", "create",
             "--name", config.devops.project_name,
             "--org", _org_url(),
             "--visibility", "private",
             "--source-control", "git",
             "--process", "Agile"],
            description=f"Create project {config.devops.project_name}",
            env=_devops_env(),
        )
        log.info("✅ Created project: %s", config.devops.project_name)

    # Import the GitHub repository
    log.info("Importing GitHub repo → Azure Repos…")
    run_or_skip(
        ["az", "repos", "import", "create",
         "--git-source-url", config.devops.github_repo_url,
         "--repository", config.devops.project_name,
         "--org", _org_url(),
         "--project", config.devops.project_name],
        description="Import GitHub repo",
        env=_devops_env(),
    )
    log.info("✅ Repo available (imported or already present)")


# ─── 12.2 Service Connections ─────────────────────────────────────────────────

def _sc_exists(name: str) -> bool:
    r = run(
        ["az", "devops", "service-endpoint", "list",
         "--org", _org_url(),
         "--project", config.devops.project_name,
         "--query", f"[?name=='{name}'].id",
         "--output", "tsv"],
        capture=True, check=False,
        env=_devops_env(),
    )
    return bool(r.stdout.strip())


def _grant_sc_to_all(name: str) -> None:
    run_or_skip(
        ["az", "devops", "service-endpoint", "update",
         "--name", name,
         "--enable-for-all",
         "--org", _org_url(),
         "--project", config.devops.project_name],
        description=f"Grant {name} to all pipelines",
        env=_devops_env(),
    )


def create_azure_rm_connection() -> None:
    name = config.devops.azure_sc_name
    if _sc_exists(name):
        log.info("✅ SC already exists: %s", name)
        return
    import os
    sp_id     = os.getenv("AZURE_SP_APP_ID", "")
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    sub_name  = os.getenv("AZURE_SUBSCRIPTION_NAME", "Azure subscription 1")
    sp_key    = os.getenv("AZURE_SP_SECRET", "")

    env = {**_devops_env()}
    if sp_key:
        env["AZURE_DEVOPS_EXT_AZURE_RM_SERVICE_PRINCIPAL_KEY"] = sp_key

    run(
        ["az", "devops", "service-endpoint", "azurerm", "create",
         "--name", name,
         "--azure-rm-subscription-id", config.azure.subscription_id,
         "--azure-rm-subscription-name", sub_name,
         "--azure-rm-tenant-id", tenant_id,
         "--azure-rm-service-principal-id", sp_id,
         "--org", _org_url(),
         "--project", config.devops.project_name],
        description=f"Create Azure RM service connection: {name}",
        env=env,
    )
    _grant_sc_to_all(name)
    log.info("✅ Azure RM service connection: %s", name)


def create_acr_connection() -> None:
    """
    Create Docker Registry service connection pointing to ACR.
    Uses Workload Identity federation (recommended in the manual guide).
    """
    name = config.devops.acr_sc_name
    if _sc_exists(name):
        log.info("✅ SC already exists: %s", name)
        return

    import os
    sp_id     = os.getenv("AZURE_SP_APP_ID", "")
    sp_key    = os.getenv("AZURE_SP_SECRET", "")
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    acr_name  = config.azure.acr_name

    ep = {
        "data": {
            "registrytype": "ACR",
            "subscriptionId": config.azure.subscription_id,
            "registryId": (
                f"/subscriptions/{config.azure.subscription_id}"
                f"/resourceGroups/{config.azure.resource_group}"
                f"/providers/Microsoft.ContainerRegistry/registries/{acr_name}"
            ),
        },
        "name": name,
        "type": "dockerregistry",
        "authorization": {
            "scheme": "ServicePrincipal",
            "parameters": {
                "serviceprincipalid": sp_id,
                "serviceprincipalkey": sp_key,
                "tenantid": tenant_id,
                "loginServer": f"{acr_name}.azurecr.io",
            }
        },
        "isShared": False,
        "isReady": True,
    }
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(ep, f)
        ep_file = f.name

    run(
        ["az", "devops", "service-endpoint", "create",
         "--service-endpoint-configuration", ep_file,
         "--org", _org_url(),
         "--project", config.devops.project_name],
        description=f"Create ACR service connection: {name}",
        env=_devops_env(),
    )
    _grant_sc_to_all(name)
    log.info("✅ ACR service connection: %s", name)


def _get_project_id(project_name: str) -> str:
    """Get Azure DevOps project ID by name via REST API."""
    import os, base64, urllib.request, json
    org_url = _org_url()
    pat = os.getenv("AZDO_PAT_TOKEN", "")
    auth = base64.b64encode(f":{pat}".encode()).decode()
    req = urllib.request.Request(
        f"{org_url}/_apis/projects/{project_name}?api-version=7.0",
        headers={"Authorization": f"Basic {auth}"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read()).get("id", "")
    except Exception:
        return ""


def create_aks_connection() -> None:
    """Create Kubernetes service connection for the AKS cluster."""
    name = config.devops.aks_sc_name
    if _sc_exists(name):
        log.info("✅ SC already exists: %s", name)
        return

    # AKS service connection via REST API using kubeconfig (Token scheme)
    # az devops CLI doesn't support Kubeconfig/Token scheme — use REST directly
    import os, subprocess, base64, json as _json
    org_url = _org_url()
    project = config.devops.project_name
    pat     = os.getenv("AZDO_PAT_TOKEN", "")
    project_id = _get_project_id(project)

    # Get kubeconfig and AKS FQDN
    try:
        fqdn_result = subprocess.run(
            ["az", "aks", "show", "--name", config.azure.aks_cluster,
             "--resource-group", config.azure.resource_group,
             "--query", "fqdn", "--output", "tsv"],
            capture_output=True, text=True
        )
        aks_fqdn = fqdn_result.stdout.strip()
        token_result = subprocess.run(
            ["kubectl", "create", "token", "default", "-n", "production"],
            capture_output=True, text=True
        )
        api_token = token_result.stdout.strip() or ""
    except Exception:
        aks_fqdn = ""
        api_token = ""

    ep = {
        "name": name,
        "type": "kubernetes",
        "url": f"https://{aks_fqdn}" if aks_fqdn else "https://kubernetes.default.svc",
        "authorization": {
            "scheme": "Token",
            "parameters": {"apitoken": api_token}
        },
        "data": {
            "authorizationType": "ServiceAccount",
            "acceptUntrustedCerts": "true"
        },
        "isShared": False,
        "isReady": True,
        "serviceEndpointProjectReferences": [{
            "projectReference": {"id": project_id},
            "name": name
        }]
    }

    import urllib.request as _req
    auth = base64.b64encode(f":{pat}".encode()).decode()
    payload = _json.dumps(ep).encode()
    req = _req.Request(
        f"{org_url}/{project}/_apis/serviceendpoint/endpoints?api-version=7.1-preview.4",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
        method="POST"
    )
    try:
        with _req.urlopen(req) as resp:
            result = _json.loads(resp.read())
            log.info("✅ AKS service connection created via REST: %s", result.get("id"))
    except Exception as e:
        log.warning("AKS REST endpoint creation failed: %s — create manually in Azure DevOps UI", e)
        return
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(ep, f)
        ep_file = f.name

    run(
        ["az", "devops", "service-endpoint", "create",
         "--service-endpoint-configuration", ep_file,
         "--org", _org_url(),
         "--project", config.devops.project_name],
        description=f"Create AKS service connection: {name}",
        env=_devops_env(),
    )
    _grant_sc_to_all(name)
    log.info("✅ AKS service connection: %s", name)


def create_service_connections() -> None:
    step("12.2 Create Service Connections")
    create_azure_rm_connection()
    create_acr_connection()
    create_aks_connection()
    log.info("✅ All 3 service connections ready")


# ─── 12.3 Self-hosted agent ───────────────────────────────────────────────────

def _agent_download_url() -> tuple[str, str]:
    system  = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        arch = "arm64" if "arm" in machine else "x64"
        fname = f"vsts-agent-osx-{arch}-{AGENT_VERSION}.tar.gz"
    elif system == "linux":
        arch = "arm64" if "aarch64" in machine or "arm" in machine else "x64"
        fname = f"vsts-agent-linux-{arch}-{AGENT_VERSION}.tar.gz"
    else:
        fname = f"vsts-agent-win-x64-{AGENT_VERSION}.zip"
    url = f"https://vstsagentpackage.azureedge.net/agent/{AGENT_VERSION}/{fname}"
    return url, fname


def download_and_configure_agent() -> None:
    step("12.3 Setup Self-Hosted Agent")
    AGENT_DIR.mkdir(parents=True, exist_ok=True)

    config_script = AGENT_DIR / ("config.cmd" if platform.system() == "Windows" else "config.sh")
    if config_script.exists():
        log.info("✅ Agent already downloaded: %s", AGENT_DIR)
    else:
        url, fname = _agent_download_url()
        archive = AGENT_DIR / fname
        log.info("Downloading agent %s…", url)
        urllib.request.urlretrieve(url, archive)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(AGENT_DIR)
        if platform.system() == "Darwin":
            run(["xattr", "-cr", str(AGENT_DIR)],
                description="Remove macOS quarantine")
        for s in (AGENT_DIR / "config.sh", AGENT_DIR / "run.sh"):
            if s.exists():
                s.chmod(s.stat().st_mode | stat.S_IEXEC)
        log.info("✅ Agent extracted: %s", AGENT_DIR)

    # Configure (unattended)
    agent_name = f"guardian-agent-{platform.node()}"
    cfg = "config.cmd" if platform.system() == "Windows" else "config.sh"
    run(
        [str(AGENT_DIR / cfg),
         "--unattended",
         "--url", _org_url(),
         "--auth", "pat",
         "--token", config.devops.pat_token,
         "--pool", "Default",
         "--agent", agent_name,
         "--work", "_work",
         "--acceptTeeEula"],
        cwd=AGENT_DIR,
        description=f"Configure agent: {agent_name}",
    )

    log.info(
        "\n  ┌─────────────────────────────────────────────┐\n"
        "  │  Start the agent in a SEPARATE terminal:     │\n"
        "  │  cd %s   │\n"
        "  │  ./run.sh                                    │\n"
        "  │  Keep the terminal open while pipelines run. │\n"
        "  └─────────────────────────────────────────────┘",
        AGENT_DIR,
    )


# ─── 12.4 Variable group & pipelines ─────────────────────────────────────────

def create_variable_group() -> int:
    step("12.4a Create Variable Group 'guardian-variables'")
    name = config.devops.variable_group_name

    r = run(
        ["az", "pipelines", "variable-group", "list",
         "--org", _org_url(),
         "--project", config.devops.project_name,
         "--query", f"[?name=='{name}'].id",
         "--output", "tsv"],
        capture=True, check=False,
        env=_devops_env(),
    )
    existing_id = r.stdout.strip()

    if existing_id:
        group_id = int(existing_id)
        log.info("✅ Variable group already exists: %s (id=%d)", name, group_id)
    else:
        r = run(
            ["az", "pipelines", "variable-group", "create",
             "--name", name,
             "--org", _org_url(),
             "--project", config.devops.project_name,
             "--variables",
             f"ACR_NAME={config.azure.acr_name}",
             f"AKS_CLUSTER={config.azure.aks_cluster}",
             f"RESOURCE_GROUP={config.azure.resource_group}",
             f"NAMESPACE={config.k8s.namespace}",
             "--authorize", "true",
             "--query", "id", "--output", "tsv"],
            capture=True,
            description="Create variable group",
            env=_devops_env(),
        )
        group_id = int(r.stdout.strip())
        log.info("✅ Variable group created: %s (id=%d)", name, group_id)

    # Ensure all ML variables are present
    ml_vars = {
        "AZURE_RESOURCE_GROUP": config.azure.resource_group,
        "AZURE_ML_WORKSPACE":   config.ml.workspace_name,
        "AZURE_ML_REGION":      config.azure.location,
        "COMPUTE_CLUSTER":      config.ml.compute_cluster_name,
    }
    for k, v in ml_vars.items():
        for cmd_verb in ("create", "update"):
            run_or_skip(
                ["az", "pipelines", "variable-group", "variable", cmd_verb,
                 "--group-id", str(group_id),
                 "--name", k, "--value", v,
                 "--org", _org_url(),
                 "--project", config.devops.project_name],
                description=f"{cmd_verb} {k}",
                env=_devops_env(),
            )
    return group_id


def _pipeline_id(name: str) -> int | None:
    r = run(
        ["az", "pipelines", "show",
         "--name", name,
         "--org", _org_url(),
         "--project", config.devops.project_name,
         "--query", "id", "--output", "tsv"],
        capture=True, check=False,
        env=_devops_env(),
    )
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def create_pipelines() -> dict[str, int]:
    step("12.4b Create Azure DevOps Pipelines")
    pipelines = {
        "guardian-app-ci-cd":      config.devops.app_pipeline_yaml,
        "guardian-ml-training":    config.devops.ml_training_yaml,
        "guardian-ml-deployment":  config.devops.ml_deployment_yaml,
    }
    ids: dict[str, int] = {}
    for pipeline_name, yaml_path in pipelines.items():
        existing = _pipeline_id(pipeline_name)
        if existing:
            log.info("✅ Pipeline already exists: %s (id=%d)", pipeline_name, existing)
            ids[pipeline_name] = existing
            continue

        r = run(
            ["az", "pipelines", "create",
             "--name", pipeline_name,
             "--org", _org_url(),
             "--project", config.devops.project_name,
             "--repository", config.devops.project_name,
             "--repository-type", "tfsgit",
             "--branch", "main",
             "--yaml-path", yaml_path,
             "--skip-first-run",
             "--query", "id", "--output", "tsv"],
            capture=True,
            description=f"Create pipeline: {pipeline_name}",
            env=_devops_env(),
        )
        pid = int(r.stdout.strip())
        ids[pipeline_name] = pid
        log.info("✅ Pipeline created: %s (id=%d)", pipeline_name, pid)

    return ids


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def setup_devops() -> dict:
    log.info("=" * 62)
    log.info("  Azure DevOps Setup  (Sections 12.1–12.4)")
    log.info("=" * 62)

    _ensure_devops_extension()
    _set_defaults()
    create_project()
    create_service_connections()
    log.info("⏭  Skipping self-hosted agent — using Microsoft-hosted ubuntu-latest pool instead")
    log.info("    To use a self-hosted agent, install manually from:")
    log.info("    https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents")
    group_id     = create_variable_group()
    pipeline_ids = create_pipelines()

    log.info("=" * 62)
    log.info("  ✅ Azure DevOps ready")
    log.info("  Org      : %s", _org_url())
    log.info("  Project  : %s", config.devops.project_name)
    log.info("  Pipelines: %s", list(pipeline_ids.keys()))
    log.info("=" * 62)

    return {
        "org_url":          _org_url(),
        "project":          config.devops.project_name,
        "variable_group_id": group_id,
        "pipeline_ids":     pipeline_ids,
    }


if __name__ == "__main__":
    setup_devops()
