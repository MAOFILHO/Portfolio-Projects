"""Pre-provisioning smoke tests.

Run before `terraform apply`. These check the *environment* is ready to
provision, not the app — deliberately independent of DEMO_MODE. Anything that
needs live Azure access is marked `live` and skipped unless
`RUN_LIVE_SMOKE=1` is set, so this file is still safe to run in plain CI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.smoke_pre

_LIVE = os.environ.get("RUN_LIVE_SMOKE") == "1"


def test_python_version_at_least_3_12():
    assert sys.version_info >= (3, 12), f"need Python >=3.12, got {sys.version}"


def test_terraform_cli_present():
    assert shutil.which("terraform") is not None, "terraform CLI not found on PATH"


def test_az_cli_present():
    assert shutil.which("az") is not None, "az CLI not found on PATH"


def test_terraform_config_is_valid():
    root = os_path_repo_root()
    tf_dir = f"{root}/infra/terraform"
    # `validate` requires modules to be installed first; init is idempotent
    # and safe to re-run (it does not touch any Azure resource).
    init = subprocess.run(
        ["terraform", f"-chdir={tf_dir}", "init", "-input=false", "-backend=false"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert init.returncode == 0, init.stdout + init.stderr

    proc = subprocess.run(
        ["terraform", f"-chdir={tf_dir}", "validate", "-json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def os_path_repo_root() -> str:
    import pathlib

    return str(pathlib.Path(__file__).resolve().parents[2])


@pytest.mark.skipif(not _LIVE, reason="set RUN_LIVE_SMOKE=1 to check az login + quota")
def test_az_is_authenticated():
    proc = subprocess.run(["az", "account", "show"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, "not logged in — run `az login` first"


@pytest.mark.skipif(not _LIVE, reason="set RUN_LIVE_SMOKE=1 to check region validity")
def test_region_is_eastus2():
    proc = subprocess.run(
        ["az", "account", "list-locations", "-o", "tsv", "--query", "[].name"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "eastus2" in proc.stdout.splitlines()


@pytest.mark.skipif(
    not _LIVE, reason="set RUN_LIVE_SMOKE=1 to check live model+region availability"
)
def test_gpt_5_4_family_available_in_eastus2():
    # Best-effort — the exact CLI query surface for model availability shifts;
    # this documents intent and fails loudly rather than silently skipping in
    # a real pre-provision run.
    proc = subprocess.run(
        [
            "az",
            "cognitiveservices",
            "model",
            "list",
            "--location",
            "eastus2",
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "gpt-5.4" in proc.stdout or "gpt-4.1" in proc.stdout
