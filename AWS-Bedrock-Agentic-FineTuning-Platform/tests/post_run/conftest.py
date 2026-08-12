import json
import os
from pathlib import Path

import pytest

from bedrock_platform.config.scenario_loader import enabled_scenarios

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _results_path(scenario_id: str) -> Path:
    return REPO_ROOT / "artifacts" / scenario_id / "results.json"


@pytest.fixture(params=[s.id for s in enabled_scenarios()])
def run_results(request) -> dict:
    """Loads artifacts/{scenario}/results.json written by scripts/run_pipeline.py.
    Skips scenarios that haven't been run yet rather than failing the suite."""
    if not os.environ.get("PROJECT_SUFFIX"):
        pytest.skip("PROJECT_SUFFIX not set")

    path = _results_path(request.param)
    if not path.exists():
        pytest.skip(f"No results.json for scenario {request.param!r} — run_pipeline hasn't run yet")

    data = json.loads(path.read_text())
    data["_scenario_id"] = request.param
    return data
