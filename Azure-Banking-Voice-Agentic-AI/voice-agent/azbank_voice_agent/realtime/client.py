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
from typing import Any, AsyncIterator, Protocol

from openai import AsyncOpenAI


class RealtimeConnection(Protocol):
    """What the relay needs from a realtime connection: send events, iterate events."""

    async def send(self, message: dict[str, Any]) -> None:
        ...

    def __aiter__(self) -> AsyncIterator[Any]:
        ...


def connect_realtime():
    """Returns the async context manager for a live realtime connection.

    Reads configuration at call time, not import time, and has no defaults: a missing pin fails
    closed rather than silently falling back to some other deployment (B3, CLAUDE.md). A pin
    rotation is a config change in provisioning, not an edit here. The boot-time (name, version)
    guard that makes B3 real is issue #21's deliverable.
    """
    api_key = os.environ["AOAI_KEY"]
    endpoint = os.environ["AOAI_ENDPOINT"]
    deployment = os.environ["AOAI_DEPLOYMENT"]
    base_url = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
    client = AsyncOpenAI(api_key=api_key, websocket_base_url=base_url)
    return client.realtime.connect(model=deployment)
