"""Step 4: Query Azure for deployed resource names and endpoints."""

from __future__ import annotations

import json

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_az


def _query(args: list[str], label: str) -> str | None:
    result = run_az(args)
    if result.success and result.stdout:
        value = result.stdout.strip().strip('"')
        if value:
            print_substep(f"{label}: {value}", "ok")
            return value
    print_substep(f"{label}: not found", "warn")
    return None


def run(ctx: dict) -> dict:
    config = ctx["config"]
    rg = config.azure_resource_group

    resources: dict[str, str] = {}

    # Container App
    app_name = _query(
        ["containerapp", "list", "-g", rg, "--query",
         "[?contains(name,'-api')].name | [0]", "-o", "tsv"],
        "Container App",
    )
    if app_name:
        resources["app_name"] = app_name

    # API FQDN
    if app_name:
        fqdn = _query(
            ["containerapp", "show", "-g", rg, "-n", app_name,
             "--query", "properties.configuration.ingress.fqdn", "-o", "tsv"],
            "API FQDN",
        )
        if fqdn:
            resources["api_fqdn"] = fqdn

    # AI Search
    search_name = _query(
        ["search", "service", "list", "-g", rg, "--query", "[0].name", "-o", "tsv"],
        "AI Search",
    )
    if search_name:
        resources["search_name"] = search_name

    # OpenAI
    openai_name = _query(
        ["cognitiveservices", "account", "list", "-g", rg,
         "--query", "[?kind=='OpenAI'].name | [0]", "-o", "tsv"],
        "Azure OpenAI",
    )
    if openai_name:
        resources["openai_name"] = openai_name

    # Document Intelligence
    docintel_name = _query(
        ["cognitiveservices", "account", "list", "-g", rg,
         "--query", "[?kind=='FormRecognizer'].name | [0]", "-o", "tsv"],
        "Document Intelligence",
    )
    if docintel_name:
        resources["docintel_name"] = docintel_name

    # Key Vault
    kv_name = _query(
        ["keyvault", "list", "-g", rg, "--query", "[0].name", "-o", "tsv"],
        "Key Vault",
    )
    if kv_name:
        resources["kv_name"] = kv_name

    # Key Vault ID
    if kv_name:
        kv_id = _query(
            ["keyvault", "show", "-n", kv_name, "--query", "id", "-o", "tsv"],
            "Key Vault ID",
        )
        if kv_id:
            resources["kv_id"] = kv_id

    # Cosmos DB
    cosmos_name = _query(
        ["cosmosdb", "list", "-g", rg, "--query", "[0].name", "-o", "tsv"],
        "Cosmos DB",
    )
    if cosmos_name:
        resources["cosmos_name"] = cosmos_name

    # Storage Account
    storage_name = _query(
        ["storage", "account", "list", "-g", rg, "--query", "[0].name", "-o", "tsv"],
        "Storage Account",
    )
    if storage_name:
        resources["storage_name"] = storage_name

    # App Insights
    result = run_az(
        ["monitor", "app-insights", "component", "list", "-g", rg,
         "--query", "[0].{name:name,key:instrumentationKey,connString:connectionString}"]
    )
    if result.success and result.stdout:
        try:
            ai = json.loads(result.stdout)
            if ai:
                resources["app_insights_name"] = ai.get("name", "")
                resources["app_insights_key"] = ai.get("key", "")
                resources["app_insights_conn_string"] = ai.get("connString", "")
                print_substep(f"App Insights: {ai.get('name', 'found')}", "ok")
        except json.JSONDecodeError:
            pass

    # Static Web App
    swa_name = _query(
        ["staticwebapp", "list", "-g", rg, "--query", "[0].name", "-o", "tsv"],
        "Static Web App",
    )
    if swa_name:
        resources["swa_name"] = swa_name

    ctx["state"].update_resources(resources)

    required = ["app_name", "api_fqdn"]
    missing = [r for r in required if r not in resources]
    if missing:
        return {"success": False, "error": f"Critical resources not found: {', '.join(missing)}"}

    return {"success": True, "resources": resources}
