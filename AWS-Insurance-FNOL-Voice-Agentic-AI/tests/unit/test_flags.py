from __future__ import annotations

from fnol_voice_agent.config.flags import (
    GENERATION_TIER_FLAG,
    configure_default_flags,
    get_generation_model_id,
)
from fnol_voice_agent.config.settings import (
    ALTERNATE_GENERATION_MODEL_ID,
    DEFAULT_GENERATION_MODEL_ID,
)


def test_default_flag_resolves_to_nova_lite() -> None:
    configure_default_flags()
    assert get_generation_model_id() == DEFAULT_GENERATION_MODEL_ID


def test_flag_can_be_flipped_to_the_alternate_tier() -> None:
    from openfeature import api
    from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

    api.set_provider(
        InMemoryProvider(
            {
                GENERATION_TIER_FLAG: InMemoryFlag(
                    default_variant="claude-haiku-4-5",
                    variants={
                        "nova-lite": DEFAULT_GENERATION_MODEL_ID,
                        "claude-haiku-4-5": ALTERNATE_GENERATION_MODEL_ID,
                    },
                )
            }
        )
    )
    assert get_generation_model_id() == ALTERNATE_GENERATION_MODEL_ID
    configure_default_flags()  # restore, so this test doesn't leak state into others
