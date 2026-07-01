"""Post-deploy smoke tests: validate deployed infrastructure is functional."""

from __future__ import annotations

import json

import httpx

from cdss_deploy.console import console, print_substep
from cdss_deploy.state import DeploymentState


def run_post_checks(state: DeploymentState) -> bool:
    console.rule("[bold]Post-Deploy Smoke Tests[/bold]", style="cyan")
    passed = 0
    failed = 0

    api_fqdn = state.deployed_resources.get("api_fqdn", "")
    swa_host = state.deployed_resources.get("swa_host", "")

    if not api_fqdn:
        console.print("[red]No API FQDN in deployment state. Run deployment first.[/red]")
        return False

    # 1. Health check
    try:
        resp = httpx.get(f"https://{api_fqdn}/api/v1/health", timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "unknown")
            print_substep(f"Backend health: {status}", "ok")
            passed += 1

            services = {k: v for k, v in data.items() if k not in ("status", "version", "service", "timestamp")}
            healthy_count = sum(1 for v in services.values() if v == "healthy")
            print_substep(f"  Healthy services: {healthy_count}/{len(services)}", "ok")
        else:
            print_substep(f"Backend health: HTTP {resp.status_code}", "error")
            failed += 1
    except Exception as e:
        print_substep(f"Backend health: {e}", "error")
        failed += 1

    # 2. API docs reachable
    try:
        resp = httpx.get(f"https://{api_fqdn}/docs", timeout=10, follow_redirects=True)
        if resp.status_code == 200:
            print_substep("API docs (Swagger): reachable", "ok")
            passed += 1
        else:
            print_substep(f"API docs: HTTP {resp.status_code}", "warn")
            failed += 1
    except Exception as e:
        print_substep(f"API docs: {e}", "error")
        failed += 1

    # 3. Frontend reachable
    if swa_host:
        try:
            resp = httpx.get(f"https://{swa_host}", timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                print_substep("Frontend (SWA): reachable", "ok")
                passed += 1
            else:
                print_substep(f"Frontend: HTTP {resp.status_code}", "warn")
                failed += 1
        except Exception as e:
            print_substep(f"Frontend: {e}", "error")
            failed += 1
    else:
        print_substep("Frontend URL not available, skipping", "info")

    # 4. Patient search (unauthenticated — may return 401 if auth enabled, that's OK)
    try:
        resp = httpx.get(
            f"https://{api_fqdn}/api/v1/patients?search=patient&limit=1",
            timeout=10,
        )
        if resp.status_code == 200:
            print_substep("Patient API: accessible (auth disabled)", "ok")
            passed += 1
        elif resp.status_code == 401:
            print_substep("Patient API: auth required (expected in production)", "ok")
            passed += 1
        else:
            print_substep(f"Patient API: HTTP {resp.status_code}", "warn")
            failed += 1
    except Exception as e:
        print_substep(f"Patient API: {e}", "error")
        failed += 1

    console.print()
    total = passed + failed
    if failed == 0:
        console.print(f"[green bold]All {passed} post-deploy checks passed.[/green bold]")
    else:
        console.print(f"[yellow]{passed}/{total} checks passed, {failed} warnings/failures.[/yellow]")

    return failed == 0
