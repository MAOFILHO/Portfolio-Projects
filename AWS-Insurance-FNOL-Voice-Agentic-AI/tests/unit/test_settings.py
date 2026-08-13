"""Settings, and specifically `ADR-016`'s environment override.

Nothing had ever imported `config.settings` in a test before Phase 8 -- the constants were exercised
only indirectly, by whatever happened to read them. That is the same gap Phase 7 Stage 8 found in
`guardrails_nodes.py`, so it is worth closing here rather than noting.

The property under test is not "the override works". It is the pair of properties `ADR-016` decision 3
actually depends on:

  1. Absent the environment variable, the value is the `us.*` literal -- so the simulator, the tests and
     every Tier A eval run with no AWS state and no provisioned inference profile.
  2. Present, it wins -- so a deployment can point the same code at a tagged application profile ARN
     without a code change.

If (1) regressed to an ARN default, every offline path in this project would start depending on
infrastructure that `make destroy` removes.
"""

from __future__ import annotations

import importlib

import pytest

from fnol_voice_agent.config import settings

# The four overridable identifiers, with the default each must fall back to. Kept as data so a fifth
# model added without a test is visible as an absence here rather than silently untested.
OVERRIDES = [
    ("FNOL_ROUTER_MODEL_ID", "ROUTER_MODEL_ID", "us.amazon.nova-micro-v1:0"),
    ("FNOL_GENERATION_MODEL_ID", "DEFAULT_GENERATION_MODEL_ID", "us.amazon.nova-lite-v1:0"),
    (
        "FNOL_JUDGE_MODEL_ID",
        "ALTERNATE_GENERATION_MODEL_ID",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    ),
    ("FNOL_EMBEDDING_MODEL_ID", "EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
]


@pytest.mark.parametrize("env_var,attr,default", OVERRIDES)
def test_default_is_the_system_profile_not_an_arn(
    env_var: str, attr: str, default: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no env var set, the default is the `us.*` literal -- never an account-specific ARN."""
    monkeypatch.delenv(env_var, raising=False)
    reloaded = importlib.reload(settings)
    try:
        assert getattr(reloaded, attr) == default
        # The specific regression that would break every offline path.
        assert not getattr(reloaded, attr).startswith("arn:")
    finally:
        importlib.reload(settings)


@pytest.mark.parametrize("env_var,attr,default", OVERRIDES)
def test_env_override_wins(
    env_var: str, attr: str, default: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deployment can substitute a tagged application inference profile ARN without a code change."""
    arn = f"arn:aws:bedrock:us-west-2:000000000000:application-inference-profile/{attr.lower()}"
    monkeypatch.setenv(env_var, arn)
    reloaded = importlib.reload(settings)
    try:
        assert getattr(reloaded, attr) == arn
    finally:
        monkeypatch.delenv(env_var, raising=False)
        importlib.reload(settings)


def test_region_is_not_a_literal_at_call_sites(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constraint 17: region comes from here, and is overridable for a region migration."""
    monkeypatch.setenv("FNOL_AWS_REGION", "us-east-2")
    reloaded = importlib.reload(settings)
    try:
        assert reloaded.DEFAULT_REGION == "us-east-2"
    finally:
        monkeypatch.delenv("FNOL_AWS_REGION", raising=False)
        importlib.reload(settings)
        assert settings.DEFAULT_REGION == "us-west-2"
