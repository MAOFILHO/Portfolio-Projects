"""Repo-root-relative data paths, shared by the four domain modules.

Anchored on `__file__`, not on process `cwd` -- these modules are launched as MCP-server subprocesses
(`.claude/mcp.json`, or any other MCP client) whose working directory is whatever the launching client
chose, not necessarily the repo root the way `make test`/`pytest` invocations are. `__file__`-relative
resolution works identically whether this module is imported in-process, run as `python -m
fnol_voice_agent.mcp.<name>_server`, or imported from a test.

Pure path constants -- no `mcp` import, no I/O beyond the callers' own `Path.read_text()`.
"""

from __future__ import annotations

from pathlib import Path

# src/fnol_voice_agent/mcp/_paths.py -> parents[3] == repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "synthetic"
POLICYHOLDERS_PATH = DATA_DIR / "policyholders" / "policyholders.json"
CLAIMS_PATH = DATA_DIR / "claims" / "claims.json"
VEHICLES_PATH = DATA_DIR / "vehicles" / "vehicles.json"
