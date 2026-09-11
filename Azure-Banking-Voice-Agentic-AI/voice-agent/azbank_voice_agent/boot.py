"""B3 — the startup guard. Refuses to boot on a model this project has not approved.

Keyed on **(model name, model version) together, never name alone.** That is a hard requirement,
promoted from a design note after Phase 0's own evidence undermined a name-only check (R-01,
docs/phase0/findings.md "Model pin reconsideration"): `gpt-realtime-mini` already has more than one
live version, with *different retirement dates and different rate limits*. A name-only allowlist
would wave through a same-name deployment silently moved onto a different version.

The version is **read from the live deployment at boot, never from configuration.** Configuration
describing what ought to be deployed is not evidence of what is deployed -- Phase 0 watched exactly
that gap open up live, when a deployment created with `NoAutoUpgrade` came back reporting
`OnceNewDefaultVersionAvailable` at create time (docs/phase0/findings.md, Stage 7).

Fails closed. An unreadable deployment is treated as an unapproved one: if this guard cannot prove
what is deployed, the application does not start.
"""
import json
import logging
import os

log = logging.getLogger("boot")

# Reviewed at every phase gate (CLAUDE.md, "Model pin review"). Each entry's retirement date was
# verified live via the Models API (docs/phase0/findings.md, "Model pin reconsideration") -- never
# assumed from isDefaultVersion, which is precisely the assumption R-01 caught being wrong.

# The pin actually in service. Only this exact (name, version) pair runs without a warning.
ACTIVE_REALTIME_MODEL = ("gpt-realtime-mini", "2025-10-06")  # GA, retires 2027-04-06

# Pre-vetted fallback, not live today. Named here so that migrating, when it is needed, is a
# one-line change plus a deployment change -- not a from-scratch model evaluation run under
# deadline pressure as the active pin's retirement approaches. Full tier, ~3.2x the per-token
# audio cost; that is the tier difference, not the version.
# **A dot, not a hyphen.** This is a *model* name, because that is what the guard compares it
# against: `parse_deployment_response` reads `properties.model.name`. The hyphen form this entry
# carried until 2026-09-11 traced to docs/phase0/findings.md:361, which described *deployment*
# names -- a different namespace, freely chosen at deployment time. The live Models API spells the
# model `gpt-realtime-1.5`, so the old entry could never match anything Azure would report, and
# booting the pre-vetted successor would have been refused at startup by the very allowlist that
# exists to let it boot. Found by /code-review 2026-09-11; see test_boot.py's
# `test_the_guard_admits_the_successor_spelled_the_way_the_catalog_spells_it`, which pins the
# catalog spelling as a literal rather than reading it back out of this constant.
SUCCESSOR_REALTIME_MODEL = ("gpt-realtime-1.5", "2026-02-23")  # GA, retires 2027-08-24

ALLOWED_REALTIME_MODELS = frozenset({ACTIVE_REALTIME_MODEL, SUCCESSOR_REALTIME_MODEL})

# The ambient key the OpenAI SDK picks up on its own. This project authenticates to the data plane
# with AOAI_KEY today and moves to managed identity in Phase 7; this check is specifically about
# *this* variable, whose presence would let the SDK silently authenticate as something other than
# what this project configured. It is not a check on AOAI_KEY, which is legitimately set today.
AMBIENT_SDK_KEY_VAR = "AZURE_OPENAI_API_KEY"

#: The public base URL this app answers on, which its own ACS callback and media URLs are built
#: from. No default, ever -- see app_base_url() below.
APP_BASE_URL_VAR = "APP_BASE_URL"

#: Where mock-core-banking lives. No default, ever -- see core_banking_url() below.
CORE_BANKING_URL_VAR = "CORE_BANKING_URL"

#: The Table Storage endpoint the call-record store writes to (issue #48). An **account URL, never a
#: connection string** -- the difference is the whole no-keys stance: a connection string carries an
#: account key, and this project authenticates with the Container App's managed identity instead.
#: No default either, for the reason below.
CALL_RECORDS_ACCOUNT_URL_VAR = "CALL_RECORDS_ACCOUNT_URL"

_ARM_API_VERSION = "2023-05-01"


def core_banking_url(env=None):
    """The configured mock-core-banking address, or a refusal to start (issue #29).

    No default. A misconfigured deployment should die at startup, where a health check catches it
    and the revision never takes traffic -- not mid-call, in front of a caller, on the first tool
    call of the day. Same fail-closed reasoning as the model pin above and as the realtime client's
    own configuration: this project does not guess at values it was not given.
    """
    env = os.environ if env is None else env
    url = env.get(CORE_BANKING_URL_VAR)
    if not url:
        raise SystemExit(
            f"{CORE_BANKING_URL_VAR} is not set -- refusing to start without an address for "
            "mock-core-banking. There is no default: an unconfigured backend must fail at boot, "
            "not on the first tool call."
        )
    return url


def app_base_url(env=None):
    """Where this app answers its own callbacks and media, or a refusal to start.

    Same no-default rule as the two addresses below, and it is here rather than in `app.py`
    because that is what makes it a *startup* failure. It used to be one by accident: `app.py` read
    it at module scope, so a missing value killed the import. Moving that read to call time
    (2026-09-11) removed an import-time side effect and, unnoticed, turned the failure into a
    `KeyError` inside the incoming-call webhook -- past a `/healthz` that answers `ok`
    unconditionally, on a revision already taking traffic, in front of a caller. Exactly what
    `core_banking_url` above refuses to allow, undone by a change meant to tidy imports
    (/code-review, 2026-09-11).
    """
    env = os.environ if env is None else env
    url = env.get(APP_BASE_URL_VAR)
    if not url:
        raise SystemExit(
            f"{APP_BASE_URL_VAR} is not set -- refusing to start without the address this app "
            "answers its own callbacks and media on. There is no default: a revision that cannot "
            "name itself must fail at boot, not on the first incoming call."
        )
    return url


def call_records_account_url(env=None):
    """The configured Table Storage endpoint, or a refusal to start (issue #48).

    Same fail-closed rule `core_banking_url` states and for the same reason: a misconfigured
    deployment should die at startup, where a health check catches it and the revision never takes
    traffic. There is an extra reason here. B4's daily cap (issue #49) reads this store before a call
    is answered and takes the closed path when it cannot; a store that was never configured would
    make every call take the closed path, which is fail-closed working exactly as specified and
    indistinguishable, from the caller's side, from an outage. Better to not start.

    **Refuses a connection string outright.** Somebody pasting one here would get working software
    with the no-keys property silently gone, and that is the kind of regression nobody notices until
    a key leaks. A connection string is recognisable: it is `Key=Value;` pairs, never a URL.
    """
    env = os.environ if env is None else env
    url = env.get(CALL_RECORDS_ACCOUNT_URL_VAR)
    if not url:
        raise SystemExit(
            f"{CALL_RECORDS_ACCOUNT_URL_VAR} is not set -- refusing to start without an address for "
            "the call-record store. There is no default: an unconfigured store would make every "
            "call take B4's closed path, which is indistinguishable from an outage."
        )
    if not url.startswith(("http://", "https://")):
        raise SystemExit(
            f"{CALL_RECORDS_ACCOUNT_URL_VAR} must be an account URL, not a connection string. This "
            "project authenticates to Storage with a managed identity and holds no account key."
        )
    return url


def parse_deployment_response(payload):
    """Pulls (modelName, modelVersion) out of an ARM deployment response.

    Split from the HTTP call so the shape-handling is testable without a network. The shape is the
    one recorded live in docs/phase0/findings.md, "B3 end-to-end check" -- properties.model.name /
    .version, with deploymentName alongside.
    """
    model = payload.get("properties", {}).get("model", {})
    name, version = model.get("name"), model.get("version")
    if not name or not version:
        raise ValueError(f"deployment response carried no model name/version: {json.dumps(payload)[:200]}")
    return (name, version)


def read_live_model(deployment_name):
    """Reads the live deployment's actual model name and version from ARM.

    Default reader only -- every branch of assert_boot_safety is tested with this injected, so the
    guard's logic never depends on the network. Uses managed identity via DefaultAzureCredential,
    consistent with the no-keys direction (docs/PLAN.md Phase 7).

    UNVERIFIED against live Azure: this project has made no live call on this path. The parsing it
    depends on is covered by tests against the recorded response shape; the HTTP and auth legs are
    not. Verify on the next container start before relying on it.
    """
    import httpx
    from azure.identity import DefaultAzureCredential

    subscription = os.environ["AZURE_SUBSCRIPTION_ID"]
    resource_group = os.environ["AZURE_RESOURCE_GROUP"]
    account = os.environ["AOAI_ACCOUNT_NAME"]
    token = DefaultAzureCredential().get_token("https://management.azure.com/.default").token
    url = (
        f"https://management.azure.com/subscriptions/{subscription}"
        f"/resourceGroups/{resource_group}"
        f"/providers/Microsoft.CognitiveServices/accounts/{account}"
        f"/deployments/{deployment_name}?api-version={_ARM_API_VERSION}"
    )
    response = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
    response.raise_for_status()
    return parse_deployment_response(response.json())


def assert_boot_safety(reader=read_live_model, env=None):
    """Refuses to start unless the live deployment is an approved (name, version) pair.

    Raises SystemExit on any refusal -- there is no return value meaning "unsafe", because there is
    no path that continues past one.
    """
    env = os.environ if env is None else env

    if AMBIENT_SDK_KEY_VAR in env:
        raise SystemExit(
            f"B3: {AMBIENT_SDK_KEY_VAR} is set. The SDK would pick it up ambiently and could "
            "authenticate as something this project did not configure. Unset it."
        )

    deployment_name = env.get("AOAI_DEPLOYMENT")
    if not deployment_name:
        # Same fail-closed reasoning as the client's own missing-pin behaviour: no default, ever.
        raise SystemExit("B3: AOAI_DEPLOYMENT is not set -- refusing to start without a named pin.")

    # Checked here as well as read in app.py, so that "the app started" means "every piece of
    # configuration it needs was present", rather than deferring the discovery to the first tool
    # call. After the B3 checks above and before the network read below: B3 is the named
    # constraint and keeps first claim on the failure message, and neither check should be paid
    # for over the network when a local one can refuse first.
    core_banking_url(env)

    try:
        live = reader(deployment_name)
    except Exception as e:
        # Fails closed: an unreadable deployment is an unapproved deployment. Never "assume the
        # config was right and carry on" -- that is exactly the trust this guard exists to remove.
        #
        # The blind catch is the point, not an oversight: this must refuse on *any* failure to
        # prove what is deployed -- an auth error, a DNS failure, a schema change, a timeout, a
        # library raising something undocumented. Enumerating exception types here would mean
        # every unenumerated one boots the app on an unverified model, which is fail-open.
        raise SystemExit(
            f"B3: could not read the live model for deployment {deployment_name!r} ({e}). "
            "Refusing to start: an unverifiable deployment is treated as an unapproved one."
        ) from e

    if live not in ALLOWED_REALTIME_MODELS:
        raise SystemExit(
            f"B3: deployed model {live!r} is not in the allowlist {sorted(ALLOWED_REALTIME_MODELS)!r}. "
            f"Refusing to start."
        )

    if live != ACTIVE_REALTIME_MODEL:
        # Booting on the successor is allowed, so a migration can be rehearsed -- but it must never
        # be silent. This is the "scheduled decision, not a surprise" requirement, mechanically
        # enforced rather than left to whoever reads the release notes.
        log.warning(
            "B3: booting on %r, not the active pin %r -- confirm this is a deliberate migration.",
            live, ACTIVE_REALTIME_MODEL,
        )
    else:
        log.info("B3: deployed model %r matches the active pin.", live)

    return live


if __name__ == "__main__":
    # Verify the one leg the test suite cannot: the real reader's HTTP and auth path against live
    # Azure. Read-only, free, and runnable locally under `az login` -- so the guard can be proven
    # before a deploy depends on it, rather than discovered at container start.
    #
    #   AZURE_SUBSCRIPTION_ID=... AZURE_RESOURCE_GROUP=... AOAI_ACCOUNT_NAME=... \
    #   AOAI_DEPLOYMENT=gpt-realtime-mini python -m azbank_voice_agent.boot
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = assert_boot_safety()
    print(f"B3 OK -- live deployed model is {result!r}")
