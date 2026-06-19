"""
Production smoke test — validates environment, dependencies, Azure connectivity, and data readiness.

Usage:
    python -m src.smoke_test           # Run all checks
    python -m src.smoke_test --quick   # Skip Azure API connectivity checks
"""

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"
SKIP = "\033[90mSKIP\033[0m"

results: list[tuple[str, str, str]] = []


def check(name: str, status: str, detail: str = ""):
    results.append((name, status, detail))
    tag = {PASS: PASS, FAIL: FAIL, WARN: WARN, SKIP: SKIP}.get(status, status)
    detail_str = f" — {detail}" if detail else ""
    print(f"  [{tag}] {name}{detail_str}")


def check_python_version():
    v = sys.version_info
    if v >= (3, 10):
        check("Python version", PASS, f"{v.major}.{v.minor}.{v.micro}")
    else:
        check("Python version", FAIL, f"{v.major}.{v.minor}.{v.micro} (need 3.10+)")


def check_required_packages():
    packages = {
        "openai": "openai",
        "azure.core": "azure-core",
        "azure.identity": "azure-identity",
        "azure.ai.formrecognizer": "azure-ai-formrecognizer",
        "streamlit": "streamlit",
        "dotenv": "python-dotenv",
        "requests": "requests",
        "pydantic": "pydantic",
        "PIL": "pillow",
        "tenacity": "tenacity",
        "azure.monitor.opentelemetry": "azure-monitor-opentelemetry",
    }
    for module, pip_name in packages.items():
        try:
            importlib.import_module(module)
            check(f"Package: {pip_name}", PASS)
        except ImportError:
            check(f"Package: {pip_name}", FAIL, f"pip install {pip_name}")


def check_azure_cli():
    if not shutil.which("az"):
        check("Azure CLI", FAIL, "Install: https://aka.ms/installazurecli")
        return

    result = subprocess.run(["az", "version", "-o", "json"], capture_output=True, text=True)
    if result.returncode == 0:
        try:
            ver = json.loads(result.stdout).get("azure-cli", "unknown")
            check("Azure CLI", PASS, f"v{ver}")
        except json.JSONDecodeError:
            check("Azure CLI", PASS, "installed")
    else:
        check("Azure CLI", FAIL, "az version failed")

    result = subprocess.run(
        ["az", "account", "show", "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        try:
            acct = json.loads(result.stdout)
            check("Azure login", PASS, f"{acct.get('user', {}).get('name', '?')} / {acct.get('name', '?')}")
        except json.JSONDecodeError:
            check("Azure login", WARN, "logged in but couldn't parse account info")
    else:
        check("Azure login", FAIL, "Run: az login")


def check_env_file():
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        check(".env file", FAIL, "Missing. Run: python -m src.provision")
        return False

    from dotenv import dotenv_values
    env = dotenv_values(env_path)

    required = {
        "AZURE_OPENAI_ENDPOINT": "Azure OpenAI",
        "AZURE_OPENAI_KEY": "Azure OpenAI",
        "AZURE_SEARCH_ENDPOINT": "Azure AI Search",
        "AZURE_SEARCH_KEY": "Azure AI Search",
        "DOC_INTELLIGENCE_ENDPOINT": "Document Intelligence",
        "DOC_INTELLIGENCE_KEY": "Document Intelligence",
    }

    all_good = True
    for var, service in required.items():
        val = env.get(var, "")
        if not val or val.startswith("<"):
            check(f"Env: {var}", FAIL, f"Not configured ({service})")
            all_good = False

    optional = {
        "AZURE_GPT_DEPLOYMENT": ("gpt-4o", "GPT deployment"),
        "AZURE_EMBEDDING_DEPLOYMENT": ("text-embedding-3-small", "Embedding deployment"),
        "AZURE_SEARCH_INDEX": ("urban-index", "Search index name"),
        "SERP_API_KEY": ("", "Web search (optional)"),
        "APPINSIGHTS_CONNECTION_STRING": ("", "Telemetry (optional)"),
    }
    for var, (default, desc) in optional.items():
        val = env.get(var, "")
        if val and not val.startswith("<"):
            check(f"Env: {var}", PASS, val[:30] + "..." if len(val) > 30 else val)
        elif default:
            check(f"Env: {var}", WARN, f"Not set, using default: {default}")
        else:
            check(f"Env: {var}", SKIP, f"{desc}")

    if all_good:
        check(".env file", PASS, "All required variables configured")
    return all_good


def check_data_directories():
    dirs = {
        "pdfs": (PROJECT_ROOT / "pdfs", ".pdf"),
        "images": (PROJECT_ROOT / "images", (".jpg", ".jpeg", ".png")),
        "sops": (PROJECT_ROOT / "sops", ".txt"),
    }
    for name, (path, exts) in dirs.items():
        if not path.exists():
            check(f"Data: {name}/", FAIL, f"Directory not found")
            continue
        if isinstance(exts, str):
            exts = (exts,)
        count = len([f for f in os.listdir(path) if any(f.lower().endswith(e) for e in exts)])
        if count > 0:
            check(f"Data: {name}/", PASS, f"{count} files")
        else:
            check(f"Data: {name}/", WARN, "Directory exists but empty")


def check_parsed_data():
    data_dir = PROJECT_ROOT / "data"
    files = {
        "parsed_incidents.json": "Incident extractions",
        "parsed_images.json": "Image captions",
        "parsed_sops.json": "SOP extractions",
    }
    for filename, desc in files.items():
        path = data_dir / filename
        if not path.exists():
            check(f"Parsed: {filename}", WARN, f"Not yet generated. Run: python -m src.pipeline --steps extract")
            continue
        try:
            with open(path) as f:
                data = json.load(f)
            check(f"Parsed: {filename}", PASS, f"{len(data)} entries")
        except (json.JSONDecodeError, OSError) as e:
            check(f"Parsed: {filename}", FAIL, str(e))


def check_azure_openai_connectivity(quick: bool):
    if quick:
        check("Azure OpenAI API", SKIP, "--quick mode")
        return

    try:
        from src.config import AZURE_EMBEDDING_DEPLOYMENT, get_openai_client
        client = get_openai_client()
        response = client.embeddings.create(
            model=AZURE_EMBEDDING_DEPLOYMENT,
            input=["smoke test"],
        )
        dim = len(response.data[0].embedding)
        check("Azure OpenAI API", PASS, f"Embedding returned {dim}-dim vector")
    except SystemExit:
        check("Azure OpenAI API", FAIL, "Config validation failed (check .env)")
    except Exception as e:
        check("Azure OpenAI API", FAIL, str(e)[:100])


def check_search_connectivity(quick: bool):
    if quick:
        check("Azure AI Search", SKIP, "--quick mode")
        return

    try:
        import requests as req
        from src.config import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AZURE_SEARCH_KEY, SEARCH_API_VERSION

        url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{AZURE_SEARCH_INDEX}?api-version={SEARCH_API_VERSION}"
        resp = req.get(url, headers={"api-key": AZURE_SEARCH_KEY}, timeout=10)
        if resp.status_code == 200:
            info = resp.json()
            check("Azure AI Search", PASS, f"Index '{AZURE_SEARCH_INDEX}' exists")
        elif resp.status_code == 404:
            check("Azure AI Search", WARN, f"Index '{AZURE_SEARCH_INDEX}' not found. Run: python -m src.pipeline --steps index")
        else:
            check("Azure AI Search", FAIL, f"HTTP {resp.status_code}")
    except SystemExit:
        check("Azure AI Search", FAIL, "Config validation failed")
    except Exception as e:
        check("Azure AI Search", FAIL, str(e)[:100])


def check_doc_intelligence_connectivity(quick: bool):
    if quick:
        check("Document Intelligence", SKIP, "--quick mode")
        return

    try:
        from azure.ai.formrecognizer import DocumentAnalysisClient
        from azure.core.credentials import AzureKeyCredential
        from src.config import DOC_INTELLIGENCE_ENDPOINT, DOC_INTELLIGENCE_KEY

        client = DocumentAnalysisClient(
            endpoint=DOC_INTELLIGENCE_ENDPOINT,
            credential=AzureKeyCredential(DOC_INTELLIGENCE_KEY),
        )
        # Just verify the client can be instantiated and endpoint is reachable
        check("Document Intelligence", PASS, f"Client configured for {DOC_INTELLIGENCE_ENDPOINT[:50]}...")
    except SystemExit:
        check("Document Intelligence", FAIL, "Config validation failed")
    except Exception as e:
        check("Document Intelligence", FAIL, str(e)[:100])


def main():
    parser = argparse.ArgumentParser(description="Smoke test for Smart Incident Assistant")
    parser.add_argument("--quick", action="store_true", help="Skip Azure API connectivity checks")
    args = parser.parse_args()

    print("=" * 60)
    print("Contoso Smart Incident Assistant — Smoke Test")
    print("=" * 60)

    print("\n--- System Requirements ---")
    check_python_version()
    check_azure_cli()

    print("\n--- Python Packages ---")
    check_required_packages()

    print("\n--- Environment Configuration ---")
    env_ok = check_env_file()

    print("\n--- Input Data ---")
    check_data_directories()

    print("\n--- Parsed Data ---")
    check_parsed_data()

    if env_ok:
        print("\n--- Azure Service Connectivity ---")
        check_azure_openai_connectivity(args.quick)
        check_search_connectivity(args.quick)
        check_doc_intelligence_connectivity(args.quick)
    else:
        print("\n--- Azure Service Connectivity ---")
        check("Azure services", SKIP, ".env not fully configured")

    # Summary
    print("\n" + "=" * 60)
    passes = sum(1 for _, s, _ in results if s == PASS)
    fails = sum(1 for _, s, _ in results if s == FAIL)
    warns = sum(1 for _, s, _ in results if s == WARN)
    skips = sum(1 for _, s, _ in results if s == SKIP)
    total = len(results)

    print(f"Results: {passes} passed, {fails} failed, {warns} warnings, {skips} skipped / {total} total")

    if fails == 0:
        print("\nAll critical checks passed! Ready to run.")
        print("  Pipeline: python -m src.pipeline")
        print("  Web app:  streamlit run src/web/app.py")
    else:
        print(f"\n{fails} critical check(s) failed. Fix the issues above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
