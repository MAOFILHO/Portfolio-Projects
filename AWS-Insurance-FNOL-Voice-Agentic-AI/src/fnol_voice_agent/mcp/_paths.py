"""Package-root-relative data paths, shared by the four domain modules.

`D87`, Option A (`RESULTS.md` §30/§31, Marco-approved 2026-08-16): this used to climb to an assumed REPO
root (`parents[3]`), which only resolved correctly in local dev. `infra/terraform/stacks/main/lambda.tf`'s
`data.archive_file.codehook` zips `src/`'s CONTENTS at the zip root (`source_dir = "${local.repo_root}/src"`),
so `/var/task` in the deployed Lambda corresponds to `<repo_root>/src`, one directory level SHALLOWER than
local dev -- `parents[3]` from this file landed on `/var`, not `/var/task`, and `data/synthetic/` was never
packaged into the zip in the first place regardless. Both problems, at once: real data existed nowhere the
running code could reach it, in either environment's own coordinate system.

Fixed by anchoring TWO FIXED LEVELS from this file -- `mcp/` -> `fnol_voice_agent/` (this package's own
root) -- and keeping the data INSIDE the package (`git mv data/synthetic/{policyholders,claims,vehicles}
src/fnol_voice_agent/data/synthetic/`) rather than climbing out of it. That arithmetic is identical in both
environments by construction, because both environments agree on where THIS FILE sits relative to the
package it is part of -- `<repo_root>/src/fnol_voice_agent/mcp/_paths.py` locally,
`/var/task/fnol_voice_agent/mcp/_paths.py` in Lambda -- even though they disagree on where the package sits
relative to anything above it. No environment branching, no assumed repo root, nothing to keep in sync by
hand across the two deploy targets. `data/synthetic/policy/` (the RAG corpus) and `.ingest-manifest.json`
deliberately did NOT move -- they are read only by local, CWD-relative ingestion/eval tooling
(`knowledge/ingest.py`, `scripts/measure_*.py`, `scripts/validate_synthetic_records.py`'s corpus-adjacent
checks) that never runs inside the deployed Lambda at all, and `_paths.py` never referenced them to begin
with (no `POLICY_PATH` constant here, before or after this fix).

Anchored on `__file__`, not on process `cwd` -- these modules are launched as MCP-server subprocesses
(`.claude/mcp.json`, or any other MCP client) whose working directory is whatever the launching client
chose, not necessarily the repo root the way `make test`/`pytest` invocations are. `__file__`-relative
resolution works identically whether this module is imported in-process, run as `python -m
fnol_voice_agent.mcp.<name>_server`, or imported from a test.

Pure path constants -- no `mcp` import, no I/O beyond the callers' own `Path.read_text()`.
"""

from __future__ import annotations

from pathlib import Path

# src/fnol_voice_agent/mcp/_paths.py -> parent.parent == src/fnol_voice_agent (THIS package's own root,
# not an assumed repo root). Identical arithmetic locally and in the deployed Lambda -- see the module
# docstring's `D87` section for why that equivalence is the whole fix.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PACKAGE_ROOT / "data" / "synthetic"
POLICYHOLDERS_PATH = DATA_DIR / "policyholders" / "policyholders.json"
CLAIMS_PATH = DATA_DIR / "claims" / "claims.json"
VEHICLES_PATH = DATA_DIR / "vehicles" / "vehicles.json"
