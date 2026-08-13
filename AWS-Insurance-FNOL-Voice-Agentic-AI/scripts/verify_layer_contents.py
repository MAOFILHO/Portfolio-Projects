"""Verify a built Lambda dependency layer's CONTENTS, not its build exit code.

`D80`'s root cause was a missing dependency that a successful-looking build/deploy never checked for.
Marco's review of the layer plan (Stage 4, `docs/phase8/STAGE4-LAMBDA-LAYER-PLAN.md`) named the sibling
failure mode directly: *"pip resolving some packages and silently skipping others."* `pip install`
exiting 0 is evidence the resolver was satisfied with SOMETHING, not evidence every package this project
actually depends on is present at the pinned version. This script checks the artifact, not the exit code.

Two checks per retained runtime dependency, both against the built `python/` directory (never against a
running interpreter -- this is a static, zero-cost, zero-AWS check meant to run before any deploy):

1. **Metadata presence and version.** `<Name>-<Version>.dist-info/` exists and its version matches the
   pin in `pyproject.toml` exactly -- not "a version," not "present," the PINNED one. A stale cached
   wheel or a resolver picking a compatible-but-different version would pass a bare presence check and
   fail this one.
2. **Import-name presence.** The actual importable module (directory or `.py` file) a `dist-info` entry
   claims to provide is really there. Metadata without the module it describes is possible (a partial
   extraction, an interrupted copy) and would pass check 1 alone.

Excluded on purpose: `mcp`. See `STAGE4-LAMBDA-LAYER-PLAN.md` §3 for why it is not one of this project's
retained runtime dependencies, and §4 for the limits of the static analysis that established that and the
dynamic check (the deploy-time execution gate, `scripts/verify_lambda_execution.py`) that backs it up.

This script does NOT prove the packages IMPORT successfully under the target interpreter (arm64 Linux,
Python 3.12) -- it cannot, running on this dev machine. That is `verify_lambda_execution.py`'s job,
against the real deployed function, and the AWS-published container image is the recommended pre-deploy
alternative (see the plan §7). This script closes the narrower, cheaper gap: did the build even put the
right things in the box.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# Mirrors pyproject.toml's runtime `dependencies` list MINUS `mcp` (excluded, see module docstring).
# Duplicated here deliberately as an explicit, reviewable pin list rather than parsed from
# pyproject.toml at run time -- this script's whole point is to catch a silent mismatch, and parsing the
# same file the build already trusts would make this check blind to exactly the class of drift it
# exists to catch. A test (`tests/unit/test_verify_layer_contents.py`, to be added alongside
# `make build-lambda-layer`) asserts this dict's keys/versions match `pyproject.toml` on every run, so
# drift between the two is a loud, fast, local failure -- not a silent one discovered at deploy time.
EXPECTED_PACKAGES: dict[str, str] = {
    "boto3": "1.43.69",
    "pydantic": "2.13.4",
    "python-dateutil": "2.9.0.post0",
    "openfeature-sdk": "0.10.0",
    "numpy": "2.5.2",
    "langgraph": "1.2.11",
    "langgraph-checkpoint-aws": "1.2.1",
    "PyYAML": "6.0.2",
}

# pip/PyPI distribution name -> the actual top-level importable name. Not always the same string
# (`PyYAML` ships as `yaml`; `python-dateutil` ships as `dateutil`), and that gap is exactly what check 2
# is for -- getting it wrong here would make the check pass regardless of what is really on disk.
IMPORT_NAMES: dict[str, str] = {
    "boto3": "boto3",
    "pydantic": "pydantic",
    "python-dateutil": "dateutil",
    "openfeature-sdk": "openfeature",
    "numpy": "numpy",
    "langgraph": "langgraph",
    "langgraph-checkpoint-aws": "langgraph_checkpoint_aws",
    "PyYAML": "yaml",
}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _dist_info_versions(layer_root: Path) -> dict[str, str]:
    """Distribution name (normalized) -> version, read from every `*.dist-info` directory present."""
    versions: dict[str, str] = {}
    for entry in layer_root.glob("*.dist-info"):
        match = re.match(r"(.+)-([^-]+)\.dist-info$", entry.name)
        if match:
            versions[_normalize(match.group(1))] = match.group(2)
    return versions


def verify(layer_root: Path) -> list[str]:
    """Returns a list of problems. Empty means every expected package is present, at the pinned
    version, with its importable module actually on disk."""
    problems: list[str] = []

    if not layer_root.is_dir():
        return [f"layer root {layer_root} does not exist or is not a directory"]

    found_versions = _dist_info_versions(layer_root)

    for package, expected_version in EXPECTED_PACKAGES.items():
        key = _normalize(package)
        actual_version = found_versions.get(key)

        if actual_version is None:
            problems.append(f"MISSING: {package}=={expected_version} — no dist-info found at all")
            continue
        if actual_version != expected_version:
            problems.append(
                f"VERSION MISMATCH: {package} — pinned {expected_version}, layer has {actual_version}"
            )

        import_name = IMPORT_NAMES[package]
        module_dir = layer_root / import_name
        module_file = layer_root / f"{import_name}.py"
        if not module_dir.is_dir() and not module_file.is_file():
            problems.append(
                f"METADATA WITHOUT MODULE: {package}'s dist-info is present but "
                f"{import_name}/ (or {import_name}.py) is not — a partial or corrupted extraction"
            )

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "layer_root",
        type=Path,
        help="Path to the built layer's python/ directory (site-packages root).",
    )
    args = parser.parse_args(argv)

    problems = verify(args.layer_root)

    if problems:
        print(f"=== Layer content verification FAILED: {len(problems)} problem(s) ===")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"=== Layer content verification passed: {len(EXPECTED_PACKAGES)}/{len(EXPECTED_PACKAGES)} "
          f"expected packages present at pinned versions, with importable modules on disk ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
