"""Connecting to the live Azure OpenAI realtime deployment.

Split out of the relay by issue #18 so that `run_call` takes an already-connected realtime
connection rather than building one from the environment. That is what makes a whole call
testable against a fake with no patching: the relay no longer reaches for the network itself,
it is handed something that satisfies `RealtimeConnection`.

GA endpoint shape, confirmed live in Phase 1 (docs/phase1/research-aoai-realtime-wire-format.md):
the deployment goes in `model=`, and there is no api-version parameter. The `?api-version=…&
deployment=…` form is the deprecated beta path.
"""
import os
from collections.abc import AsyncIterator
from typing import Any, Protocol

from openai import AsyncOpenAI


class RealtimeConnection(Protocol):
    """What the relay needs from a realtime connection: send events, iterate events."""

    async def send(self, message: dict[str, Any]) -> None:
        ...

    def __aiter__(self) -> AsyncIterator[Any]:
        ...


def connect_realtime(token_provider):
    """Returns the async context manager for a live realtime connection.

    `token_provider` is an async callable returning a bearer token (`azure.identity.aio.
    get_bearer_token_provider` over the app's one shared credential). It is handed to the client
    uncalled: `AsyncOpenAI` awaits it on every connect, so a token refresh never blocks the event
    loop, and the credential's own cache serves calls that arrive inside a token's lifetime.

    Reads configuration at call time, not import time, and has no defaults: a missing pin fails
    closed rather than silently falling back to some other deployment (B3, CLAUDE.md). A pin
    rotation is a config change in provisioning, not an edit here. The boot-time (name, version)
    guard that makes B3 real is issue #21's deliverable.
    """
    endpoint = os.environ["AOAI_ENDPOINT"]
    deployment = os.environ["AOAI_DEPLOYMENT"]
    base_url = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
    # D2 (docs/phase7/exit-criteria.md): the static api-key secret is retired, Entra ID token from
    # the Container App's system-assigned identity instead -- the role grant this token needs is
    # aoai.bicep's `dataAccess` role assignment (Cognitive Services OpenAI User). Until the Phase 8
    # gate review this built a sync `DefaultAzureCredential` per call and called it on the event
    # loop; scope and fresh-per-call token: docs/phase7/research-aoai-rbac-realtime.md sections 3-4.
    client = AsyncOpenAI(api_key=token_provider, websocket_base_url=base_url)
    return client.realtime.connect(model=deployment)
