"""Pre-setup smoke tests: run BEFORE `make setup`. Confirms the machine is
ready for setup.py to actually succeed — Python version, and (only if the
user intends to use Azure) that the CLI is present and logged in."""
import os
import shutil
import subprocess
import sys

MIN_PYTHON = (3, 12)


def test_python_version_at_least_3_12():
    assert sys.version_info[:2] >= MIN_PYTHON, (
        f"Python {sys.version.split()[0]} found — this project requires >= "
        f"{'.'.join(map(str, MIN_PYTHON))}"
    )


def test_env_example_exists(repo_root):
    assert (repo_root / ".env.example").exists()


def test_azure_cli_present_and_logged_in_if_azure_mode(repo_root):
    if os.environ.get("RUN_MODE", "local") != "azure":
        import pytest
        pytest.skip("RUN_MODE is not 'azure' — Azure CLI is not required for local-only usage")

    assert shutil.which("az") is not None, "Azure CLI ('az') not found on PATH"
    result = subprocess.run(["az", "account", "show", "--output", "json"], capture_output=True, text=True)
    assert result.returncode == 0, "Not logged in to Azure CLI — run `az login` first"
