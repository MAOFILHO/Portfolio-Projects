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
SUCCESSOR_REALTIME_MODEL = ("gpt-realtime-1-5", "2026-02-23")  # GA, retires 2027-08-24

ALLOWED_REALTIME_MODELS = frozenset({ACTIVE_REALTIME_MODEL, SUCCESSOR_REALTIME_MODEL})

# The ambient key the OpenAI SDK picks up on its own. This project authenticates to the data plane
# with AOAI_KEY today and moves to managed identity in Phase 7; this check is specifically about
# *this* variable, whose presence would let the SDK silently authenticate as something other than
# what this project configured. It is not a check on AOAI_KEY, which is legitimately set today.
AMBIENT_SDK_KEY_VAR = "AZURE_OPENAI_API_KEY"

_ARM_API_VERSION = "2023-05-01"


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

    try:
        live = reader(deployment_name)
    except Exception as e:
        # Fails closed: an unreadable deployment is an unapproved deployment. Never "assume the
        # config was right and carry on" -- that is exactly the trust this guard exists to remove.
        raise SystemExit(
            f"B3: could not read the live model for deployment {deployment_name!r} ({e}). "
            "Refusing to start: an unverifiable deployment is treated as an unapproved one."
        )

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
