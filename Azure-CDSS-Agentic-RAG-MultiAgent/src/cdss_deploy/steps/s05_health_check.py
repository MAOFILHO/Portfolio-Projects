"""Step 5: Validate backend health with retry and exponential backoff."""

from __future__ import annotations

import json
import time

import httpx

from cdss_deploy.console import print_substep


def run(ctx: dict) -> dict:
    state = ctx["state"]
    fqdn = state.deployed_resources.get("api_fqdn")
    if not fqdn:
        return {"success": False, "error": "API FQDN not found — run step 4 first"}

    url = f"https://{fqdn}/api/v1/health"
    print_substep(f"Health endpoint: {url}", "info")

    max_retries = 10
    backoff = 10

    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    status = data.get("status", "unknown")
                    services = {
                        k: v for k, v in data.items()
                        if k not in ("status", "version", "service", "timestamp")
                    }
                    print_substep(f"Status: {status}", "ok")
                    for svc, svc_status in services.items():
                        icon = "ok" if svc_status == "healthy" else "warn"
                        print_substep(f"  {svc}: {svc_status}", icon)
                    return {"success": True}
                except json.JSONDecodeError:
                    print_substep(f"Attempt {attempt}: got 200 but invalid JSON", "warn")
            else:
                print_substep(
                    f"Attempt {attempt}/{max_retries}: HTTP {resp.status_code}", "warn"
                )
        except httpx.ConnectError:
            print_substep(
                f"Attempt {attempt}/{max_retries}: connection refused (container starting...)",
                "warn",
            )
        except httpx.TimeoutException:
            print_substep(f"Attempt {attempt}/{max_retries}: timeout", "warn")
        except Exception as e:
            print_substep(f"Attempt {attempt}/{max_retries}: {e}", "warn")

        if attempt < max_retries:
            wait = min(backoff * attempt, 60)
            print_substep(f"Retrying in {wait}s...", "info")
            time.sleep(wait)

    return {"success": False, "error": f"Backend health check failed after {max_retries} attempts"}
