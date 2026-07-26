from __future__ import annotations

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success
from surveil_deploy.runner import run_json
from surveil_deploy.soft_delete import (
    purge_soft_deleted_vision_accounts,
    recover_soft_deleted_log_analytics_workspaces,
)
from surveil_deploy.state import DeploymentState

STEP_NAME = "s03_deploy_infra"
STEP_TITLE = "Deploying infrastructure (Bicep -> Azure)"

# HAZARD: functionapp.bicep's siteConfig.appSettings is a full replace of
# the Function App's app settings on every deploy (an ARM/Azure Functions
# platform behavior, not something Bicep can express as a merge). It
# deliberately does NOT include WEBSITE_RUN_FROM_PACKAGE /
# WEBSITE_RUN_FROM_PACKAGE_BLOB_MI_RESOURCE_ID -- s07_deploy_function.py sets
# those afterward via `az functionapp config appsettings set`. Re-running
# THIS step without immediately re-running s07 afterward silently wipes the
# Function's code package reference: the host reports "Running" and the app
# setting update reports success, but nothing gets analyzed ever again until
# s07 runs. Confirmed the hard way in production. Whenever this step runs
# outside the full `surveil-deploy deploy` pipeline (which always runs s07
# right after), always re-run s07_deploy_function immediately after it.
#
# The same hazard applies to the Nest ingestor when NEST_INGESTOR_ENABLED:
# nest-ingestor.bicep's container `image` field is a placeholder (the real
# image is set afterward by s06_deploy_ingestor.py via `az containerapp
# update --image`, for the same chicken-and-egg reason as the Function).
# Re-running this step resets the ingestor Container App back to that
# placeholder image too -- always re-run s06_deploy_ingestor immediately
# after this step as well, whenever the ingestor is enabled.

DEPLOYMENT_NAME = "surveil-main"


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(3, 12, STEP_TITLE)

    template_file = config.source_dir / "infra" / "main.bicep"
    parameters_file = config.source_dir / "infra" / "main.parameters.json"

    log_info(f"Resource group: {config.resource_group_name()}  Region: {config.azure_location}")
    log_info("This provisions Storage, Vision, Container Apps, Function App, ACS, Static Web App, "
              "Container Registry, and observability resources. Typical time: 3-8 minutes.")

    # Resource names here are deterministic per (subscription, env name,
    # location) -- a redeploy after a prior teardown reuses the exact same
    # Vision account / Log Analytics workspace names, which fail against
    # Azure's soft-delete retention unless purged/recovered first.
    purge_soft_deleted_vision_accounts(config)
    recover_soft_deleted_log_analytics_workspaces(config)

    inline_params = [
        f"environmentName={config.azure_env_name}",
        f"location={config.azure_location}",
        f"resourceGroupName={config.resource_group_name()}",
        f"visionSkuName={config.vision_sku}",
        f"storageSkuName={config.storage_sku_name}",
        f"alertWatchTags={config.alert_watch_tags}",
        f"alertMinConfidence={config.alert_min_confidence}",
        f"alertMinCount={config.alert_min_count}",
        f"analyzerBackend={config.analyzer_backend}",
        f"alertCrowdThreshold={config.alert_crowd_threshold}",
        f"alertRestrictedZone={config.alert_restricted_zone}",
        f"alertSeverityMap={config.alert_severity_map}",
        f"visionLocation={config.vision_location}",
        f"acsSenderEmail={config.acs_sender_email}",
        f"alertEmailTo={config.alert_email_to}",
        f"alertSmsTo={config.alert_sms_to}",
        f"acsSmsFrom={config.acs_sms_from}",
    ]

    if config.nest_ingestor_enabled:
        log_info("NEST_INGESTOR_ENABLED=true — provisioning the always-on Nest ingestor Container App too")
        gcp_key_json = config.gcp_service_account_key_path.read_text()
        inline_params += [
            "nestIngestorEnabled=true",
            f"googleClientId={config.google_client_id}",
            f"googleClientSecret={config.google_client_secret}",
            f"googleRefreshToken={config.google_refresh_token}",
            f"googleDeviceAccessProjectId={config.google_device_access_project_id}",
            f"googleDevices={config.google_devices}",
            f"gcpPubsubProjectId={config.gcp_pubsub_project_id}",
            f"gcpPubsubSubscriptionId={config.gcp_pubsub_subscription_id}",
            f"gcpServiceAccountKeyJson={gcp_key_json}",
        ]

    payload = run_json(
        [
            "az", "deployment", "sub", "create",
            "--name", DEPLOYMENT_NAME,
            "--location", config.azure_location,
            "--template-file", str(template_file),
            "--parameters", str(parameters_file),
            "--parameters", *inline_params,
            "-o", "json",
        ],
    )

    # ARM mangles the case of every Bicep output name when returning
    # deployment results (e.g. STORAGE_ACCOUNT_NAME comes back as
    # storagE_ACCOUNT_NAME -- it lowercases the leading all-caps run except
    # its last letter). Every output declared in main.bicep is fully
    # uppercase, so .upper() trivially restores the original name regardless
    # of the exact mangling rule.
    outputs = {
        k.upper(): v["value"]
        for k, v in payload.get("properties", {}).get("outputs", {}).items()
    }

    log_success(f"Infrastructure deployed to resource group {outputs.get('AZURE_RESOURCE_GROUP')}")
    for key in ("STORAGE_ACCOUNT_NAME", "VISION_ACCOUNT_NAME", "CONTAINER_APP_NAME", "FUNCTION_APP_NAME", "STATIC_WEB_APP_NAME"):
        if key in outputs:
            log_info(f"{key} = {outputs[key]}")

    return outputs
