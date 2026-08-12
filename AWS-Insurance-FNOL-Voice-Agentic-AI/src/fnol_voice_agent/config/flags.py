"""OpenFeature kill-switch flags. `AI-USE-CASE-CARD.md`'s human oversight model: "OpenFeature flags gate
model tier, RAG, agentic tools and prompt versions, each taking effect on the next turn." This module wires
exactly the one flag `ADR-004` requires today (the generation-tier model) using OpenFeature's in-memory
provider -- zero external service, zero cost, consistent with the mock-by-default posture everywhere else
in this project. `ADR-004`'s structural guarantee holds regardless of provider choice: this flag has no
code path to the fixed router+L2 call (Nova Micro, never flag-controlled).
"""

from __future__ import annotations

from openfeature import api
from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

from .settings import ALTERNATE_GENERATION_MODEL_ID, DEFAULT_GENERATION_MODEL_ID

GENERATION_TIER_FLAG = "generation-tier"


def configure_default_flags() -> None:
    """Installs the in-memory provider with this project's one live flag. Call once at process start
    (or per-test, since the in-memory provider holds no state a fresh call wouldn't reset)."""
    api.set_provider(
        InMemoryProvider(
            {
                GENERATION_TIER_FLAG: InMemoryFlag(
                    default_variant="nova-lite",
                    variants={
                        "nova-lite": DEFAULT_GENERATION_MODEL_ID,
                        "claude-haiku-4-5": ALTERNATE_GENERATION_MODEL_ID,
                    },
                )
            }
        )
    )


def get_generation_model_id() -> str:
    """Reads the current generation-tier flag value. Falls back to the Nova Lite default if the provider
    was never configured (e.g. a test importing this module without calling `configure_default_flags`
    first) -- fails safe to the cheaper, already-accepted default, never to an unconfigured error state.
    """
    client = api.get_client()
    return client.get_string_value(GENERATION_TIER_FLAG, DEFAULT_GENERATION_MODEL_ID)
