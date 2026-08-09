"""Post-provisioning smoke tests.

Run after `terraform apply`. Asserts every resource Terraform said it created
is actually live in Azure, AND on the approved SKU — Developer tier for the
fine-tuned deployment, GlobalStandard for the base catalog models. A resource
existing on the wrong (billable-by-the-hour) SKU is exactly the failure mode
COSTS.md exists to prevent, so this is checked explicitly, not just presence.

Reads `terraform output -json` for resource identifiers rather than
hardcoding names, since the auto-increment suffix makes names unpredictable.
All tests are skipped unless RUN_LIVE_SMOKE=1, so this file is inert (and
CI-safe) with no live infrastructure.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess

import pytest

_LIVE = os.environ.get("RUN_LIVE_SMOKE") == "1"
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_TF_DIR = _REPO_ROOT / "infra" / "terraform"


def _terraform_outputs() -> dict:
    proc = subprocess.run(
        ["terraform", f"-chdir={_TF_DIR}", "output", "-json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return {k: v.get("value") for k, v in json.loads(proc.stdout).items()}


def _az_json(*args: str) -> object:
    proc = subprocess.run(["az", *args, "-o", "json"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout or "null")


pytestmark = [
    pytest.mark.smoke_post_provision,
    pytest.mark.skipif(not _LIVE, reason="set RUN_LIVE_SMOKE=1"),
]


def test_resource_group_exists():
    outputs = _terraform_outputs()
    rg = outputs["resource_group_name"]
    info = _az_json("group", "show", "--name", rg)
    assert info["properties"]["provisioningState"] == "Succeeded"


def test_resource_group_carries_managed_by_tag():
    outputs = _terraform_outputs()
    rg = outputs["resource_group_name"]
    info = _az_json("group", "show", "--name", rg)
    assert info["tags"]["managed_by"] == "foundry-agentic-platform"


def test_budget_alert_exists_before_anything_else():
    outputs = _terraform_outputs()
    assert outputs.get("budget_id"), (
        "budget module produced no id — did it run before the Foundry account?"
    )


def test_foundry_account_is_live_and_s0():
    outputs = _terraform_outputs()
    account_id = outputs["foundry_account_id"]
    rg = outputs["resource_group_name"]
    account_name = account_id.rsplit("/", 1)[-1]
    info = _az_json(
        "cognitiveservices", "account", "show", "--name", account_name, "--resource-group", rg
    )
    assert info["properties"]["provisioningState"] == "Succeeded"
    assert info["sku"]["name"] == "S0"


def test_base_model_deployments_are_global_standard():
    outputs = _terraform_outputs()
    account_id = outputs["foundry_account_id"]
    rg = outputs["resource_group_name"]
    account_name = account_id.rsplit("/", 1)[-1]
    deployments = _az_json(
        "cognitiveservices",
        "account",
        "deployment",
        "list",
        "--name",
        account_name,
        "--resource-group",
        rg,
    )
    names = outputs["base_model_deployment_names"].values()
    by_name = {d["name"]: d for d in deployments}
    for name in names:
        assert name in by_name, f"expected deployment {name} not found"
        assert by_name[name]["sku"]["name"] == "GlobalStandard"


def test_finetuned_deployment_if_present_is_developer_tier():
    """Only asserts something if a fine-tuned deployment already exists —
    Terraform itself never creates one (it's created by the finetune agent
    after a real training job completes), so absence here is not a failure."""
    outputs = _terraform_outputs()
    account_id = outputs["foundry_account_id"]
    rg = outputs["resource_group_name"]
    account_name = account_id.rsplit("/", 1)[-1]
    deployments = _az_json(
        "cognitiveservices",
        "account",
        "deployment",
        "list",
        "--name",
        account_name,
        "--resource-group",
        rg,
    )
    ft_deployments = [d for d in deployments if "-ft-" in d["name"]]
    for d in ft_deployments:
        assert d["sku"]["name"] == "Developer", (
            f"{d['name']} is on {d['sku']['name']}, not Developer — "
            f"this bills $1.70/hr (~$1,224/month) even idle, see COSTS.md"
        )
