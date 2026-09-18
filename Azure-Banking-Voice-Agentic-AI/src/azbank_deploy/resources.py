"""The resource dependency graph and its legality rules -- pure, no `az` calls, no I/O.

Validated as a prototype first (`infra/PROTOTYPE-deploy-teardown-ordering.html`, throwaway branch
`throwaway/phase7-deploy-teardown-prototype`): Marco confirmed 2026-09-18 that an auto-computed legal
order is what `deploy`/`teardown` should do, not something left to whoever runs the command.

**Two real circular-looking dependencies found tracing the actual Bicep modules, not assumed from the
prototype's simplified shape:**

  * `call-records-store.bicep` bundles the storage account with a role assignment that needs the
    voice agent's identity, in one file with one required param -- so that file cannot be deployed at
    all until the voice agent exists. But `voice-agent.bicep` does an `existing`-resource lookup on
    that same storage account (for its table endpoint), which fails at deploy time if the account
    isn't there yet. Real deadlock, not resolved by clever ordering alone.
  * `acs.bicep` needs the voice agent's future public URL (`voiceAgentWebhookUrl`) as a required
    param -- but `voice-agent.bicep` needs ACS's connection string, which only exists once ACS is
    deployed.

The ACS case resolves for free: Container Apps FQDNs are deterministic (`<app-name>.<environment's
default domain>`), so the CLI computes the voice agent's future URL from the environment alone and
never needs the app to exist first -- no graph change needed, see `az_cli.predicted_app_fqdn()`.

The call-records case does not resolve for free, because the constraint lives inside
`voice-agent.bicep`'s own body (an `existing` lookup), not in a param the CLI controls. Splitting
`call-records-store.bicep` into an account-only module and a role-assignment-only module would fix
this cleanly -- deferred (Marco, 2026-09-18, Option B) in favour of shipping the CLI now with a
documented workaround: **`call_records_account` is a graph node of its own**, created by a plain `az
storage account create` (bypassing this Bicep file for just the account), matching the account
properties `call-records-store.bicep` itself declares. The voice agent depends on that node, not on
the full Bicep-managed resource. `call_records_rbac` is the *real* `call-records-store.bicep` deploy
(account properties are then a no-op under `Incremental` mode; the table and role assignment are
new), depending on both `call_records_account` and `voice_agent`. One workaround, not the two the
naive per-resource reading would suggest -- fix the actual Bicep split later, tracked as Phase 7 debt.

`acs` deploys like every other resource but is **never a teardown target** (D5, R-09): the ACS
resource is what the phone number hangs off, and nothing about "zero billable spend" is worth the
risk of a script that can delete it. `TEARDOWN_ORDER` excludes it by construction, not by a runtime
check anyone could accidentally skip.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Resource:
    key: str
    label: str
    deps: frozenset[str] = field(default_factory=frozenset)
    teardown_eligible: bool = True


RESOURCES: dict[str, Resource] = {
    r.key: r
    for r in (
        Resource("app_insights", "Application Insights"),
        Resource("container_apps_env", "Container Apps environment"),
        Resource("call_records_account", "Call-records storage account (bootstrap)"),
        Resource(
            "mock_core_banking", "Mock core-banking Container App",
            deps=frozenset({"container_apps_env"}),
        ),
        Resource(
            "acs", "ACS resource + Event Grid wiring",
            deps=frozenset({"container_apps_env"}), teardown_eligible=False,
        ),
        Resource(
            "voice_agent",
            "Voice-agent Container App",
            deps=frozenset({"container_apps_env", "call_records_account", "acs", "app_insights"}),
        ),
        Resource(
            "call_records_rbac", "Call-records table + RBAC grant",
            deps=frozenset({"call_records_account", "voice_agent"}),
        ),
        Resource(
            "aoai", "AOAI account + realtime deployment + RBAC grant",
            deps=frozenset({"voice_agent"}),
        ),
    )
}

ORDER = tuple(RESOURCES.keys())  # insertion order; deterministic iteration for the algorithms below


def initial_state(overrides: dict[str, str] | None = None) -> dict[str, str]:
    overrides = overrides or {}
    return {key: overrides.get(key, "absent") for key in ORDER}


def can_deploy(state: dict[str, str], key: str) -> tuple[bool, str | None]:
    if state[key] == "deployed":
        return False, f"{RESOURCES[key].label} is already deployed."
    missing = [d for d in RESOURCES[key].deps if state[d] != "deployed"]
    if missing:
        names = ", ".join(RESOURCES[d].label for d in missing)
        return False, f"needs {names} deployed first."
    return True, None


def can_teardown(state: dict[str, str], key: str) -> tuple[bool, str | None]:
    if not RESOURCES[key].teardown_eligible:
        return False, f"{RESOURCES[key].label} is never a teardown target (D5)."
    if state[key] == "absent":
        return False, f"{RESOURCES[key].label} is already absent."
    # A dependent that is itself never a teardown target (acs) never actually blocks this --
    # its dependency on `key` was a deploy-time *value* dependency (acs.bicep needs
    # container_apps_env's default domain to compute its webhook URL), not a live Azure
    # containment relationship. Counting it here would make container_apps_env permanently
    # un-teardownable, since acs can never go absent to satisfy it -- found by
    # tests/test_azbank_deploy_resources.py's TeardownToZero suite, not assumed correct.
    dependents = [
        other for other in ORDER
        if state[other] == "deployed"
        and key in RESOURCES[other].deps
        and RESOURCES[other].teardown_eligible
    ]
    if dependents:
        names = ", ".join(RESOURCES[d].label for d in dependents)
        plural = "s" if len(dependents) == 1 else ""
        return False, f"{names} still depend{plural} on this -- tear that down first."
    return True, None


def legal_deploy_order(state: dict[str, str]) -> list[str]:
    """Every resource this state can still deploy, in a dependency-respecting order. Deterministic:
    scans `ORDER` repeatedly, taking whatever is newly legal, until nothing more can move."""
    s = dict(state)
    steps: list[str] = []
    progressed = True
    while progressed:
        progressed = False
        for key in ORDER:
            if s[key] == "absent" and can_deploy(s, key)[0]:
                s[key] = "deployed"
                steps.append(key)
                progressed = True
    return steps


def legal_teardown_order(state: dict[str, str]) -> list[str]:
    """Every eligible resource this state can still tear down, in reverse-dependency order. ACS is
    never included -- `can_teardown` refuses it unconditionally, so it never becomes legal."""
    s = dict(state)
    steps: list[str] = []
    progressed = True
    while progressed:
        progressed = False
        for key in reversed(ORDER):
            if s[key] == "deployed" and can_teardown(s, key)[0]:
                s[key] = "absent"
                steps.append(key)
                progressed = True
    return steps
