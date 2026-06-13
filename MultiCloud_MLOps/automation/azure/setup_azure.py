"""
MultiCloud MLOps - Azure Infrastructure Setup
Automates Sections 8.1–8.5 of the manual guide.

  8.1  Login + set subscription + register providers
  8.2  Create Resource Group
  8.3  Create ACR, enable admin, retrieve credentials
       → calls scripts/update-acr-in-manifests.sh to patch k8s YAMLs
  8.4  Create AKS cluster (idempotent, ~10–15 min first time)
  8.5  Install NGINX Ingress Controller via Helm

Replaces all Azure Portal GUI steps with Azure CLI.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from automation.config import config
from automation.utils.shell import (
    az, az_exists, az_json, get_logger, run, run_or_skip, step,
)

log = get_logger("azure")

_REQUIRED_PROVIDERS = [
    "Microsoft.ContainerService",
    "Microsoft.Compute",
    "Microsoft.Network",
    "Microsoft.ContainerRegistry",
    "Microsoft.ManagedIdentity",
    "Microsoft.MachineLearningServices",
    "Microsoft.Storage",
    "Microsoft.KeyVault",
    "Microsoft.Insights",
    "Microsoft.OperationalInsights",
]


# ─── 8.1 Login & Subscription ─────────────────────────────────────────────────

def login_and_set_subscription() -> str:
    step("8.1 Login to Azure & Set Active Subscription")

    result = run(["az", "account", "show"], capture=True, check=False)
    if result.returncode != 0:
        log.info("Not logged in — launching 'az login'…")
        run(["az", "login"])

    subs = az_json("account", "list")
    if not subs:
        log.error("No Azure subscriptions found.")
        sys.exit(1)

    sub_id = config.azure.subscription_id or subs[0]["id"]
    config.azure.subscription_id = sub_id
    run(["az", "account", "set", "--subscription", sub_id])
    log.info("✅ Active subscription: %s", sub_id)

    # Register resource providers (fixes MissingSubscriptionRegistration)
    log.info("Registering resource providers (async, first-time only)…")
    for provider in _REQUIRED_PROVIDERS:
        run_or_skip(
            ["az", "provider", "register", "--namespace", provider],
            description=f"Register {provider}",
        )
    return sub_id


# ─── 8.2 Resource Group ───────────────────────────────────────────────────────

def create_resource_group() -> None:
    step("8.2 Create Azure Resource Group")
    rg = config.azure.resource_group
    if az_exists(["az", "group", "show", "--name", rg]):
        log.info("✅ Resource group already exists: %s", rg)
        return
    run(
        ["az", "group", "create", "--name", rg, "--location", config.azure.location],
        description=f"Create RG {rg}",
    )
    log.info("✅ Created resource group: %s", rg)


# ─── 8.3 ACR ──────────────────────────────────────────────────────────────────

def _gen_acr_name() -> str:
    return f"guardianacr{str(int(time.time()))[-5:]}"


def create_acr() -> dict:
    step("8.3 Create Azure Container Registry (ACR)")
    rg = config.azure.resource_group

    if not config.azure.acr_name:
        config.azure.acr_name = _gen_acr_name()
    acr = config.azure.acr_name

    if az_exists(["az", "acr", "show", "--name", acr, "--resource-group", rg]):
        log.info("✅ ACR already exists: %s", acr)
    else:
        run(
            ["az", "acr", "create",
             "--resource-group", rg,
             "--name", acr,
             "--sku", "Standard",
             "--location", config.azure.location],
            description=f"Create ACR {acr}",
        )
        log.info("✅ ACR created: %s", acr)

    # Enable admin
    run(["az", "acr", "update", "--name", acr, "--admin-enabled", "true"],
        description="Enable ACR admin")

    # Retrieve credentials
    login_server = az("acr", "show", "--name", acr, "--query", "loginServer", "--output", "tsv")
    username     = az("acr", "credential", "show", "--name", acr, "--query", "username", "--output", "tsv")
    password     = az("acr", "credential", "show", "--name", acr, "--query", "passwords[0].value", "--output", "tsv")

    config.azure.acr_login_server = login_server
    config.azure.acr_username     = username
    config.azure.acr_password     = password
    log.info("✅ ACR login server: %s", login_server)

    # Persist ACR name to .env so subsequent stages can find it
    from pathlib import Path
    env_path = config.project_root / ".env"
    if env_path.exists():
        env_text = env_path.read_text()
        if "AZURE_ACR_NAME=" in env_text:
            import re
            env_text = re.sub(r"AZURE_ACR_NAME=.*", f"AZURE_ACR_NAME={acr}", env_text)
        else:
            env_text += f"\nAZURE_ACR_NAME={acr}\n"
        env_path.write_text(env_text)
        log.info("✅ Persisted AZURE_ACR_NAME=%s to .env", acr)

    # Docker login
    run(["az", "acr", "login", "--name", acr], description="Docker login to ACR")

    # Update k8s manifests with actual ACR name (uses the repo's own script)
    _patch_k8s_manifests(acr)

    return {"loginServer": login_server, "username": username, "password": password}


def _patch_k8s_manifests(acr_name: str) -> None:
    """
    Replace the hardcoded ACR server in all k8s/*.yaml files with the
    current ACR login server.  Uses sed so it works on existing deployments.
    """
    k8s_dir = config.project_root / "k8s"
    acr_server = f"{acr_name}.azurecr.io"

    import platform
    if platform.system() == "Darwin":
        sed_inplace = "sed -i ''"
    else:
        sed_inplace = "sed -i"

    # Replace any existing *.azurecr.io reference
    run(
        f"find {k8s_dir} -name '*.yaml' -exec "
        f"{sed_inplace} 's|[a-z0-9]*.azurecr.io|{acr_server}|g' {{}} +",
        description="Patch k8s manifests: replace ACR server",
    )
    # Also replace ACR_PLACEHOLDER if present (repo uses this in the update script)
    run(
        f"find {k8s_dir} -name '*.yaml' -exec "
        f"{sed_inplace} 's|ACR_PLACEHOLDER|{acr_name}|g' {{}} +",
        description="Patch k8s manifests: replace ACR_PLACEHOLDER",
    )
    log.info("✅ k8s manifests patched with ACR: %s", acr_server)


# ─── 8.4 AKS ──────────────────────────────────────────────────────────────────

def create_aks_cluster() -> None:
    step("8.4 Create AKS Cluster (10–15 min first run)")
    rg      = config.azure.resource_group
    cluster = config.azure.aks_cluster
    acr     = config.azure.acr_name

    if az_exists(["az", "aks", "show", "--resource-group", rg, "--name", cluster]):
        log.info("✅ AKS cluster already exists: %s", cluster)
        # Verify ACR attachment
        if run(
            ["az", "aks", "check-acr", "--name", cluster,
             "--resource-group", rg,
             "--acr", f"{acr}.azurecr.io"],
            capture=True, check=False,
        ).returncode != 0:
            run(
                ["az", "aks", "update", "--name", cluster,
                 "--resource-group", rg, "--attach-acr", acr],
                description="Attach ACR to existing AKS",
            )
    else:
        log.info("Creating AKS cluster — this takes 10–15 minutes…")
        run(
            ["az", "aks", "create",
             "--resource-group", rg,
             "--name", cluster,
             "--node-count", "4",
             "--node-vm-size", "Standard_D2s_v3",
             "--enable-managed-identity",
             "--attach-acr", acr,
             "--generate-ssh-keys",
             "--location", config.azure.location,
             "--network-plugin", "azure"],
            description=f"Create AKS {cluster}",
        )
        log.info("✅ AKS cluster created: %s", cluster)

    # Fetch kubeconfig
    run(
        ["az", "aks", "get-credentials",
         "--resource-group", rg, "--name", cluster,
         "--overwrite-existing"],
        description="Fetch AKS kubeconfig",
    )
    run(["kubectl", "get", "nodes"], description="Verify kubectl")
    log.info("✅ kubectl connected to: %s", cluster)


# ─── 8.5 NGINX Ingress ────────────────────────────────────────────────────────

def install_nginx_ingress() -> str:
    step("8.5 Install NGINX Ingress Controller")

    run(["helm", "repo", "add", "ingress-nginx",
         "https://kubernetes.github.io/ingress-nginx"],
        description="Add ingress-nginx Helm repo")
    run(["helm", "repo", "update"], description="Helm repo update")

    existing = run(
        ["helm", "status", "ingress-nginx", "--namespace", "ingress-nginx"],
        capture=True, check=False,
    )
    if existing.returncode == 0:
        log.info("✅ ingress-nginx already installed")
    else:
        run(
            ["helm", "install", "ingress-nginx", "ingress-nginx/ingress-nginx",
             "--namespace", "ingress-nginx",
             "--create-namespace",
             "--set", "controller.service.type=LoadBalancer",
             "--set", "controller.service.externalTrafficPolicy=Local"],
            description="Install NGINX Ingress via Helm",
        )
        log.info("✅ NGINX Ingress installed")

    # Wait up to 3 min for external IP
    external_ip = ""
    log.info("Waiting for LoadBalancer external IP (up to 3 minutes)…")
    for _ in range(36):
        r = run(
            ["kubectl", "get", "svc", "-n", "ingress-nginx",
             "ingress-nginx-controller",
             "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"],
            capture=True, check=False,
        )
        external_ip = r.stdout.strip()
        if external_ip:
            break
        time.sleep(5)

    config.azure.external_ip = external_ip
    if external_ip:
        log.info("✅ External IP: %s", external_ip)
    else:
        log.warning("⚠  External IP not yet assigned — check later: "
                    "kubectl get svc -n ingress-nginx")
    return external_ip


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def setup_azure() -> dict:
    log.info("=" * 62)
    log.info("  Azure Infrastructure Setup  (Sections 8.1–8.5)")
    log.info("=" * 62)

    sub_id     = login_and_set_subscription()
    create_resource_group()
    acr_creds  = create_acr()
    create_aks_cluster()
    external_ip = install_nginx_ingress()

    log.info("=" * 62)
    log.info("  ✅ Azure infrastructure complete")
    log.info("  Subscription   : %s", sub_id)
    log.info("  Resource Group : %s", config.azure.resource_group)
    log.info("  ACR            : %s", acr_creds["loginServer"])
    log.info("  AKS            : %s", config.azure.aks_cluster)
    log.info("  External IP    : %s", external_ip or "(pending)")
    log.info("=" * 62)

    return {
        "subscription_id": sub_id,
        "resource_group":  config.azure.resource_group,
        "acr_login_server": acr_creds["loginServer"],
        "aks_cluster":     config.azure.aks_cluster,
        "external_ip":     external_ip,
    }


if __name__ == "__main__":
    setup_azure()
