"""What actually happens for each resource key -- the glue between resources.py's pure ordering,
config.py's fixed names, and az_cli.py's `az` calls.

**No run-local cache of one step's output for a later step to read.** Every value a step needs from
an earlier resource (a connection string, a principal id, the environment's default domain) is
re-fetched live from Azure at the point of use, every time -- including on a resumed run, where the
resource that produced it may have been deployed in a *previous* process that no longer has anything
in memory. This is the same resume discipline `state.py` applies to *whether* a resource is deployed,
applied here to the *values* those resources hand to each other: an in-memory cache populated only on
the happy path would silently break the exact "partial failure, then resume" scenario the prototype
validated (`infra/PROTOTYPE-deploy-teardown-ordering.html` scenario 3), since a resumed run's `steps`
list skips whatever already deployed and never re-executes the code that would have cached its output.
"""
from __future__ import annotations

from . import az_cli, config


def deploy_one(resource_group: str, key: str, image: dict, dockerhub: dict) -> None:
    names = config.NAMES
    location = config.LOCATION

    if key == "app_insights":
        az_cli.deploy_bicep(resource_group, "app-insights", "azbank-app-insights", {
            "name": names["app_insights"],
            "location": location,
            "logAnalyticsWorkspaceName": config.LOG_ANALYTICS_WORKSPACE,
        })

    elif key == "container_apps_env":
        az_cli.deploy_bicep(resource_group, "container-apps-env", "azbank-container-apps-env", {
            "name": names["container_apps_env"],
            "location": location,
            "logAnalyticsWorkspaceName": config.LOG_ANALYTICS_WORKSPACE,
        })

    elif key == "call_records_account":
        az_cli.create_call_records_account_bootstrap(resource_group, names["call_records_account"], location)

    elif key == "mock_core_banking":
        az_cli.deploy_bicep(resource_group, "mock-core-banking", "azbank-mock-core-banking", {
            "environmentName": names["container_apps_env"],
            "image": image["core_banking"],
            "name": names["mock_core_banking"],
        })

    elif key == "acs":
        default_domain = az_cli.container_app_env_default_domain(resource_group, names["container_apps_env"])
        webhook_fqdn = az_cli.predicted_app_fqdn(names["voice_agent"], default_domain)
        az_cli.deploy_bicep(resource_group, "acs", "azbank-acs", {
            "name": names["acs"],
            "voiceAgentWebhookUrl": f"https://{webhook_fqdn}/api/incoming-call",
        })

    elif key == "voice_agent":
        default_domain = az_cli.container_app_env_default_domain(resource_group, names["container_apps_env"])
        app_fqdn = az_cli.predicted_app_fqdn(names["voice_agent"], default_domain)
        az_cli.deploy_bicep(resource_group, "voice-agent", "azbank-voice-agent", {
            "location": location,
            "environmentName": names["container_apps_env"],
            "name": names["voice_agent"],
            "image": image["voice_agent"],
            "acsConnectionString": az_cli.communication_connection_string(resource_group, names["acs"]),
            "appBaseUrl": f"https://{app_fqdn}",
            # D2 already migrated the app off this key (identity auth, live-verified
            # 2026-09-17) -- this module's `aoaiKey` param is still required, so a
            # placeholder is supplied rather than an empty string, and this is tracked
            # as Phase 7 debt to remove once the file split lands (Marco, 2026-09-18).
            "aoaiKey": "unused-post-d2-migration",
            "appInsightsConnectionString": az_cli.app_insights_connection_string(resource_group, names["app_insights"]),
            "dockerHubUsername": dockerhub["username"],
            "dockerHubPassword": dockerhub["password"],
        })

    elif key == "call_records_rbac":
        az_cli.deploy_bicep(resource_group, "call-records-store", "azbank-call-records-store", {
            "location": location,
            "name": names["call_records_account"],
            "voiceAgentPrincipalId": az_cli.container_app_principal_id(resource_group, names["voice_agent"]),
            "tableName": "callrecords",
        })

    elif key == "aoai":
        az_cli.deploy_bicep(resource_group, "aoai", "azbank-aoai", {
            "location": location,
            "name": names["aoai"],
            "voiceAgentPrincipalId": az_cli.container_app_principal_id(resource_group, names["voice_agent"]),
        })

    else:
        raise ValueError(f"unknown resource key: {key!r}")


def teardown_one(resource_group: str, key: str) -> None:
    names = config.NAMES

    if key == "app_insights":
        az_cli.delete_app_insights(resource_group, names["app_insights"])
    elif key == "container_apps_env":
        az_cli.delete_container_app_env(resource_group, names["container_apps_env"])
    elif key == "call_records_account":
        az_cli.delete_storage_account(resource_group, names["call_records_account"])
    elif key == "mock_core_banking":
        az_cli.delete_container_app(resource_group, names["mock_core_banking"])
    elif key == "voice_agent":
        az_cli.delete_container_app(resource_group, names["voice_agent"])
    elif key == "call_records_rbac":
        pass  # same physical resource as call_records_account; nothing separate to delete
    elif key == "aoai":
        az_cli.delete_cognitive_services_account(resource_group, names["aoai"])
    elif key == "acs":
        raise ValueError(
            "acs is never a teardown target (D5) -- resources.py should have refused this "
            "before it got here"
        )
    else:
        raise ValueError(f"unknown resource key: {key!r}")


def purge_soft_deleted_aoai(resource_group: str) -> str | None:
    """The last step of every teardown run, unconditionally -- Marco, 2026-09-18: a soft-deleted
    AOAI account blocks recreating one with the same name (a real, well-documented Azure failure
    mode), so teardown must not leave one behind for the next deploy to trip over."""
    for account in az_cli.list_soft_deleted_cognitive_services_accounts():
        if account.get("name") == config.NAMES["aoai"]:
            az_cli.purge_cognitive_services_account(resource_group, config.NAMES["aoai"], config.LOCATION)
            return account["name"]
    return None
