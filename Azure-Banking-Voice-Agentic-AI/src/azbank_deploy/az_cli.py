"""Thin wrapper around `az`. One function per real operation this CLI needs -- no retry framework,
no generic "run any az command" helper: each function names exactly what it does, so a reader (or
D5's static check) can see every place this tool can touch Azure without following string concatenation.

Every deployment call is `--mode Incremental`, hardcoded, never a parameter -- D1 (docs/phase7/
exit-criteria.md) and D5's own static check both treat `Complete` mode as forbidden outright, not
something this module should make easy to pass in by accident.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

INFRA_ROOT = Path(__file__).resolve().parents[2] / "infra" / "modules"


class AzCommandError(RuntimeError):
    """An `az` invocation exited non-zero. Carries the full stderr so the caller can decide whether
    it's fatal (most cases) or a known, tolerated partial failure (none, currently -- every deploy
    step here either fully succeeds or is treated as a hard stop)."""

    def __init__(self, args: list[str], returncode: int, stderr: str):
        # Not `self.args` -- that name collides with BaseException's own `args` tuple.
        self.command = args
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"`{' '.join(args)}` exited {returncode}: {stderr.strip()}")


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["az", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AzCommandError(args, result.returncode, result.stderr)
    return result


def _run_json(args: list[str]):
    result = _run([*args, "-o", "json"])
    return json.loads(result.stdout) if result.stdout.strip() else None


# ---------------------------------------------------------------------------
# Bicep deployment -- every module this CLI manages goes through this one
# function, so `--mode Incremental` is enforced in exactly one place.
# ---------------------------------------------------------------------------

def deploy_bicep(resource_group: str, module: str, deployment_name: str, parameters: dict[str, str]) -> dict:
    """Deploys `infra/modules/<module>.bicep` in Incremental mode. `parameters` values are passed as
    `key=value` -- fine for every param this project's modules take (strings, including secrets;
    none of them are objects or arrays)."""
    template_file = INFRA_ROOT / f"{module}.bicep"
    param_args = [f"{k}={v}" for k, v in parameters.items()]
    args = [
        "deployment", "group", "create",
        "--resource-group", resource_group,
        "--name", deployment_name,
        "--mode", "Incremental",
        "--template-file", str(template_file),
    ]
    if param_args:
        args += ["--parameters", *param_args]
    return _run_json(args)


# ---------------------------------------------------------------------------
# call_records_account bootstrap -- the one documented workaround for the
# circular dependency resources.py's module docstring explains. Properties
# match infra/modules/call-records-store.bicep's own `account` resource
# exactly, so the later real Bicep deploy sees a matching resource and is a
# clean no-op on it.
# ---------------------------------------------------------------------------

def storage_account_exists(resource_group: str, name: str) -> bool:
    result = _run(["storage", "account", "show", "-g", resource_group, "-n", name], check=False)
    return result.returncode == 0


def create_call_records_account_bootstrap(resource_group: str, name: str, location: str) -> None:
    if storage_account_exists(resource_group, name):
        return
    _run([
        "storage", "account", "create",
        "--resource-group", resource_group,
        "--name", name,
        "--location", location,
        "--sku", "Standard_LRS",
        "--kind", "StorageV2",
        "--min-tls-version", "TLS1_2",
        "--https-only", "true",
        "--allow-blob-public-access", "false",
        "--allow-shared-key-access", "false",
        "--public-network-access", "Enabled",
    ])


# ---------------------------------------------------------------------------
# Reads used to wire one module's output into the next module's input.
# ---------------------------------------------------------------------------

def container_app_env_default_domain(resource_group: str, name: str) -> str:
    return _run_json(["containerapp", "env", "show", "-g", resource_group, "-n", name])["properties"]["defaultDomain"]


def predicted_app_fqdn(app_name: str, default_domain: str) -> str:
    """Container Apps FQDNs are deterministic once the environment exists -- `<app-name>.<default
    domain>` -- so ACS's webhook URL and the voice agent's own `appBaseUrl` can both be computed
    before the voice agent itself is deployed. See resources.py's module docstring."""
    return f"{app_name}.{default_domain}"


def communication_connection_string(resource_group: str, name: str) -> str:
    return _run_json(["communication", "list-key", "-g", resource_group, "-n", name])["primaryConnectionString"]


def container_app_principal_id(resource_group: str, name: str) -> str:
    return _run_json(["containerapp", "show", "-g", resource_group, "-n", name])["identity"]["principalId"]


def app_insights_connection_string(resource_group: str, name: str) -> str:
    args = ["monitor", "app-insights", "component", "show", "-g", resource_group, "--app", name]
    return _run_json(args)["connectionString"]


# ---------------------------------------------------------------------------
# Live existence checks -- resume discipline (CLAUDE.md): `deployment_state.json`
# is a convenience checkpoint, not the truth. `resume_state()` in state.py calls
# these before trusting the checkpoint, so a resource deleted outside this CLI
# (by hand, or by someone else's script) doesn't get silently skipped.
# ---------------------------------------------------------------------------

def app_insights_exists(resource_group: str, name: str) -> bool:
    args = ["monitor", "app-insights", "component", "show", "-g", resource_group, "--app", name]
    return _run(args, check=False).returncode == 0


def container_app_env_exists(resource_group: str, name: str) -> bool:
    return _run(["containerapp", "env", "show", "-g", resource_group, "-n", name], check=False).returncode == 0


def container_app_exists(resource_group: str, name: str) -> bool:
    return _run(["containerapp", "show", "-g", resource_group, "-n", name], check=False).returncode == 0


def acs_exists(resource_group: str, name: str) -> bool:
    return _run(["communication", "show", "-g", resource_group, "-n", name], check=False).returncode == 0


def cognitive_services_account_exists(resource_group: str, name: str) -> bool:
    return _run(["cognitiveservices", "account", "show", "-g", resource_group, "-n", name], check=False).returncode == 0


def call_records_rbac_present(resource_group: str, account_name: str) -> bool:
    """True once the table (not just the account) exists -- the signal that the *full*
    call-records-store.bicep deploy has actually run, not just the bootstrap step."""
    result = _run([
        "storage", "table", "exists",
        "--account-name", account_name, "--name", "callrecords",
        "--auth-mode", "login",
    ], check=False)
    if result.returncode != 0:
        return False
    return json.loads(result.stdout).get("exists", False)


# ---------------------------------------------------------------------------
# Teardown -- imperative deletes, never a smaller Bicep template. D1 forbids
# Complete mode, so "redeploy without this resource" was never an option;
# every teardown target here is deleted by name, directly.
# ---------------------------------------------------------------------------

def delete_container_app(resource_group: str, name: str) -> None:
    _run(["containerapp", "delete", "-g", resource_group, "-n", name, "--yes"])


def delete_container_app_env(resource_group: str, name: str) -> None:
    _run(["containerapp", "env", "delete", "-g", resource_group, "-n", name, "--yes"])


def delete_storage_account(resource_group: str, name: str) -> None:
    _run(["storage", "account", "delete", "-g", resource_group, "-n", name, "--yes"])


def delete_app_insights(resource_group: str, name: str) -> None:
    _run(["monitor", "app-insights", "component", "delete", "-g", resource_group, "--app", name])


def delete_cognitive_services_account(resource_group: str, name: str) -> None:
    _run(["cognitiveservices", "account", "delete", "-g", resource_group, "-n", name])


# ---------------------------------------------------------------------------
# Soft-delete cleanup -- Marco, 2026-09-18: a deleted Cognitive Services
# (AOAI) account is only soft-deleted; a name collision on the next deploy
# is a real, well-documented Azure failure mode, not a hypothetical one.
# Nothing else this CLI manages has an equivalent purge step (Storage
# accounts and Container Apps don't soft-delete; Key Vault would, but this
# project has none, by design -- docs/PLAN.md decision 3/D2).
# ---------------------------------------------------------------------------

def list_soft_deleted_cognitive_services_accounts(location: str) -> list[dict]:
    return _run_json(["cognitiveservices", "account", "list-deleted"]) or []


def purge_cognitive_services_account(resource_group: str, name: str, location: str) -> None:
    _run(["cognitiveservices", "account", "purge", "-g", resource_group, "-n", name, "-l", location])
