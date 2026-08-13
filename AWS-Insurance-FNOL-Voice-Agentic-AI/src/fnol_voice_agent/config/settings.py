"""Settings. Single source of truth for the region default -- constraint 17 (`CLAUDE.md`) requires region
never appear as a literal scattered across application code; every module that needs a region imports
`DEFAULT_REGION` from here rather than hardcoding `"us-west-2"` itself.
"""

from __future__ import annotations

import os

DEFAULT_REGION = os.environ.get("FNOL_AWS_REGION", "us-west-2")


def _model_id(env_var: str, default: str) -> str:
    """Model identifier, overridable by an application inference profile ARN.

    `ADR-016`. Bedrock on-demand spend invoked through a SYSTEM-DEFINED `us.*` profile is
    unattributable -- system profiles carry no tags -- so Phase 8's tag-filtered budget alarm cannot see
    it. An APPLICATION inference profile wrapping the same `us.*` profile carries cost allocation tags
    and is passed as `modelId` in its place; `infra/terraform/stacks/inference` creates them and outputs
    the ARNs.

    The `us.*` literal stays the DEFAULT rather than the ARN, deliberately and for two reasons:

    1. `CLAUDE.md` requires everything to run locally without AWS. A profile ARN is account-specific and
       only exists after an apply, so hardcoding one would make the simulator, the tests and every Tier A
       eval depend on provisioned infrastructure.
    2. `make destroy` removes the profiles. The default is what the code falls back to, and it has to be
       something that still works -- attribution is a property worth having, not worth failing closed on.

    So: identical routing either way, and the ARN is a deployment-time fact rather than a source-code one.
    """
    return os.environ.get(env_var, default)


# ADR-004's model IDs -- named here, not re-typed at each call site.
ROUTER_MODEL_ID = _model_id("FNOL_ROUTER_MODEL_ID", "us.amazon.nova-micro-v1:0")

# `D27`. The router's output is a decision, not prose, so it samples at 0. Through Phase 6 no
# temperature was sent at all and Bedrock applied Nova's default of 0.7 -- measured in Phase 7
# Stage 0.5 over 5 runs x 78 turns at each setting:
#
#   temperature 0.7 : macro-F1 0.488-0.551 (sd 0.024), 35/78 turns unstable, 13/78 safety_flag unstable
#   temperature 0.0 : macro-F1 0.518 exactly on all 5 runs, 0/78 unstable
#
# **This buys reproducibility, not accuracy** -- 0.518 sits inside the 0.7 range, so the fix does not
# move quality at all. What it removes is a safety detector whose verdict flipped between runs on 17%
# of turns, which is not something a gate can be written against.
ROUTER_TEMPERATURE = 0.0
DEFAULT_GENERATION_MODEL_ID = _model_id("FNOL_GENERATION_MODEL_ID", "us.amazon.nova-lite-v1:0")

# `Q12`, decided by Marco 2026-08-12 at Stage 2 rather than deferred to Stage 8: *"A spoken line in an FNOL
# system gains nothing from sampling and loses reproducibility, defect stability, and same-question-
# same-answer consistency."*
#
# The router fix (`D27`) pinned only `classify_turn`; `generate_response` still sent no temperature, so Nova
# Lite kept sampling at Nova's default 0.7. That made every Phase 6 generation figure -- groundedness 9/9,
# answer relevance 9/9, redundancy 0/9 -- a single draw, and it is the most likely mechanism behind `CF5`'s
# *intermittent* redundancy defect: a defect that appears on some runs and not others, from an unchanged
# prompt, is what a sampled decoder produces.
#
# Two callers hear the same answer to the same question, which for a coverage question is a correctness
# property and not a stylistic one. The naturalness argument for sampling does not apply here either:
# `D17`/`D20` mean only two prompts in this system generate at all -- everything else is a fixed string or a
# template -- so variety was never reaching the caller through this path anyway.
GENERATION_TEMPERATURE = 0.0
ALTERNATE_GENERATION_MODEL_ID = _model_id(
    "FNOL_JUDGE_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)

# ADR-002's embedding model, matching src/fnol_voice_agent/knowledge/ingest.py's constants.
EMBEDDING_MODEL_ID = _model_id("FNOL_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIMENSION = 1024
