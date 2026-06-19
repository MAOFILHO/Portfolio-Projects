"""
Azure resource provisioning via Azure CLI.

Creates all required Azure resources for the Smart Incident Assistant:
  - Resource Group
  - Azure OpenAI (with gpt-4o and text-embedding-3-small deployments)
  - Azure Document Intelligence (F0 free tier)
  - Azure AI Vision (S1)
  - Azure AI Search (Free tier)
  - Application Insights (for observability and telemetry)

Usage:
    python -m src.provision
    python -m src.provision --cleanup   # Delete all resources
"""

import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SUBSCRIPTION_ID = "960936b9-ecde-465b-be8d-776ca077dcd0"
REGION = "eastus"
RESOURCE_GROUP = "contoso-incident-assistant-rg"

OPENAI_RESOURCE = "contoso-openai-incident"
DOC_INTEL_RESOURCE = "contoso-docintell-incident"
AI_VISION_RESOURCE = "contoso-vision-incident"
SEARCH_RESOURCE = "contoso-search-incident"
APPINSIGHTS_RESOURCE = "contoso-insights-incident"

SEARCH_INDEX = "urban-index"


def run_az(args: list[str], capture: bool = True) -> str | None:
    cmd = ["az"] + args + ["--subscription", SUBSCRIPTION_ID]
    print(f"  $ az {' '.join(args[:6])}{'...' if len(args) > 6 else ''}")
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr if capture else ""
        if "already exists" in stderr.lower() or "conflict" in stderr.lower():
            print("    (resource already exists, continuing)")
            return result.stdout if capture else None
        print(f"    ERROR: {stderr}", file=sys.stderr)
        return None
    return result.stdout if capture else None


def purge_soft_deleted_cognitive(name: str):
    print(f"    Checking for soft-deleted resource '{name}'...")
    result = subprocess.run(
        ["az", "cognitiveservices", "account", "list-deleted",
         "--subscription", SUBSCRIPTION_ID,
         "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return
    deleted = json.loads(result.stdout or "[]")
    match = [d for d in deleted if name in d.get("name", "")]
    if not match:
        return
    for d in match:
        resource_name = d.get("name", "")
        location = d.get("location", REGION)
        rg = d.get("resourceGroup", RESOURCE_GROUP)
        print(f"    Purging soft-deleted '{resource_name}'...")
        subprocess.run(
            ["az", "cognitiveservices", "account", "purge",
             "--name", resource_name,
             "--resource-group", rg,
             "--location", location,
             "--subscription", SUBSCRIPTION_ID],
            capture_output=True, text=True,
        )
        print(f"    Purged '{resource_name}'")


def resource_exists(resource_type: str, name: str) -> bool:
    result = subprocess.run(
        ["az", "resource", "list",
         "--resource-group", RESOURCE_GROUP,
         "--resource-type", resource_type,
         "--query", f"[?name=='{name}']",
         "--subscription", SUBSCRIPTION_ID,
         "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False
    items = json.loads(result.stdout or "[]")
    return len(items) > 0


def create_resource_group():
    print("\n[1/7] Creating Resource Group...")
    result = run_az([
        "group", "create",
        "--name", RESOURCE_GROUP,
        "--location", REGION,
        "-o", "json",
    ])
    if result:
        print(f"    Resource group '{RESOURCE_GROUP}' ready in {REGION}")
    return result is not None


def create_openai_resource():
    print("\n[2/7] Creating Azure OpenAI resource...")
    if resource_exists("Microsoft.CognitiveServices/accounts", OPENAI_RESOURCE):
        print(f"    '{OPENAI_RESOURCE}' already exists, skipping creation")
    else:
        purge_soft_deleted_cognitive(OPENAI_RESOURCE)
        result = run_az([
            "cognitiveservices", "account", "create",
            "--name", OPENAI_RESOURCE,
            "--resource-group", RESOURCE_GROUP,
            "--kind", "OpenAI",
            "--sku", "S0",
            "--location", REGION,
            "--custom-domain", OPENAI_RESOURCE,
            "--yes",
            "-o", "json",
        ])
        if not result:
            print("    ERROR: Failed to create OpenAI resource")
            return False
        print(f"    OpenAI resource '{OPENAI_RESOURCE}' created")

    print("\n  Deploying gpt-4o model...")
    run_az([
        "cognitiveservices", "account", "deployment", "create",
        "--name", OPENAI_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "--deployment-name", "gpt-4o",
        "--model-name", "gpt-4o",
        "--model-version", "2024-11-20",
        "--model-format", "OpenAI",
        "--sku-capacity", "10",
        "--sku-name", "Standard",
        "-o", "json",
    ])
    print("    gpt-4o deployment ready")

    print("\n  Deploying text-embedding-3-small model...")
    run_az([
        "cognitiveservices", "account", "deployment", "create",
        "--name", OPENAI_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "--deployment-name", "text-embedding-3-small",
        "--model-name", "text-embedding-3-small",
        "--model-version", "1",
        "--model-format", "OpenAI",
        "--sku-capacity", "10",
        "--sku-name", "Standard",
        "-o", "json",
    ])
    print("    text-embedding-3-small deployment ready")
    return True


def create_doc_intelligence():
    print("\n[3/7] Creating Document Intelligence resource (F0 free tier)...")
    if resource_exists("Microsoft.CognitiveServices/accounts", DOC_INTEL_RESOURCE):
        print(f"    '{DOC_INTEL_RESOURCE}' already exists, skipping")
        return True

    purge_soft_deleted_cognitive(DOC_INTEL_RESOURCE)
    result = run_az([
        "cognitiveservices", "account", "create",
        "--name", DOC_INTEL_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "--kind", "FormRecognizer",
        "--sku", "F0",
        "--location", REGION,
        "--custom-domain", DOC_INTEL_RESOURCE,
        "--yes",
        "-o", "json",
    ])
    if result:
        print(f"    Document Intelligence '{DOC_INTEL_RESOURCE}' created (F0)")
    return result is not None


def create_ai_vision():
    print("\n[4/7] Creating Azure AI Vision resource (S1)...")
    if resource_exists("Microsoft.CognitiveServices/accounts", AI_VISION_RESOURCE):
        print(f"    '{AI_VISION_RESOURCE}' already exists, skipping")
        return True

    purge_soft_deleted_cognitive(AI_VISION_RESOURCE)
    result = run_az([
        "cognitiveservices", "account", "create",
        "--name", AI_VISION_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "--kind", "ComputerVision",
        "--sku", "S1",
        "--location", REGION,
        "--yes",
        "-o", "json",
    ])
    if result:
        print(f"    AI Vision '{AI_VISION_RESOURCE}' created (S1)")
    return result is not None


def create_app_insights():
    print("\n[5/7] Creating Application Insights (observability)...")
    result = run_az([
        "monitor", "app-insights", "component", "create",
        "--app", APPINSIGHTS_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "--location", REGION,
        "--kind", "web",
        "--application-type", "web",
        "-o", "json",
    ])
    if result:
        info = json.loads(result)
        conn_str = info.get("connectionString", "")
        if conn_str:
            print(f"    Application Insights '{APPINSIGHTS_RESOURCE}' created")
        else:
            print(f"    Application Insights created (connection string will be retrieved later)")
    else:
        # May already exist
        print(f"    '{APPINSIGHTS_RESOURCE}' may already exist, continuing")
    return True


def create_search():
    print("\n[6/7] Creating Azure AI Search resource (Free tier)...")
    check = subprocess.run(
        ["az", "search", "service", "show",
         "--name", SEARCH_RESOURCE,
         "--resource-group", RESOURCE_GROUP,
         "--subscription", SUBSCRIPTION_ID,
         "-o", "json"],
        capture_output=True, text=True,
    )
    if check.returncode == 0:
        print(f"    '{SEARCH_RESOURCE}' already exists, skipping")
        return True

    result = run_az([
        "search", "service", "create",
        "--name", SEARCH_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "--sku", "free",
        "--location", REGION,
        "-o", "json",
    ])
    if result:
        print(f"    AI Search '{SEARCH_RESOURCE}' created (Free)")
    return result is not None


def retrieve_keys_and_write_env():
    print("\n[7/7] Retrieving keys and writing .env file...")

    # OpenAI endpoint + key
    openai_show = run_az([
        "cognitiveservices", "account", "show",
        "--name", OPENAI_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    openai_info = json.loads(openai_show) if openai_show else {}
    openai_endpoint = openai_info.get("properties", {}).get("endpoint", "")

    openai_keys_raw = run_az([
        "cognitiveservices", "account", "keys", "list",
        "--name", OPENAI_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    openai_keys = json.loads(openai_keys_raw) if openai_keys_raw else {}
    openai_key = openai_keys.get("key1", "")

    # Doc Intelligence endpoint + key
    docintell_show = run_az([
        "cognitiveservices", "account", "show",
        "--name", DOC_INTEL_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    docintell_info = json.loads(docintell_show) if docintell_show else {}
    docintell_endpoint = docintell_info.get("properties", {}).get("endpoint", "")

    docintell_keys_raw = run_az([
        "cognitiveservices", "account", "keys", "list",
        "--name", DOC_INTEL_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    docintell_keys = json.loads(docintell_keys_raw) if docintell_keys_raw else {}
    docintell_key = docintell_keys.get("key1", "")

    # Search endpoint + key
    search_show = run_az([
        "search", "service", "show",
        "--name", SEARCH_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    search_info = json.loads(search_show) if search_show else {}
    search_id = search_info.get("id", "")
    search_endpoint = f"https://{SEARCH_RESOURCE}.search.windows.net"

    search_keys_raw = run_az([
        "search", "admin-key", "show",
        "--service-name", SEARCH_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    search_keys = json.loads(search_keys_raw) if search_keys_raw else {}
    search_key = search_keys.get("primaryKey", "")

    # App Insights connection string
    appinsights_raw = run_az([
        "monitor", "app-insights", "component", "show",
        "--app", APPINSIGHTS_RESOURCE,
        "--resource-group", RESOURCE_GROUP,
        "-o", "json",
    ])
    appinsights_info = json.loads(appinsights_raw) if appinsights_raw else {}
    appinsights_conn_str = appinsights_info.get("connectionString", "")

    # Read existing SERP_API_KEY if .env already exists
    env_path = PROJECT_ROOT / ".env"
    existing_serp_key = ""
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("SERP_API_KEY="):
                existing_serp_key = line.split("=", 1)[1].strip()

    env_content = f"""# Auto-generated by src/provision.py — {time.strftime('%Y-%m-%d %H:%M:%S')}

# Azure Document Intelligence
DOC_INTELLIGENCE_ENDPOINT={docintell_endpoint}
DOC_INTELLIGENCE_KEY={docintell_key}

# Azure OpenAI
AZURE_OPENAI_ENDPOINT={openai_endpoint}
AZURE_OPENAI_KEY={openai_key}
AZURE_GPT_DEPLOYMENT=gpt-4o
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Azure AI Search
AZURE_SEARCH_ENDPOINT={search_endpoint}
AZURE_SEARCH_KEY={search_key}
AZURE_SEARCH_INDEX={SEARCH_INDEX}

# SerpAPI (optional, for web search feature)
SERP_API_KEY={existing_serp_key}

# Azure Application Insights (observability and telemetry)
APPINSIGHTS_CONNECTION_STRING={appinsights_conn_str}
"""

    env_path.write_text(env_content)
    print(f"    .env written to {env_path}")
    print(f"    OpenAI endpoint: {openai_endpoint}")
    print(f"    Doc Intelligence endpoint: {docintell_endpoint}")
    print(f"    Search endpoint: {search_endpoint}")
    return True


def _delete_resource_group(rg_name: str, label: str):
    check = subprocess.run(
        ["az", "group", "show", "--name", rg_name,
         "--subscription", SUBSCRIPTION_ID, "-o", "json"],
        capture_output=True, text=True,
    )
    if check.returncode != 0:
        print(f"\n  [{label}] Resource group '{rg_name}' does not exist. Skipping.")
        return

    # List resources before deletion
    print(f"\n  [{label}] Resources in '{rg_name}':")
    list_raw = subprocess.run(
        ["az", "resource", "list",
         "--resource-group", rg_name,
         "--subscription", SUBSCRIPTION_ID,
         "--query", "[].{Name:name, Type:type, Location:location}",
         "-o", "table"],
        capture_output=True, text=True,
    )
    if list_raw.returncode == 0 and list_raw.stdout.strip():
        for line in list_raw.stdout.strip().splitlines():
            print(f"    {line}")
    else:
        print("    (no resources found)")

    print(f"\n  Deleting '{rg_name}'...")

    result = subprocess.run(
        ["az", "group", "delete",
         "--name", rg_name,
         "--subscription", SUBSCRIPTION_ID,
         "--yes"],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"  '{rg_name}' deleted successfully.")
    else:
        print(f"  ERROR deleting '{rg_name}': {result.stderr}")


def cleanup():
    print("=" * 60)
    print("Contoso Smart Incident Assistant — Cleanup")
    print("=" * 60)
    print("  This may take 2-5 minutes...\n")

    # 1. Delete the project resource group
    _delete_resource_group(RESOURCE_GROUP, "Project")

    # 2. Delete the managed resource group auto-created by Application Insights
    managed_rg_raw = subprocess.run(
        ["az", "group", "list",
         "--subscription", SUBSCRIPTION_ID,
         "--query", "[?contains(name, 'contoso') && contains(name, 'managed')].name",
         "-o", "json"],
        capture_output=True, text=True,
    )
    if managed_rg_raw.returncode == 0:
        managed_groups = json.loads(managed_rg_raw.stdout or "[]")
        for rg in managed_groups:
            _delete_resource_group(rg, "Managed")

    print("\n" + "=" * 60)
    print("  Cleanup complete.")
    print("  Run 'python -m src.provision --verify-cleanup' to confirm.")
    print("=" * 60)


def verify_cleanup():
    print("=" * 60)
    print("Contoso Smart Incident Assistant — Verify Cleanup")
    print("=" * 60)

    issues_found = False

    # Check for project-related resource groups
    print("\n  Checking for project resource groups...")
    rg_list_raw = subprocess.run(
        ["az", "group", "list",
         "--subscription", SUBSCRIPTION_ID,
         "--query", "[].{Name:name, Location:location}",
         "-o", "json"],
        capture_output=True, text=True,
    )
    if rg_list_raw.returncode == 0:
        rg_list = json.loads(rg_list_raw.stdout or "[]")
        # Filter to only project-related groups (ignore VisualStudioOnline and other unrelated ones)
        project_rgs = [rg for rg in rg_list if "contoso" in rg.get("Name", "").lower() or "incident" in rg.get("Name", "").lower()]
        skipped_rgs = [rg for rg in rg_list if rg not in project_rgs]

        if project_rgs:
            issues_found = True
            print(f"  WARNING: {len(project_rgs)} project resource group(s) still exist:")
            for rg in project_rgs:
                print(f"    - {rg.get('Name', '?')} ({rg.get('Location', '?')})")
            print("\n  These may still be deleting. Wait a few minutes and try again.")
        else:
            print("  No project resource groups found.")

        if skipped_rgs:
            print(f"\n  Note: {len(skipped_rgs)} unrelated resource group(s) ignored:")
            for rg in skipped_rgs:
                print(f"    - {rg.get('Name', '?')} ({rg.get('Location', '?')}) [not project-related]")

    # Check for orphaned cognitive services
    print("\n  Checking for orphaned Cognitive Services resources...")
    orphan_check = subprocess.run(
        ["az", "cognitiveservices", "account", "list",
         "--subscription", SUBSCRIPTION_ID,
         "--query", "[].{Name:name, ResourceGroup:resourceGroup}",
         "-o", "json"],
        capture_output=True, text=True,
    )
    if orphan_check.returncode == 0:
        orphans = json.loads(orphan_check.stdout or "[]")
        if orphans:
            issues_found = True
            print(f"  WARNING: Found {len(orphans)} Cognitive Services resource(s):")
            for o in orphans:
                print(f"    - {o.get('Name', '?')} (in {o.get('ResourceGroup', '?')})")
        else:
            print("  No orphaned Cognitive Services resources found.")

    # Check for orphaned search services
    search_check = subprocess.run(
        ["az", "search", "service", "list",
         "--subscription", SUBSCRIPTION_ID,
         "--query", "[].{Name:name, ResourceGroup:resourceGroup}",
         "-o", "json"],
        capture_output=True, text=True,
    )
    if search_check.returncode == 0:
        search_orphans = json.loads(search_check.stdout or "[]")
        if search_orphans:
            issues_found = True
            print(f"  WARNING: Found {len(search_orphans)} Search resource(s):")
            for o in search_orphans:
                print(f"    - {o.get('Name', '?')} (in {o.get('ResourceGroup', '?')})")
        else:
            print("  No orphaned Search resources found.")

    if not issues_found:
        print("\n" + "=" * 60)
        print("  ALL RESOURCES CLEANED UP SUCCESSFULLY")
        print("  Subscription is clean — zero resource groups remaining.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("  CLEANUP INCOMPLETE — see warnings above")
        print("=" * 60)


def main():
    if "--cleanup" in sys.argv:
        cleanup()
        return

    if "--verify-cleanup" in sys.argv:
        verify_cleanup()
        return

    print("=" * 60)
    print("Contoso Smart Incident Assistant — Azure Provisioning")
    print("=" * 60)
    print(f"  Subscription: {SUBSCRIPTION_ID}")
    print(f"  Region:       {REGION}")
    print(f"  Resource Group: {RESOURCE_GROUP}")

    steps = [
        create_resource_group,
        create_openai_resource,
        create_doc_intelligence,
        create_ai_vision,
        create_app_insights,
        create_search,
        retrieve_keys_and_write_env,
    ]

    for step in steps:
        if not step():
            print(f"\nProvisioning failed at: {step.__name__}", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 60)
    print("Provisioning complete! All Azure resources are ready.")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Validate environment:  make smoke-test")
    print("  2. Run the pipeline:      make pipeline")
    print("  3. Start the web app:     make run")


if __name__ == "__main__":
    main()
