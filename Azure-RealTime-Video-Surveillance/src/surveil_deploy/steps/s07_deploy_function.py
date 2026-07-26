from __future__ import annotations

import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import CommandError, run as run_command, run_json
from surveil_deploy.state import DeploymentState

STEP_NAME = "s07_deploy_function"
STEP_TITLE = "Deploying the Azure Function analysis worker"

# Files/dirs zipped into the deployment package alongside .python_packages
# and the vendored surveil_core (added separately, see below).
_PACKAGE_ENTRIES = ["function_app.py", "host.json", "requirements.txt"]

_PYTHON_TAGS = ["--python-version", "3.12", "--implementation", "cp", "--abi", "cp312", "--platform", "manylinux2014_x86_64"]

DEPLOYMENT_CONTAINER = "function-deployments"
STORAGE_DATA_ROLE = "Storage Blob Data Contributor"
RBAC_PROPAGATION_RETRIES = 12
RBAC_PROPAGATION_DELAY_SECONDS = 5

BLOB_EVENT_SUBSCRIPTION_NAME = "analyze-frame-blob-created"
FUNCTION_READY_RETRIES = 24
FUNCTION_READY_DELAY_SECONDS = 10

# This Linux Consumption ("run from package") Function App rejects every
# push-based deploy mechanism tried here:
#   - `func azure functionapp publish` (any --build mode) authenticates to
#     blob storage directly from this machine using AzureWebJobsStorage's
#     connection string -- which doesn't exist, since that setting is
#     identity-based by design (see functionapp.bicep).
#   - `az functionapp deployment source config-zip` (legacy Kudu zip-deploy)
#     is explicitly rejected: "does not support this deployment path".
#   - `az functionapp deploy` (OneDeploy) errors "This API isn't available in
#     this environment yet!" on this plan.
# The mechanism Azure's own error message points to (aka.ms/deployfromurl)
# does work: upload the package to blob storage and point
# WEBSITE_RUN_FROM_PACKAGE at it. This storage account has
# allowSharedKeyAccess=false (storage.bicep) -- account keys are rejected
# outright -- so every storage call here uses `--auth-mode login` (our own
# `az login` identity, which provisioned this deployment and has the
# necessary data-plane RBAC). The Function App itself reads the package back
# via WEBSITE_RUN_FROM_PACKAGE_BLOB_MI_RESOURCE_ID (the shared user-assigned
# identity, already granted Storage Blob Data Contributor on this account) --
# not a SAS token. An earlier version of this step used a 1-hour user
# delegation SAS instead; that meant the Function silently stopped being able
# to load its own code (no errors, no telemetry) exactly one hour after every
# deploy, which is a much worse failure mode than it sounds since nothing
# about it looks like a bug until you try to use the deployment again later.


def _current_principal_object_id() -> str:
    """Object ID of whoever `az login` is currently authenticated as.

    `az ad signed-in-user show` only works for an interactive/user principal
    -- it errors outright under a service-principal login (e.g. GitHub
    Actions' OIDC-based `azure/login`, which never went through this path
    until the pipeline's first real CI/CD run). Branch on the principal
    type reported by `az account show` instead of assuming a human user.
    """
    account = run_json(["az", "account", "show", "-o", "json"])
    user = account["user"]
    if user["type"] == "servicePrincipal":
        return run_json(["az", "ad", "sp", "show", "--id", user["name"], "-o", "json"])["id"]
    return run_command(["az", "ad", "signed-in-user", "show", "--query", "id", "-o", "tsv"], stream=False).stdout.strip()


def _ensure_own_blob_data_access(storage_account: str, resource_group: str) -> None:
    """Self-grants Storage Blob Data Contributor on this storage account.

    Being subscription/RG Owner (which deploying this Bicep template
    requires) does NOT include storage *data-plane* access -- Azure keeps
    blob data operations behind a separate RBAC check even for Owners.
    Idempotent: safely re-run if the assignment already exists.
    """
    user_oid = _current_principal_object_id()
    storage_id = run_command(
        ["az", "storage", "account", "show", "--name", storage_account,
         "--resource-group", resource_group, "--query", "id", "-o", "tsv"],
        stream=False,
    ).stdout.strip()

    log_info(f"Ensuring this deploy identity has '{STORAGE_DATA_ROLE}' on {storage_account} (needed to upload the function package)")
    try:
        run_command(
            ["az", "role", "assignment", "create", "--assignee", user_oid,
             "--role", STORAGE_DATA_ROLE, "--scope", storage_id],
            stream=False,
        )
    except CommandError as exc:
        if "already exists" not in exc.output.lower():
            raise


def _retry_rbac_propagation(description: str, action):  # noqa: ANN001, ANN202
    """Retries an action while Azure RBAC assignment propagation catches up.

    New role assignments aren't instant -- can take up to ~30-60s to take
    effect against data-plane APIs.
    """
    for attempt in range(1, RBAC_PROPAGATION_RETRIES + 1):
        try:
            return action()
        except CommandError:
            if attempt == RBAC_PROPAGATION_RETRIES:
                raise
            log_info(f"{description} not yet authorized (RBAC still propagating) -- retrying ({attempt}/{RBAC_PROPAGATION_RETRIES})")
            time.sleep(RBAC_PROPAGATION_DELAY_SECONDS)


def _ensure_blob_created_event_subscription(storage_account: str, resource_group: str, function_app_name: str) -> None:
    """Creates the Event Grid subscription that fires AnalyzeFrame on new blobs.

    Confirmed the hard way that the `azurefunction` destination type is NOT
    for this: it only accepts genuine Event Grid *trigger* functions
    (`@app.event_grid_trigger`), and rejects a blob-trigger function
    (`Unsupported Azure Function Trigger ... Azure Event Grid supports
    EventGrid Trigger type only`) even with `source="EventGrid"` set on the
    blob trigger. For an Event-Grid-sourced *blob* trigger, Microsoft's actual
    mechanism is a `webhook` destination pointed at the Function's built-in
    blob-extension endpoint, authenticated with the `blobs_extension` system
    key (`az functionapp keys list`) -- both only obtainable once the
    function code is deployed and running, hence this lives in s07 rather
    than functionapp.bicep. Retried in case the function is still
    cold-starting right after the restart above. Idempotent: an
    `event-subscription create` on an existing name updates it in place.
    """
    log_info("Ensuring the Event Grid subscription for the blob-triggered Function exists")
    storage_id = run_command(
        ["az", "storage", "account", "show", "--name", storage_account,
         "--resource-group", resource_group, "--query", "id", "-o", "tsv"],
        stream=False,
    ).stdout.strip()
    system_key = run_json(
        ["az", "functionapp", "keys", "list", "--name", function_app_name,
         "--resource-group", resource_group, "-o", "json"],
    )["systemKeys"]["blobs_extension"]
    webhook_endpoint = (
        f"https://{function_app_name}.azurewebsites.net/runtime/webhooks/blobs"
        f"?functionName=Host.Functions.AnalyzeFrame&code={system_key}"
    )

    for attempt in range(1, FUNCTION_READY_RETRIES + 1):
        try:
            run_command(
                ["az", "eventgrid", "event-subscription", "create",
                 "--name", BLOB_EVENT_SUBSCRIPTION_NAME,
                 "--source-resource-id", storage_id,
                 "--endpoint-type", "webhook",
                 "--endpoint", webhook_endpoint,
                 "--included-event-types", "Microsoft.Storage.BlobCreated",
                 "--subject-begins-with", "/blobServices/default/containers/frames/blobs/",
                 "--event-delivery-schema", "eventgridschema"],
                stream=False,
            )
            return
        except CommandError:
            if attempt == FUNCTION_READY_RETRIES:
                raise
            log_info(
                f"Blob extension webhook not yet responding (Function still cold-starting) "
                f"-- retrying ({attempt}/{FUNCTION_READY_RETRIES})"
            )
            time.sleep(FUNCTION_READY_DELAY_SECONDS)


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(7, 12, STEP_TITLE)

    outputs = state.resource_outputs
    function_app_name = outputs["FUNCTION_APP_NAME"]
    resource_group = outputs["AZURE_RESOURCE_GROUP"]

    function_dir = config.source_dir / "function"
    shared_src = config.source_dir / "shared" / "surveil_core"
    vendored_dest = function_dir / "surveil_core"
    packages_dir = function_dir / ".python_packages" / "lib" / "site-packages"
    zip_path = function_dir / "_deploy_package.zip"

    log_info("Vendoring shared/surveil_core into function/ (see shared/README.md for why)")
    if vendored_dest.exists():
        shutil.rmtree(vendored_dest)
    shutil.copytree(shared_src, vendored_dest)

    try:
        log_info("Installing function/requirements.txt for linux/x86_64 Python 3.12 (target runtime, not this machine's platform)")
        if packages_dir.exists():
            shutil.rmtree(packages_dir)
        packages_dir.mkdir(parents=True)
        run_command(
            [
                "pip", "install", "--only-binary=:all:", *_PYTHON_TAGS,
                "--target", str(packages_dir),
                "-r", "requirements.txt",
            ],
            cwd=function_dir,
        )

        log_info(f"Building deployment package for {function_app_name}")
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in _PACKAGE_ENTRIES:
                archive.write(function_dir / entry, arcname=entry)
            for src_root in (vendored_dest, function_dir / ".python_packages"):
                for path in src_root.rglob("*"):
                    if path.is_file() and "__pycache__" not in path.parts:
                        archive.write(path, arcname=str(path.relative_to(function_dir)))

        storage_account = outputs["STORAGE_ACCOUNT_NAME"]
        blob_name = f"{function_app_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.zip"

        _ensure_own_blob_data_access(storage_account, resource_group)

        log_info(f"Uploading deployment package to blob storage (container: {DEPLOYMENT_CONTAINER}, Azure AD auth)")
        _retry_rbac_propagation(
            "Container create",
            lambda: run_command(
                ["az", "storage", "container", "create", "--name", DEPLOYMENT_CONTAINER,
                 "--account-name", storage_account, "--auth-mode", "login"],
                stream=False,
            ),
        )
        _retry_rbac_propagation(
            "Blob upload",
            lambda: run_command(
                ["az", "storage", "blob", "upload",
                 "--account-name", storage_account, "--auth-mode", "login",
                 "--container-name", DEPLOYMENT_CONTAINER, "--name", blob_name,
                 "--file", str(zip_path), "--overwrite"],
                stream=False,
            ),
        )

        package_url = f"https://{storage_account}.blob.core.windows.net/{DEPLOYMENT_CONTAINER}/{blob_name}"
        managed_identity_id = outputs["MANAGED_IDENTITY_ID"]

        log_info(f"Pointing {function_app_name} at the new package via managed identity (WEBSITE_RUN_FROM_PACKAGE) and restarting")
        run_command(
            ["az", "functionapp", "config", "appsettings", "set",
             "--name", function_app_name, "--resource-group", resource_group,
             "--settings",
             f"WEBSITE_RUN_FROM_PACKAGE={package_url}",
             f"WEBSITE_RUN_FROM_PACKAGE_BLOB_MI_RESOURCE_ID={managed_identity_id}"],
            stream=False,
        )
        run_command(["az", "functionapp", "restart", "--name", function_app_name, "--resource-group", resource_group])
        _ensure_blob_created_event_subscription(storage_account, resource_group, function_app_name)
    finally:
        log_info("Cleaning up vendored copy, installed packages, and zip (source of truth stays in shared/surveil_core)")
        shutil.rmtree(vendored_dest, ignore_errors=True)
        shutil.rmtree(function_dir / ".python_packages", ignore_errors=True)
        Path(zip_path).unlink(missing_ok=True)

    log_success(f"Function app {function_app_name} published in resource group {resource_group}")
    return {}
