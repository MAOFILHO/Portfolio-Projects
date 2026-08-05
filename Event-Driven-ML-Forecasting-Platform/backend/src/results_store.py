"""Simple per-model JSON result persistence, shared by run_pipeline.py (seed run)
and api/main.py (on-demand job results), so the dashboard has data to show on
first load and after every live re-run."""
from __future__ import annotations

import json
from pathlib import Path


def _result_path(output_dir: Path, model_key: str) -> Path:
    return output_dir / "results" / f"{model_key}.json"


def save_result(output_dir: Path, model_key: str, data: dict) -> None:
    path = _result_path(output_dir, model_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_result(output_dir: Path, model_key: str) -> dict | None:
    path = _result_path(output_dir, model_key)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def load_all_results(output_dir: Path) -> dict[str, dict]:
    results_dir = output_dir / "results"
    if not results_dir.exists():
        return {}
    return {file.stem: json.loads(file.read_text()) for file in results_dir.glob("*.json")}
