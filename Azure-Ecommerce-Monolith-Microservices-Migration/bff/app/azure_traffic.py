"""Real Azure Container Apps orchestration for the 'azure' migration mode.

This module runs INSIDE the bff Container App once it's deployed to Azure —
it does not read infra/.state.json (that file only ever exists on whichever
machine ran `make provision`, never inside the running container). Instead
every value it needs was injected directly as an env var by
infra/bicep/main.bicep (plain values for non-secrets, secretRef for the ACR
and MySQL passwords), so the container is fully self-describing.

The microservices' Container Apps (user-, product-, order-service) are
deliberately NOT part of the initial `make provision` deploy — this module
creates each one for real, for the first time, as the live migration reaches
its extraction step for that service. That's the whole "wow" of the demo:
watching real Azure resources appear as you migrate, not a pre-provisioned
stack where migration just flips a switch.

Uses azure-mgmt-appcontainers + azure-identity (DefaultAzureCredential, which
picks up the bff Container App's own system-assigned managed identity when
running in Azure). provision.py grants that identity Contributor scoped to
just this one resource group.
"""
import asyncio
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.mgmt.appcontainers.models import (
    Configuration,
    Container,
    ContainerApp,
    ContainerResources,
    EnvironmentVar,
    Ingress,
    RegistryCredentials,
    Scale,
    Secret,
    Template,
)

STEP_TO_SERVICE = {
    "extract_user": ("user-service", 5001),
    "extract_product": ("product-service", 5002),
    "extract_order_acl": ("order-service", 5003),
}

_client: ContainerAppsAPIClient | None = None


def is_configured() -> bool:
    """True once the bff is actually running inside the Azure deployment
    (main.bicep injects AZURE_RESOURCE_GROUP) rather than locally, where
    'azure' migration mode has nothing real to do yet."""
    return bool(os.environ.get("AZURE_RESOURCE_GROUP"))


def _get_client() -> ContainerAppsAPIClient:
    global _client
    if _client is None:
        _client = ContainerAppsAPIClient(DefaultAzureCredential(), os.environ["AZURE_SUBSCRIPTION_ID"])
    return _client


def _create_microservice_container_app(service_name: str, target_port: int) -> str:
    """Creates one microservice's Container App for the first time — it
    genuinely does not exist before this call. Blocks until the ARM
    operation completes (a real 20-60 second operation), so the migration
    engine's SSE-driven step status reflects real progress, not a canned
    delay. Returns the app's FQDN."""
    resource_group = os.environ["AZURE_RESOURCE_GROUP"]
    default_domain = os.environ["AZURE_CONTAINER_APPS_DEFAULT_DOMAIN"]
    client = _get_client()

    env_vars = [
        EnvironmentVar(name="RUN_MODE", value="azure"),
        EnvironmentVar(name="AZURE_MYSQL_HOST", value=os.environ["AZURE_MYSQL_HOST"]),
        EnvironmentVar(name="AZURE_MYSQL_PORT", value="3306"),
        EnvironmentVar(name="AZURE_MYSQL_ADMIN_USER", value=os.environ["AZURE_MYSQL_ADMIN_USER"]),
        EnvironmentVar(name="AZURE_MYSQL_ADMIN_PASSWORD", secret_ref="mysql-password"),
    ]
    if service_name == "order-service":
        user_service_fqdn = f"user-service.{default_domain}"
        env_vars.append(EnvironmentVar(name="USER_SERVICE_BASE_URL", value=f"https://{user_service_fqdn}"))

    container_app = ContainerApp(
        location=os.environ["AZURE_LOCATION"],
        managed_environment_id=os.environ["AZURE_CONTAINER_APPS_ENV_ID"],
        configuration=Configuration(
            secrets=[
                Secret(name="acr-password", value=os.environ["AZURE_ACR_PASSWORD"]),
                Secret(name="mysql-password", value=os.environ["AZURE_MYSQL_ADMIN_PASSWORD"]),
            ],
            ingress=Ingress(external=True, target_port=target_port, transport="auto"),
            registries=[
                RegistryCredentials(
                    server=os.environ["AZURE_ACR_LOGIN_SERVER"],
                    username=os.environ["AZURE_ACR_NAME"],
                    password_secret_ref="acr-password",
                )
            ],
        ),
        template=Template(
            containers=[
                Container(
                    name=service_name,
                    image=f"{os.environ['AZURE_ACR_LOGIN_SERVER']}/{service_name}:latest",
                    resources=ContainerResources(cpu=0.25, memory="0.5Gi"),
                    env=env_vars,
                )
            ],
            scale=Scale(min_replicas=0, max_replicas=3),
        ),
    )

    poller = client.container_apps.begin_create_or_update(resource_group, service_name, container_app)
    result = poller.result()
    return result.configuration.ingress.fqdn


def _scale_container_app(app_name: str, min_replicas: int, max_replicas: int) -> None:
    """Scales an existing Container App. Used for the decommission step: the
    monolith is retired to 0 replicas, not deleted — mirroring local mode's
    'restart monolith' undo path.

    revisionSuffix is explicitly reset to "" (let Azure auto-generate a new
    one) — caught for real: this app had a manually-set suffix from earlier
    debugging, and every update PATCH kept resubmitting that same stored
    suffix, which fails once a revision with it already exists
    (ContainerAppOperationError: 'revision with suffix ... already exists')."""
    client = _get_client()
    client.container_apps.begin_update(
        os.environ["AZURE_RESOURCE_GROUP"],
        app_name,
        {"properties": {"template": {
            "revisionSuffix": "",
            "scale": {"minReplicas": min_replicas, "maxReplicas": max_replicas},
        }}},
    ).result()


async def scale_monolith(min_replicas: int, max_replicas: int) -> None:
    """Public entry point for restart_monolith()'s undo path in
    migration_engine.py — scales the monolith Container App back up from 0
    replicas, the inverse of what the decommission step does."""
    await asyncio.to_thread(_scale_container_app, "monolith", min_replicas, max_replicas)


async def shift_traffic_for_step(step_id: str) -> tuple[bool, str | None]:
    """Returns (ok, new_base_url). new_base_url is set only when this step
    just brought a new microservice online, so the caller (migration_engine)
    can update its runtime URL registry — the BFF's proxy has nothing to
    route to until that happens."""
    if step_id in STEP_TO_SERVICE:
        service_name, target_port = STEP_TO_SERVICE[step_id]
        fqdn = await asyncio.to_thread(_create_microservice_container_app, service_name, target_port)
        return True, f"https://{fqdn}"

    if step_id == "decommission":
        # Azure rejects maxReplicas=0 outright (ContainerAppInvalidScaleSpec:
        # "MaxReplicas must be greater than 0") — caught for real running this
        # migration against Azure. min=0/max=1 still retires it to 0 running
        # replicas (nothing serves traffic until scale_monolith() undoes this),
        # just within a range Azure accepts.
        await asyncio.to_thread(_scale_container_app, "monolith", 0, 1)
        return True, None

    return True, None  # narrative-only step, nothing to do
