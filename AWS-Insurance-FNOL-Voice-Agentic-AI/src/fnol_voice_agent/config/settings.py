"""Settings. Single source of truth for the region default -- constraint 17 (`CLAUDE.md`) requires region
never appear as a literal scattered across application code; every module that needs a region imports
`DEFAULT_REGION` from here rather than hardcoding `"us-west-2"` itself.
"""

from __future__ import annotations

import os

DEFAULT_REGION = os.environ.get("FNOL_AWS_REGION", "us-west-2")

# ADR-004's model IDs -- named here, not re-typed at each call site.
ROUTER_MODEL_ID = "us.amazon.nova-micro-v1:0"
DEFAULT_GENERATION_MODEL_ID = "us.amazon.nova-lite-v1:0"
ALTERNATE_GENERATION_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# ADR-002's embedding model, matching src/fnol_voice_agent/knowledge/ingest.py's constants.
EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024
