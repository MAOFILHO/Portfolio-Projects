"""Naming-collision detection & auto-increment for Azure resources.

Some Azure resources are not immediately reusable after teardown even
though the delete command reports success (soft-delete, globally-unique
names). This module checks both active AND soft-deleted state before
provision.py hands a name to Bicep, and auto-increments a numeric suffix on
collision rather than failing the whole provision step. It never force-purges
a soft-deleted resource — auto-increment is always the safe default.
"""
import json
import subprocess

MAX_ATTEMPTS = 20


def _run_az(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(["az", *args, "--output", "json"], capture_output=True, text=True)
    return result.returncode, result.stdout


def _candidate_names(base: str, alphanumeric_only: bool = False):
    """alphanumeric_only=True for resource types (e.g. ACR) whose naming rules
    reject hyphens — an incremented suffix must still be a legal name for that
    resource type, or the collision check will reject every candidate as
    'Invalid' rather than 'Taken' and the resolver will wrongly exhaust all
    attempts (this was caught by the real-Azure verification test)."""
    yield base
    separator = "" if alphanumeric_only else "-"
    for i in range(2, MAX_ATTEMPTS + 1):
        yield f"{base}{separator}{i}"
    raise RuntimeError(f"Exhausted {MAX_ATTEMPTS} naming attempts for base '{base}'")


def acr_name_available(name: str) -> bool:
    """ACR names are globally unique across all of Azure."""
    code, out = _run_az(["acr", "check-name", "--name", name])
    if code != 0:
        return False
    return json.loads(out).get("nameAvailable", False)


def mysql_server_name_taken(name: str, resource_group: str) -> bool:
    """Checks both an active server AND a soft-deleted one with the same name
    in this resource group/region — MySQL Flexible Server names can be
    reserved by a soft-deleted server for a retention window."""
    code, _ = _run_az(["mysql", "flexible-server", "show", "--name", name, "--resource-group", resource_group])
    if code == 0:
        return True  # active server exists

    code, out = _run_az(["mysql", "flexible-server", "list", "--resource-group", resource_group])
    if code == 0:
        for server in json.loads(out):
            if server.get("name") == name and server.get("state", "").lower() in ("dropping", "disabled"):
                return True
    return False


def static_web_app_name_taken(name: str, resource_group: str) -> bool:
    code, _ = _run_az(["staticwebapp", "show", "--name", name, "--resource-group", resource_group])
    return code == 0


def log_analytics_workspace_soft_deleted(name: str, resource_group: str) -> bool:
    """Log Analytics Workspace names can be reserved by a soft-deleted
    workspace for up to 14 days — a real re-provision failure mode after
    `make teardown` followed by `make provision` within that window, since
    this project's own workspace from a prior run is exactly the kind of
    'stale resource' that blocks the name."""
    code, out = _run_az(["monitor", "log-analytics", "workspace", "list-deleted-workspaces", "--resource-group", resource_group])
    if code != 0:
        return False
    try:
        workspaces = json.loads(out)
    except json.JSONDecodeError:
        return False
    return any(w.get("name") == name for w in workspaces)


def recover_log_analytics_workspace(name: str, resource_group: str) -> bool:
    """Un-deletes a soft-deleted workspace in place — this is the only
    automated mechanism `az` exposes for this resource type (there is no
    'purge' subcommand), and it's strictly better than purging anyway: no
    data loss, and the original name becomes usable again immediately, so a
    redeploy never needs to fall back to an incremented name at all."""
    code, _ = _run_az(["monitor", "log-analytics", "workspace", "recover", "--workspace-name", name, "--resource-group", resource_group])
    return code == 0


def resolve_log_analytics_name(base: str, resource_group: str) -> str:
    """Recovers a soft-deleted workspace under `base` if one exists (so the
    original name is reused, not abandoned), otherwise falls back to the
    normal increment-on-collision scheme for a workspace that's actively in
    use by something else."""
    if log_analytics_workspace_soft_deleted(base, resource_group):
        if recover_log_analytics_workspace(base, resource_group):
            return base
    return resolve_name(base, lambda n: _log_analytics_active(n, resource_group))


def _log_analytics_active(name: str, resource_group: str) -> bool:
    code, _ = _run_az(["monitor", "log-analytics", "workspace", "show", "--workspace-name", name, "--resource-group", resource_group])
    return code == 0


def resolve_name(base: str, checker, alphanumeric_only: bool = False) -> str:
    """checker(candidate) -> True if taken/unavailable. Returns the first free name."""
    for candidate in _candidate_names(base, alphanumeric_only=alphanumeric_only):
        if not checker(candidate):
            return candidate
    raise RuntimeError(f"Could not resolve a free name for base '{base}'")


def resolve_all_names(base_prefix: str, resource_group: str) -> dict:
    """Resolves every globally-unique / soft-deletable resource name up front,
    auto-incrementing independently per resource type on collision."""
    resolved = {
        "acr_name": resolve_name(
            base_prefix.replace("-", "") + "acr",
            lambda n: not acr_name_available(n),
            alphanumeric_only=True,  # ACR names: alphanumeric only, no hyphens
        ),
        "mysql_server_name": resolve_name(
            f"{base_prefix}-mysql", lambda n: mysql_server_name_taken(n, resource_group)
        ),
        "static_web_app_name": resolve_name(
            f"{base_prefix}-web", lambda n: static_web_app_name_taken(n, resource_group)
        ),
        "log_analytics_name": resolve_log_analytics_name(f"{base_prefix}-logs", resource_group),
    }
    return resolved
