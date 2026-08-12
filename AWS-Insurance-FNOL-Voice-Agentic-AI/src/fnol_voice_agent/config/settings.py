"""Settings. Single source of truth for the region default -- constraint 17 (`CLAUDE.md`) requires region
never appear as a literal scattered across application code; every module that needs a region imports
`DEFAULT_REGION` from here rather than hardcoding `"us-west-2"` itself.
"""

from __future__ import annotations

import os

DEFAULT_REGION = os.environ.get("FNOL_AWS_REGION", "us-west-2")

# ADR-004's model IDs -- named here, not re-typed at each call site.
ROUTER_MODEL_ID = "us.amazon.nova-micro-v1:0"

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
DEFAULT_GENERATION_MODEL_ID = "us.amazon.nova-lite-v1:0"
ALTERNATE_GENERATION_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# ADR-002's embedding model, matching src/fnol_voice_agent/knowledge/ingest.py's constants.
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024
