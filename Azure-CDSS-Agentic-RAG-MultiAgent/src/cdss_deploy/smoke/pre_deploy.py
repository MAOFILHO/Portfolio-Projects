"""Pre-deploy smoke tests: verify all prerequisites before deployment."""

from __future__ import annotations

import shutil
from pathlib import Path

from cdss_deploy.console import console, print_substep
from cdss_deploy.runner import run_cmd


def run_pre_checks(source_dir: Path) -> bool:
    import os

    console.rule("[bold]Pre-Deploy Smoke Tests[/bold]", style="cyan")
    passed = 0
    failed = 0
    acr_mode = os.environ.get("CDSS_IMAGE_BUILD_MODE", "local") == "acr"

    # Tool checks
    tools = ["docker", "python3", "az", "node", "npm", "npx", "jq", "curl", "git"]
    if acr_mode:
        tools = [t for t in tools if t != "docker"]
    for tool in tools:
        if shutil.which(tool):
            print_substep(f"{tool}: found", "ok")
            passed += 1
        else:
            print_substep(f"{tool}: NOT FOUND", "error")
            failed += 1

    # Docker daemon — only needed for local builds
    if acr_mode:
        print_substep("Docker daemon: skipped (using ACR cloud build)", "ok")
        passed += 1
    else:
        result = run_cmd(["docker", "info"])
        if result.success:
            print_substep("Docker daemon: running", "ok")
            passed += 1
        else:
            print_substep("Docker daemon: not running", "error")
            failed += 1

    # Azure CLI logged in
    result = run_cmd(["az", "account", "show"])
    if result.success:
        print_substep("Azure CLI: logged in", "ok")
        passed += 1
    else:
        print_substep("Azure CLI: not logged in (run 'az login')", "error")
        failed += 1

    # Azure CLI extensions
    for ext in ["containerapp", "staticwebapp"]:
        result = run_cmd(["az", "extension", "show", "--name", ext])
        if result.success:
            print_substep(f"az extension {ext}: installed", "ok")
            passed += 1
        else:
            print_substep(f"az extension {ext}: installing...", "info")
            run_cmd(["az", "extension", "add", "--name", ext, "--upgrade", "--yes"])
            passed += 1

    # Bicep
    result = run_cmd(["az", "bicep", "version"])
    if result.success:
        print_substep("az bicep: installed", "ok")
        passed += 1
    else:
        print_substep("az bicep: installing...", "info")
        run_cmd(["az", "bicep", "install"])
        passed += 1

    # Source directory
    if source_dir.exists():
        print_substep(f"Source directory: {source_dir}", "ok")
        passed += 1

        critical = [
            "Dockerfile",
            "pyproject.toml",
            "infra/bicep/main.bicep",
            "infra/scripts/bootstrap-deploy.sh",
            "frontend/package.json",
        ]
        for f in critical:
            if (source_dir / f).exists():
                passed += 1
            else:
                print_substep(f"Missing: {f}", "error")
                failed += 1
    else:
        print_substep(f"Source directory NOT FOUND: {source_dir}", "error")
        failed += 1

    console.print()
    total = passed + failed
    if failed == 0:
        console.print(f"[green bold]All {passed} pre-deploy checks passed.[/green bold]")
    else:
        console.print(f"[red]{failed}/{total} checks failed.[/red]")

    return failed == 0
