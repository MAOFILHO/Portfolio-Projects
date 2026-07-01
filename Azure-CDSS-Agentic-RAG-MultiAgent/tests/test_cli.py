"""Tests for CLI command structure."""

from __future__ import annotations

from typer.testing import CliRunner

from cdss_deploy.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "deploy" in result.stdout
    assert "teardown" in result.stdout
    assert "status" in result.stdout


def test_status_no_state(tmp_path) -> None:
    import os
    with patch_state_file(tmp_path):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0


def patch_state_file(tmp_path):
    from unittest.mock import patch
    return patch("cdss_deploy.cli.STATE_FILE", tmp_path / "state.json")
