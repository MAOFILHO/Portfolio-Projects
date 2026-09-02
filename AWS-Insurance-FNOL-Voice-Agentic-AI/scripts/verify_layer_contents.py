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

A THIRD check, gated on platform, attempts a real `importlib.import_module()` of each package with the
layer root on `sys.path`. Marco's review of the first version of this script named the gap directly: check
1 alone is the WEAKER claim, because the manylinux failure mode already hit once this session (`PyYAML`/
`numpy` resolving zero versions under one platform tag) puts real, correctly-named files on disk that
still fail to import -- metadata and even the presence check can both be satisfied by a wheel built for
the wrong ABI. Presence is necessary, not sufficient.

That check is only meaningful if it runs under the TARGET interpreter and architecture (`aarch64`-Linux,
CPython 3.12 -- Lambda's `arm64` runtime). Several of these 8 packages ship compiled extensions (`numpy`,
`pydantic`'s Rust `pydantic-core` core). Importing `aarch64`-Linux `.so` files under a different platform's
interpreter does not approximate that answer -- it fails immediately and unconditionally on an ELF/Mach-O
mismatch, regardless of whether the layer is actually correct for Lambda. Running this check on a
mismatched platform would therefore produce a false FAIL on every real layer, not a weaker true signal --
worse than not running it, because a script printing "FAILED" that fails on every possible input trains
its own reader to ignore it. So: on a platform/interpreter match, the import actually runs and a failure is
real evidence. On a mismatch, the import check is SKIPPED, loudly, with the interpreter/platform that ran
printed either way -- never silently treated as passed, and never run to produce a result that cannot be
trusted. This script's own run this session was on this dev machine (Darwin, not Linux `aarch64`), so its
import check skipped for exactly this reason -- see the plan §3 for what that leaves open and its
disposition (the AWS-published container image, or `verify_lambda_execution.py` against the real deployed
function, are the two ways to actually close it).

A FOURTH check, `--zip`, gated on nothing (always meaningful, unlike the import check -- this is pure
path inspection, no interpreter involved): asserts every expected package appears under a top-level
`python/` prefix INSIDE THE BUILT ZIP ITSELF, not merely present in the directory the zip was built from.

`D82` is the reason this check exists, not a hypothetical: every check above -- checks 1-3, the whole
`verify()` function -- ran against `.terraform-build/layer/python`, the DIRECTORY, and passed 8/8, import
check included once run under a matching interpreter. The LAYER attached to the deployed function still
crashed on `No module named 'pydantic'`, because `lambda.tf`'s `archive_file` zipped that directory's
CONTENTS at the zip's own root, silently dropping the `python/` path component AWS Lambda's layer
convention depends on -- every package landed at `/opt/pydantic` instead of `/opt/python/pydantic`, the
one path Lambda's runtime actually searches. **Presence-in-directory and correct-path-in-archive are
different claims.** `D82` passed the first and failed the second, and nothing before this check would
have caught that difference, because nothing before this check ever looked inside the artifact that
actually ships -- only at the directory it was assembled from. `verify_archive_structure` below opens the
zip with `zipfile` and inspects its own internal paths; it cannot be fooled by a source-directory bug the
way the directory-based checks structurally cannot see one.
"""

from __future__ import annotations

import argparse
import importlib
import platform
import re
import sys
import zipfile
from pathlib import Path

# Lambda's `arm64` runtime, at the Python version this layer is built for (`pyproject.toml`'s
# `>=3.12,<3.13`). Only a match on all three lets an import attempted by THIS script mean anything --
# see the module docstring on why a mismatched run is skipped rather than trusted or silently omitted.
_TARGET_SYSTEM = "Linux"
_TARGET_MACHINE = {"aarch64", "arm64"}  # `platform.machine()` reports differently across libc/OS
_TARGET_PYTHON = (3, 12)


def _platform_report() -> str:
    """What actually ran this check, printed unconditionally -- this is Marco's ask directly: report
    which interpreter it ran under, not just whether it matched."""
    return (
        f"{platform.system()} {platform.machine()}, "
        f"CPython {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )


def _running_on_target() -> bool:
    return (
        platform.system() == _TARGET_SYSTEM
        and platform.machine() in _TARGET_MACHINE
        and (sys.version_info.major, sys.version_info.minor) == _TARGET_PYTHON
    )


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


def _try_import(import_name: str, layer_root: Path) -> str | None:
    """Attempts a real `importlib.import_module()` with `layer_root` on `sys.path`. Returns a problem
    string on failure, `None` on success. Only called when `_running_on_target()` is true -- see the
    module docstring for why a mismatched-platform import is skipped rather than attempted and trusted.
    """
    sys.path.insert(0, str(layer_root))
    try:
        importlib.invalidate_caches()
        importlib.import_module(import_name)
        return None
    except (
        Exception
    ) as exc:  # noqa: BLE001 - any import failure is the finding, not a bug in this script
        return f"IMPORT FAILED: {import_name} — {type(exc).__name__}: {exc}"
    finally:
        sys.path.remove(str(layer_root))
        sys.modules.pop(import_name, None)


def verify(layer_root: Path, *, attempt_import: bool = True) -> tuple[list[str], bool]:
    """Returns `(problems, import_check_ran)`. `problems` empty means every expected package is present,
    at the pinned version, with its importable module on disk -- and, when `import_check_ran` is `True`,
    that every one of them actually imports under THIS interpreter. `import_check_ran` is `False` when
    `attempt_import` was requested but this interpreter/platform does not match Lambda's `arm64` runtime
    (see `_running_on_target`) -- in that case no import is attempted at all, on any package, because a
    failure there would not be evidence and a success would not be either."""
    problems: list[str] = []

    if not layer_root.is_dir():
        return [f"layer root {layer_root} does not exist or is not a directory"], False

    found_versions = _dist_info_versions(layer_root)
    import_check_ran = attempt_import and _running_on_target()

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
            continue  # nothing on disk to attempt importing

        if import_check_ran:
            import_problem = _try_import(import_name, layer_root)
            if import_problem is not None:
                problems.append(import_problem)

    return problems, import_check_ran


def verify_archive_structure(zip_path: Path) -> list[str]:
    """`D82`. Inspects the BUILT ZIP's own internal paths -- never the directory `verify()` above reads
    from, because a bug in how the zip was ASSEMBLED (this is what `D82` was) is invisible to any check
    that only ever looks at the directory it was assembled from. Returns an empty list on success.

    Two things are checked, in order:

    1. A top-level `python/` prefix exists in the archive AT ALL. Its total absence is `D82`'s exact
       shape -- every package present, correctly versioned, at the zip's own root instead.
    2. Every `IMPORT_NAMES` value has at least one archive entry under `python/<import_name>/` (a
       package directory) or exactly at `python/<import_name>.py` (a single-file module, e.g. `six.py`
       if it were retained). Checked per package rather than inferred from (1) alone, because a PARTIALLY
       correct archive -- some packages nested under `python/`, others not, e.g. from a manual/partial
       repackaging -- would pass (1) and still ship a broken layer for whichever packages it missed.
    """
    problems: list[str] = []
    if not zip_path.is_file():
        return [f"archive {zip_path} does not exist or is not a file"]

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()

    if not any(name.startswith("python/") for name in names):
        problems.append(
            f"ARCHIVE STRUCTURE: no entry under a top-level 'python/' prefix found anywhere in "
            f"{zip_path.name} ({len(names)} entries total) -- this is D82's exact shape: packages "
            f"present at the zip's OWN root instead of nested under python/, which Lambda's runtime "
            f"never adds to sys.path"
        )
        return problems  # per-package checks below would only restate the same finding once each

    for package, import_name in IMPORT_NAMES.items():
        expected_dir_prefix = f"python/{import_name}/"
        expected_file = f"python/{import_name}.py"
        if not any(name.startswith(expected_dir_prefix) or name == expected_file for name in names):
            problems.append(
                f"ARCHIVE STRUCTURE: {package} ({import_name}) has no entry under "
                f"{expected_dir_prefix!r} or {expected_file!r} inside {zip_path.name} -- present on "
                f"disk does not mean present at the right path inside the archive that actually ships"
            )

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "layer_root",
        type=Path,
        help="Path to the built layer's python/ directory (site-packages root).",
    )
    parser.add_argument(
        "--no-import-check",
        action="store_true",
        help="Skip the import attempt even on a matching platform; presence/version checks only.",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        default=None,
        help=(
            "Path to the built layer ZIP (D82). Asserts every expected package appears under a "
            "top-level python/ prefix inside the archive itself, not only in the directory it was "
            "built from. Strongly recommended before any apply; SKIPPED loudly, not silently, if "
            "omitted -- see the module docstring."
        ),
    )
    args = parser.parse_args(argv)

    print(f"=== Running under: {_platform_report()} ===")
    problems, import_check_ran = verify(args.layer_root, attempt_import=not args.no_import_check)

    if import_check_ran:
        print(
            "=== Import check: RAN (interpreter matches Lambda's arm64/Linux/CPython 3.12 target) ==="
        )
    else:
        print(
            "=== Import check: SKIPPED — this interpreter does not match Lambda's target "
            "(Linux aarch64, CPython 3.12). A skip here is not a pass: presence-and-version checks "
            "below are real, but nothing has confirmed these packages actually import under Lambda. "
            "See STAGE4-LAMBDA-LAYER-PLAN.md §3 for how that gap is closed (the AWS-published container "
            "image pre-deploy, or verify_lambda_execution.py's post-deploy event matrix). ==="
        )

    archive_problems: list[str] = []
    if args.zip is not None:
        archive_problems = verify_archive_structure(args.zip)
        if archive_problems:
            print(f"=== Archive structure check: RAN against {args.zip} -- FAILED ===")
        else:
            print(
                f"=== Archive structure check: RAN against {args.zip} -- every expected package is "
                f"under a top-level python/ prefix (D82) ==="
            )
    else:
        print(
            "=== Archive structure check: SKIPPED — no --zip given. A skip here is not a pass: "
            "presence-in-directory (checks above) is a DIFFERENT claim from correct-path-in-archive, "
            "and D82 is the proof -- 8/8 on every check above, and the shipped zip still put every "
            "package at the wrong path. Pass --zip before trusting this layer for an apply. ==="
        )

    problems = problems + archive_problems
    if problems:
        print(f"=== Layer content verification FAILED: {len(problems)} problem(s) ===")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    import_clause = (
        "and imported successfully under this interpreter"
        if import_check_ran
        else "with importable modules on disk (import NOT attempted — see the skip notice above)"
    )
    archive_clause = (
        "and every expected package is at the correct python/ path in the built zip"
        if args.zip is not None
        else "with the archive's own structure NOT checked — see the skip notice above"
    )
    print(
        f"=== Layer content verification passed: {len(EXPECTED_PACKAGES)}/{len(EXPECTED_PACKAGES)} "
        f"expected packages present at pinned versions, {import_clause}, {archive_clause} ==="
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
