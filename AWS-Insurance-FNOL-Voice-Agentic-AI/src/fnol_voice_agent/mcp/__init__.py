"""MCP servers, one module per backend domain (`ADR-012`, `docs/phase5/BUILD-PLAN.md` Stage 2).

Deliberately empty beyond this docstring: importing this package must not import any of the four
domain modules (`policy_server`, `claims_server`, `contact_server`, `escalation_server`) as a side
effect, since each of those is independently runnable as `python -m fnol_voice_agent.mcp.<name>_server`
and each keeps the `mcp` transport SDK out of its own module-level import graph (ADR-012). A re-export
here would defeat that by forcing every domain's handler-only import to also import its siblings.
"""

from __future__ import annotations
