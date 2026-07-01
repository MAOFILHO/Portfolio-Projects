"""Step 12: End-to-end validation — health, API endpoints, frontend reachability."""

from __future__ import annotations

import json

import httpx

from cdss_deploy.console import console, print_substep
from cdss_deploy.runner import run_az


def _check_url(url: str, label: str, expected_status: int = 200) -> bool:
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        if resp.status_code == expected_status:
            print_substep(f"{label}: OK ({resp.status_code})", "ok")
            return True
        print_substep(f"{label}: HTTP {resp.status_code}", "warn")
        return False
    except Exception as e:
        print_substep(f"{label}: {e}", "error")
        return False


def run(ctx: dict) -> dict:
    state = ctx["state"]
    config = ctx["config"]
    rg = config.azure_resource_group
    api_fqdn = state.deployed_resources.get("api_fqdn", "")
    swa_host = state.deployed_resources.get("swa_host", "")
    app_name = state.deployed_resources.get("app_name", "")

    passed = 0
    failed = 0

    # 1. Backend health
    if api_fqdn:
        if _check_url(f"https://{api_fqdn}/api/v1/health", "Backend health"):
            passed += 1
        else:
            failed += 1

    # 2. API docs
    if api_fqdn:
        if _check_url(f"https://{api_fqdn}/docs", "API docs (Swagger)"):
            passed += 1
        else:
            failed += 1

    # 3. Frontend
    if swa_host:
        if _check_url(f"https://{swa_host}", "Frontend (SWA)"):
            passed += 1
        else:
            failed += 1
    else:
        print_substep("Frontend URL not available, skipping", "warn")

    # 4. Auth configuration check
    if app_name:
        result = run_az([
            "containerapp", "show", "-g", rg, "-n", app_name,
            "--query",
            "properties.template.containers[0].env[?name=='CDSS_AUTH_ENABLED'||name=='CDSS_AUTH_TENANT_ID'||name=='CDSS_AUTH_AUDIENCE'].[name,value]",
            "-o", "json",
        ])
        if result.success:
            try:
                env_pairs = json.loads(result.stdout)
                auth_vars = {pair[0]: pair[1] for pair in env_pairs if pair}
                auth_enabled = auth_vars.get("CDSS_AUTH_ENABLED", "false")
                auth_audience = auth_vars.get("CDSS_AUTH_AUDIENCE", "")
                print_substep(f"Auth enabled: {auth_enabled}", "ok")
                if auth_audience:
                    print_substep(f"Auth audience: {auth_audience}", "ok")
                    passed += 1
                else:
                    print_substep("Auth audience: NOT SET", "warn")
                    failed += 1
            except json.JSONDecodeError:
                print_substep("Could not parse auth config", "warn")

    # 5. CORS check
    if app_name:
        result = run_az([
            "containerapp", "ingress", "cors", "show", "-g", rg, "-n", app_name,
        ])
        if result.success:
            try:
                cors = json.loads(result.stdout)
                origins = cors.get("allowedOrigins", [])
                print_substep(f"CORS origins: {origins}", "ok")
                passed += 1
            except json.JSONDecodeError:
                print_substep("Could not parse CORS config", "warn")

    # 6. PubMed env vars
    if app_name:
        result = run_az([
            "containerapp", "show", "-g", rg, "-n", app_name,
            "--query",
            "properties.template.containers[0].env[?name=='CDSS_PUBMED_API_KEY'||name=='CDSS_PUBMED_EMAIL'||name=='CDSS_PUBMED_BASE_URL'].[name]",
            "-o", "json",
        ])
        if result.success:
            try:
                pubmed_vars = json.loads(result.stdout)
                count = len([v for v in pubmed_vars if v])
                if count >= 2:
                    print_substep(f"PubMed env vars: {count} configured", "ok")
                    passed += 1
                else:
                    print_substep(f"PubMed env vars: only {count} found", "warn")
            except json.JSONDecodeError:
                pass

    console.print()
    total = passed + failed
    if failed == 0:
        print_substep(f"All {passed} checks passed", "ok")
        return {"success": True}
    else:
        print_substep(f"{passed}/{total} checks passed, {failed} failed", "warn")
        return {"success": True, "outputs": {"passed": passed, "failed": failed}}
