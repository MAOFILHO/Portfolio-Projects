"""Tests for deployment state persistence."""

from __future__ import annotations

from pathlib import Path

from cdss_deploy.state import DeploymentState


def test_load_nonexistent(tmp_state_file: Path) -> None:
    state = DeploymentState.load(tmp_state_file)
    assert state.steps == {}
    assert state.resource_group == ""
    assert state.created_at != ""


def test_save_and_reload(tmp_state_file: Path) -> None:
    state = DeploymentState.load(tmp_state_file)
    state.resource_group = "test-rg"
    state.mark_started("s00_preflight")
    state.mark_completed("s00_preflight", outputs={"foo": "bar"})
    state.save()

    reloaded = DeploymentState.load(tmp_state_file)
    assert reloaded.resource_group == "test-rg"
    assert reloaded.is_completed("s00_preflight")
    assert reloaded.steps["s00_preflight"].outputs == {"foo": "bar"}


def test_is_completed(tmp_state_file: Path) -> None:
    state = DeploymentState.load(tmp_state_file)
    assert not state.is_completed("s00_preflight")
    state.mark_completed("s00_preflight")
    assert state.is_completed("s00_preflight")


def test_mark_failed(tmp_state_file: Path) -> None:
    state = DeploymentState.load(tmp_state_file)
    state.mark_failed("s03_deploy_infra", "timeout")
    assert state.steps["s03_deploy_infra"].status == "failed"
    assert state.steps["s03_deploy_infra"].error == "timeout"


def test_update_resources(tmp_state_file: Path) -> None:
    state = DeploymentState.load(tmp_state_file)
    state.update_resources({"app_name": "test-api"})
    state.update_resources({"api_fqdn": "test.azure.io"})
    assert state.deployed_resources["app_name"] == "test-api"
    assert state.deployed_resources["api_fqdn"] == "test.azure.io"


def test_reset(tmp_state_file: Path) -> None:
    state = DeploymentState.load(tmp_state_file)
    state.mark_completed("s00_preflight")
    state.update_resources({"app_name": "api"})
    state.reset()
    assert state.steps == {}
    assert state.deployed_resources == {}


def test_load_existing(populated_state_file: Path) -> None:
    state = DeploymentState.load(populated_state_file)
    assert state.resource_group == "cdss-test-rg"
    assert state.is_completed("s00_preflight")
    assert state.deployed_resources["app_name"] == "cdss-test-api"
