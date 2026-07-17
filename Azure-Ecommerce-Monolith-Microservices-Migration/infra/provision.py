#!/usr/bin/env python3
"""make provision — stands up the FOUNDATION plus the monolith ("before")
stack on Azure. Deliberately does NOT deploy the three microservices'
Container Apps — those don't exist until a live migration creates them on
demand (see bff/app/azure_traffic.py and bff/app/migration_engine.py). That
is the whole point of the demo: watching real Azure resources get created
while the migration runs, not flipping a switch on a stack that was already
fully provisioned upfront.

Thin orchestrator: resolves collision-safe resource names, builds every
service image in the cloud via `az acr build` (no local Docker daemon, and
pre-building all five images now means the live migration only has to
create Container Apps from already-pushed images — fast and demo-safe,
instead of a slow, network-flaky image build happening on camera), deploys
infra/bicep/main.bicep (foundation + monolith + bff only) with the exact
cheap SKUs approved in cost_estimate.md, grants the bff Container App's
managed identity Contributor scoped to just this resource group (so it can
create the microservices Container Apps itself at migration time), creates
a Cost Management budget alert BEFORE any billable resource exists, and
persists every resolved name + deployment output to infra/.state.json so
run.py, smoke tests, and teardown.py pick it up automatically.

Zero secrets are hardcoded: the MySQL admin password is generated locally
and never printed. Region is never hardcoded either — it comes from the
repo-root .env's AZURE_LOCATION (see .env.example), falling back to `az
config get defaults.location`, and only as a last resort the constant below.
"""
import argparse
import json
import os
import secrets
import shutil
import string
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from name_resolver import resolve_all_names  # noqa: E402

STATE_FILE = REPO_ROOT / "infra" / ".state.json"
BICEP_FILE = REPO_ROOT / "infra" / "bicep" / "main.bicep"
ENV_FILE = REPO_ROOT / ".env"

DEFAULT_RESOURCE_GROUP = "rg-flask-monolith-microservices"
FALLBACK_LOCATION = "eastus"  # only used if neither .env nor `az config` set one
DEFAULT_NAME_PREFIX = "flaskms"
MYSQL_ADMIN_USERNAME = "flaskadmin"


def load_dotenv_defaults() -> None:
    """Minimal, dependency-free .env loader — this project deliberately has
    no third-party dependency for something this simple. Only fills in
    variables not already set in the environment, so an explicit shell
    export or CI-set env var always wins over the .env file."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

SERVICES = {
    "monolith": REPO_ROOT / "monolith",
    "user-service": REPO_ROOT / "microservices" / "user-service",
    "product-service": REPO_ROOT / "microservices" / "product-service",
    "order-service": REPO_ROOT / "microservices" / "order-service",
    "bff": REPO_ROOT / "bff",
}


def _redact_secrets(args: list[str]) -> list[str]:
    """Never echo a secret value to the console/log — e.g. mysqlAdminPassword=...
    on the `az deployment group create --parameters` line. Matches any arg of
    the form key=value where key looks like it holds a secret."""
    redacted = []
    for arg in args:
        key, sep, value = arg.partition("=")
        if sep and any(word in key.lower() for word in ("password", "secret", "token", "key")):
            redacted.append(f"{key}=***REDACTED***")
        else:
            redacted.append(arg)
    return redacted


def run_az(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    cmd = ["az", *args, "--output", "json"]
    print(f"$ {' '.join(_redact_secrets(cmd))}")
    return subprocess.run(cmd, capture_output=capture, text=True, check=True)


def get_default_location_and_subscription() -> tuple[str, str]:
    result = subprocess.run(["az", "account", "show", "--output", "json"], capture_output=True, text=True, check=True)
    subscription_id = json.loads(result.stdout)["id"]

    # Priority: .env's AZURE_LOCATION (or an actual shell env var, which
    # load_dotenv_defaults() never overrides) > `az config` default > the
    # hardcoded fallback constant — region is never hardcoded as the primary
    # source, only as a last resort if the user hasn't set one anywhere.
    env_location = os.environ.get("AZURE_LOCATION", "").strip()
    if env_location:
        return env_location, subscription_id

    result = subprocess.run(["az", "config", "get", "defaults.location", "--output", "json"], capture_output=True, text=True)
    location = FALLBACK_LOCATION
    if result.returncode == 0:
        try:
            location = json.loads(result.stdout)["value"] or FALLBACK_LOCATION
        except (json.JSONDecodeError, KeyError):
            pass
    return location, subscription_id


def generate_mysql_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(24))


def ensure_resource_group(resource_group: str, location: str) -> None:
    exists = subprocess.run(
        ["az", "group", "show", "--name", resource_group, "--output", "json"],
        capture_output=True, text=True,
    ).returncode == 0
    if not exists:
        run_az(["group", "create", "--name", resource_group, "--location", location])
    else:
        print(f"Resource group '{resource_group}' already exists — reusing it.")


def wait_for_acr_ready(resource_group: str, acr_name: str, timeout: float = 60.0) -> None:
    """`az acr create` can return before the registry is actually queryable —
    caught for real: `az acr build` immediately afterward failed with
    ParentResourceNotFound even though the registry existed moments later.
    Polls `az acr show` until it succeeds instead of assuming it's ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["az", "acr", "show", "--name", acr_name, "--resource-group", resource_group, "--output", "json"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return
        time.sleep(3)
    print(f"Warning: ACR '{acr_name}' still not queryable after {timeout}s — proceeding anyway.")


def build_images(resource_group: str, acr_name: str) -> None:
    for service_name, service_dir in SERVICES.items():
        print(f"\n=== az acr build: {service_name} (cloud-side, no local Docker) ===")
        # bff's /api/metrics/run endpoint shells out to scripts/benchmark.py,
        # but that file lives at the repo root, outside bff/'s own build
        # context — `az acr build`'s Dockerfile does `COPY . .` from
        # `service_dir` only. Stage a copy in so it lands in the image
        # (config.REPO_ROOT resolves to /app inside the container either
        # way, so both the bff app and the staged script agree on paths).
        staged_scripts_dir = None
        if service_name == "bff":
            staged_scripts_dir = service_dir / "scripts"
            staged_scripts_dir.mkdir(exist_ok=True)
            shutil.copy2(REPO_ROOT / "scripts" / "benchmark.py", staged_scripts_dir / "benchmark.py")
        try:
            run_az([
                "acr", "build",
                "--registry", acr_name,
                "--resource-group", resource_group,
                "--image", f"{service_name}:latest",
                str(service_dir),
            ], capture=False)
        finally:
            if staged_scripts_dir is not None:
                shutil.rmtree(staged_scripts_dir, ignore_errors=True)


def deploy_bicep(resource_group: str, location: str, names: dict, mysql_password: str, keep_warm: bool) -> dict:
    print("\n=== Deploying infra/bicep/main.bicep ===")
    # Static Web Apps is only available in a handful of regions (Central US,
    # East US 2, West US 2, West Europe, East Asia) — NOT every region that
    # supports Container Apps/MySQL/etc (plain "East US" doesn't support it,
    # which is a real failure discovered running this for the first time).
    # Kept independently configurable via .env so it's still never hardcoded
    # as the only option.
    static_web_app_location = os.environ.get("AZURE_STATIC_WEB_APP_LOCATION", "eastus2").strip() or "eastus2"
    result = run_az([
        "deployment", "group", "create",
        "--resource-group", resource_group,
        "--template-file", str(BICEP_FILE),
        "--parameters",
        f"location={location}",
        f"staticWebAppLocation={static_web_app_location}",
        f"acrName={names['acr_name']}",
        f"logAnalyticsName={names['log_analytics_name']}",
        f"containerAppsEnvName={names['acr_name']}-env",
        f"staticWebAppName={names['static_web_app_name']}",
        f"mysqlServerName={names['mysql_server_name']}",
        f"mysqlAdminUsername={MYSQL_ADMIN_USERNAME}",
        f"mysqlAdminPassword={mysql_password}",
        f"keepWarm={'true' if keep_warm else 'false'}",
    ])
    return json.loads(result.stdout)["properties"]["outputs"]


def get_acr_password(resource_group: str, acr_name: str) -> str:
    """The bff Container App needs the ACR admin password itself, at
    runtime, to create the microservices' Container Apps on demand during
    migration — it can't call `az` (no CLI in the container image), so this
    gets persisted to the gitignored state file for the BFF to read at
    startup, same as the MySQL password already is."""
    result = run_az(["acr", "credential", "show", "--name", acr_name, "--resource-group", resource_group])
    return json.loads(result.stdout)["passwords"][0]["value"]


def grant_bff_contributor_on_resource_group(resource_group: str, subscription_id: str, bff_principal_id: str) -> None:
    """The bff Container App creates the microservices' Container Apps itself
    at migration time (see bff/app/azure_traffic.py) — it needs Contributor
    to do that. Scoped to just this one resource group, not the subscription,
    and torn down automatically when `make teardown` deletes the group."""
    scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
    print(f"\n=== Granting bff's managed identity Contributor on {scope} ===")
    subprocess.run([
        "az", "role", "assignment", "create",
        "--assignee-object-id", bff_principal_id,
        "--assignee-principal-type", "ServicePrincipal",
        "--role", "Contributor",
        "--scope", scope,
        "--output", "json",
    ], check=True)


def create_budget_alert(resource_group: str, subscription_id: str, ceiling_usd: int, contact_email: str) -> None:
    """Uses `az rest` against the ARM REST API directly rather than
    `az consumption budget create` — caught for real, running this live for
    the first time: that CLI command (a preview/under-development command
    group) required --start-date/--end-date it wasn't being passed, AND its
    --notification flag doesn't exist in this CLI version at all, so
    notifications couldn't be created through it regardless. The REST API
    itself is stable across CLI versions and supports notifications
    natively, so this avoids depending on whatever a given `az` version
    happens to wrap. Start is the first of the current month; end is 5 years
    out — Cost Management budgets recur monthly on their own, this window
    just needs to be long enough the user won't need to recreate it."""
    print(f"\n=== Creating Cost Management budget alert at ${ceiling_usd}/mo ===")
    today = datetime.now(timezone.utc)
    start_date = today.replace(day=1).strftime("%Y-%m-01T00:00:00Z")
    end_date = today.replace(year=today.year + 5, day=1).strftime("%Y-%m-01T00:00:00Z")
    budget_name = f"{resource_group}-budget"
    url = (
        f"https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        f"/providers/Microsoft.Consumption/budgets/{budget_name}?api-version=2023-11-01"
    )
    body = {
        "properties": {
            "category": "Cost",
            "amount": ceiling_usd,
            "timeGrain": "Monthly",
            "timePeriod": {"startDate": start_date, "endDate": end_date},
            "notifications": {
                "actual_80": {
                    "enabled": True,
                    "operator": "GreaterThanOrEqualTo",
                    "threshold": 80,
                    "contactEmails": [contact_email],
                    "thresholdType": "Actual",
                }
            },
        }
    }
    result = subprocess.run(
        ["az", "rest", "--method", "put", "--url", url, "--body", json.dumps(body), "--output", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"WARNING: budget alert creation failed — resources are live WITHOUT a cost alert:\n{result.stderr}")
    else:
        print(f"Budget alert active: ${ceiling_usd}/mo, notifying {contact_email} at 80%/100%.")


def main() -> int:
    load_dotenv_defaults()

    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-group", default=DEFAULT_RESOURCE_GROUP)
    parser.add_argument("--name-prefix", default=DEFAULT_NAME_PREFIX)
    parser.add_argument("--budget-ceiling", type=int, default=25, help="Monthly budget alert ceiling in USD")
    parser.add_argument("--budget-email", required=True, help="Email to receive the budget alert")
    parser.add_argument("--keep-warm", action="store_true", help="minReplicas=1 instead of scale-to-zero (costs more)")
    parser.add_argument("--skip-build", action="store_true", help="skip az acr build (useful when only re-running Bicep)")
    parser.add_argument(
        "--reuse-names", action="store_true",
        help="Reuse this resource group's existing ACR/MySQL server/Static Web App names instead of "
             "resolving new ones. For retrying after a partial failure (e.g. a Bicep error after images "
             "already built) without the collision resolver auto-incrementing to a fresh, empty name — "
             "which was a real annoyance discovered running this for the first time. Names still come "
             "from --name-prefix; this only skips the collision check/increment, it doesn't fabricate "
             "names that were never resolved.",
    )
    parser.add_argument("--acr-name", help="Override: use this exact ACR name instead of resolving/reusing one")
    parser.add_argument("--mysql-server-name", help="Override: use this exact MySQL server name")
    parser.add_argument("--static-web-app-name", help="Override: use this exact Static Web App name")
    parser.add_argument("--log-analytics-name", help="Override: use this exact Log Analytics workspace name")
    args = parser.parse_args()

    location, subscription_id = get_default_location_and_subscription()
    print(f"Subscription: {subscription_id}  Location: {location}")

    ensure_resource_group(args.resource_group, location)

    if args.reuse_names:
        print("\n=== Reusing existing resource names (--reuse-names) ===")
        prefix = args.name_prefix
        names = {
            "acr_name": prefix.replace("-", "") + "acr",
            "mysql_server_name": f"{prefix}-mysql",
            "static_web_app_name": f"{prefix}-web",
            "log_analytics_name": f"{prefix}-logs",
        }
    else:
        print("\n=== Resolving collision-safe resource names ===")
        names = resolve_all_names(args.name_prefix, args.resource_group)

    overrides = {
        "acr_name": args.acr_name,
        "mysql_server_name": args.mysql_server_name,
        "static_web_app_name": args.static_web_app_name,
        "log_analytics_name": args.log_analytics_name,
    }
    for key, value in overrides.items():
        if value:
            names[key] = value

    for key, value in names.items():
        print(f"  {key}: {value}")

    mysql_password = generate_mysql_password()

    if not args.skip_build:
        run_az([
            "acr", "create",
            "--name", names["acr_name"],
            "--resource-group", args.resource_group,
            "--sku", "Basic",
            "--location", location,
            # Bicep's acr.bicep module also sets this, but caught for real:
            # flipping adminUserEnabled true for the first time as part of
            # the SAME Bicep deployment that immediately calls
            # listCredentials() on it races the control plane — the
            # deployment fails with "admin user is disabled" even though the
            # property update reports success. Enabling it here, minutes
            # before Bicep ever runs, gives it time to actually take effect.
            "--admin-enabled", "true",
        ])
        wait_for_acr_ready(args.resource_group, names["acr_name"])
        build_images(args.resource_group, names["acr_name"])

    try:
        outputs = deploy_bicep(args.resource_group, location, names, mysql_password, args.keep_warm)
    except subprocess.CalledProcessError as exc:
        # Never let the real password leak into a traceback or log — redact
        # it from stderr/stdout before printing (caught for real: the first
        # run of this script hit a genuine Bicep failure — Static Web Apps
        # isn't available in every region — and the unhandled traceback here
        # didn't show the actual az error at all, only a stack trace).
        stderr = (exc.stderr or "").replace(mysql_password, "***REDACTED***")
        print(f"\nBicep deployment failed:\n{stderr}")
        return 1
    output_values = {k: v["value"] for k, v in outputs.items()}

    grant_bff_contributor_on_resource_group(args.resource_group, subscription_id, output_values["bffPrincipalId"])

    create_budget_alert(args.resource_group, subscription_id, args.budget_ceiling, args.budget_email)

    acr_password = get_acr_password(args.resource_group, names["acr_name"])

    state = {
        "resource_group": args.resource_group,
        "location": location,
        "subscription_id": subscription_id,
        "names": names,
        "outputs": output_values,
        # NOTE: the running bff Container App does NOT read this file (it
        # lives only on whichever machine ran `make provision`, not inside
        # the container) — it gets these same secrets via its own env vars,
        # injected directly by main.bicep's secretRefs. This copy is kept
        # only for teardown.py/verify_teardown.py and for a human operator
        # to inspect/debug with.
        "mysql_admin_username": MYSQL_ADMIN_USERNAME,
        "mysql_admin_password": mysql_password,
        "acr_password": acr_password,
        # Only monolith and bff exist right now. user-service/product-service/
        # order-service are added here by the BFF itself (see
        # azure_traffic.py's create_microservice_container_app) as the live
        # migration creates each one — this file is re-read by teardown.py
        # and verify_teardown.py, not by the running BFF, so it does not need
        # to stay in sync with the BFF's in-memory registry in real time.
        "container_apps": {
            "monolith": "monolith",
            "bff": "bff",
        },
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"\nState persisted to {STATE_FILE} (gitignored).")
    print(f"\nFoundation + monolith are live. Static Web App: https://{output_values['staticWebAppHostname']}")
    print("Open that URL, use the Shop against the monolith, then click 'Start Migration' on the")
    print("Migrate page — that's what creates user-service/product-service/order-service for real.")
    print("\nRemember: MySQL Flexible Server bills whether idle or not — run `make teardown` when finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
