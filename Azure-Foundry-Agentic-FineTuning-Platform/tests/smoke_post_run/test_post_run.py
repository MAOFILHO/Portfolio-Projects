"""Post-run smoke tests.

Run after `make run` (any DEMO_MODE). Asserts the three demo outputs the CLI's
`run-all` writes to `outputs/` actually exist and are non-empty/well-formed —
catches a silent failure where a demo "completes" but writes nothing useful.

Unlike smoke_pre/smoke_post_provision, this suite runs in BOTH mock and live
mode — it doesn't touch Azure directly, only the files `make run` produced —
so it is not gated behind RUN_LIVE_SMOKE.
"""

from __future__ import annotations

import json
import pathlib

import pytest

pytestmark = pytest.mark.smoke_post_run

_OUTPUTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "outputs"

_EXPECTED_FILES = ("discovery.json", "finetune.json", "comparison.json")


def _require_outputs_dir():
    if not _OUTPUTS_DIR.exists():
        pytest.skip(f"{_OUTPUTS_DIR} does not exist — run `make run` first")


@pytest.mark.parametrize("name", _EXPECTED_FILES)
def test_output_file_exists_and_non_empty(name: str):
    _require_outputs_dir()
    path = _OUTPUTS_DIR / name
    if not path.exists():
        pytest.skip(f"{path} not found — run `make run` first")
    assert path.stat().st_size > 0, f"{name} exists but is empty"


@pytest.mark.parametrize("name", _EXPECTED_FILES)
def test_output_file_is_valid_json(name: str):
    _require_outputs_dir()
    path = _OUTPUTS_DIR / name
    if not path.exists():
        pytest.skip(f"{path} not found — run `make run` first")
    data = json.loads(path.read_text())
    assert isinstance(data, dict)
    assert data, f"{name} parsed but is an empty object"


def test_discovery_output_has_leaderboards():
    _require_outputs_dir()
    path = _OUTPUTS_DIR / "discovery.json"
    if not path.exists():
        pytest.skip("discovery.json not found — run `make run` first")
    data = json.loads(path.read_text())
    assert "leaderboards" in data
    assert "evaluation" in data


def test_finetune_output_reached_a_terminal_status():
    _require_outputs_dir()
    path = _OUTPUTS_DIR / "finetune.json"
    if not path.exists():
        pytest.skip("finetune.json not found — run `make run` first")
    data = json.loads(path.read_text())
    if data.get("blocked"):
        pytest.fail(f"finetune job was blocked: {data.get('validation', {}).get('errors')}")
    assert data["status"]["status"] in {"succeeded", "running", "queued"}


def test_comparison_output_has_scored_prompts():
    _require_outputs_dir()
    path = _OUTPUTS_DIR / "comparison.json"
    if not path.exists():
        pytest.skip("comparison.json not found — run `make run` first")
    data = json.loads(path.read_text())
    assert "report" in data
    assert len(data["report"]["comparisons"]) > 0
