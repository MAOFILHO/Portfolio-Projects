"""Step 0: Check all prerequisites (Docker, Python, Azure CLI, Node.js, jq, curl)."""

from __future__ import annotations

import re
import shutil

from cdss_deploy.console import print_substep
from cdss_deploy.runner import run_cmd

REQUIRED_TOOLS = [
    ("docker", "24.0", "Docker Desktop: https://www.docker.com/products/docker-desktop"),
    ("python3", "3.12", "Python 3.12+: brew install python@3.12"),
    ("az", "2.50", "Azure CLI: brew install azure-cli"),
    ("node", "20.0", "Node.js LTS: brew install node"),
    ("npm", "9.0", "Included with Node.js"),
    ("jq", "1.6", "jq: brew install jq"),
    ("curl", "7.8", "curl: brew install curl"),
    ("git", "2.40", "Git: brew install git"),
]


def _parse_version(version_output: str) -> str | None:
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_output)
    return match.group(1) if match else None


def _version_gte(actual: str, minimum: str) -> bool:
    actual_parts = [int(x) for x in actual.split(".")]
    min_parts = [int(x) for x in minimum.split(".")]
    for a, m in zip(actual_parts, min_parts):
        if a > m:
            return True
        if a < m:
            return False
    return len(actual_parts) >= len(min_parts)


def run(ctx: dict) -> dict:
    source_dir = ctx["source_dir"]
    config = ctx.get("config")
    build_mode = getattr(config, "cdss_image_build_mode", "local") if config else "local"
    errors: list[str] = []

    tools = REQUIRED_TOOLS
    if build_mode == "acr":
        tools = [(t, v, h) for t, v, h in REQUIRED_TOOLS if t != "docker"]

    for tool, min_version, install_hint in tools:
        path = shutil.which(tool)
        if not path:
            print_substep(f"{tool}: NOT FOUND — {install_hint}", "error")
            errors.append(f"{tool} not installed")
            continue

        result = run_cmd([tool, "--version"])
        version = _parse_version(result.stdout + result.stderr)
        if version and _version_gte(version, min_version):
            print_substep(f"{tool}: v{version}", "ok")
        elif version:
            print_substep(f"{tool}: v{version} (minimum: {min_version})", "warn")
        else:
            print_substep(f"{tool}: installed (version unknown)", "warn")

    # Docker daemon check — only needed for local builds
    if build_mode == "acr":
        print_substep("Docker daemon: skipped (using ACR cloud build)", "ok")
    else:
        result = run_cmd(["docker", "info"])
        if result.success:
            print_substep("Docker daemon: running", "ok")
        else:
            print_substep("Docker daemon: not running — start Docker Desktop", "error")
            errors.append("Docker daemon not running")

    # Source directory check
    required_files = [
        "Dockerfile",
        "pyproject.toml",
        "src/cdss/api/app.py",
        "infra/bicep/main.bicep",
        "infra/scripts/bootstrap-deploy.sh",
        "infra/scripts/deploy.sh",
        "frontend/package.json",
        "sample_data/sample_patient.json",
    ]

    if source_dir.exists():
        print_substep(f"Source directory: {source_dir}", "ok")
        for f in required_files:
            if not (source_dir / f).exists():
                print_substep(f"Missing: {f}", "error")
                errors.append(f"Source file missing: {f}")
    else:
        print_substep(f"Source directory not found: {source_dir}", "error")
        errors.append(f"Source directory missing: {source_dir}")

    if errors:
        return {"success": False, "error": f"{len(errors)} prerequisite(s) failed: {', '.join(errors)}"}

    return {"success": True}
