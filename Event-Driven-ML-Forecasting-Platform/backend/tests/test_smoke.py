"""End-to-end smoke test: runs every model in the registry (ARIMA, both
SARIMAX models, TensorFlow LSTM, PyTorch LSTM) against the real data/model
files and asserts each produces the expected result shape.

Uses the pre-trained checkpoints (LSTM_RETRAIN=false) instead of retraining,
so the LSTM models run quickly while still exercising the whole pipeline
(scaling, windowing, forecasting, evaluation).
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.data_loading import load_bombay_data  # noqa: E402
from src.model_registry import MODEL_REGISTRY, RunContext  # noqa: E402
from src.preprocessing import preprocess  # noqa: E402


def _make_context(tmp_path: Path) -> RunContext:
    data = load_bombay_data(BACKEND_DIR / "data" / "GlobalLandTemperaturesByMajorCity.csv")
    data = preprocess(data)
    y = data["AverageTemperature"]
    return RunContext(
        train=y[:"2009"],
        test=y["2010":],
        y=y,
        output_dir=tmp_path,
        epochs=1,
        retrain=False,
        model_path_tf=BACKEND_DIR / "models" / "TemperatureForecastingModel.keras",
        model_path_pytorch=BACKEND_DIR / "models" / "TemperatureForecastingModel_pytorch.pt",
    )


def test_arima_runs(tmp_path):
    ctx = _make_context(tmp_path)
    result = MODEL_REGISTRY["arima"].run(ctx)
    assert len(result["forecast"]) == 36
    assert "auto_arima" in result


def test_sarimax_model1_runs(tmp_path):
    ctx = _make_context(tmp_path)
    result = MODEL_REGISTRY["sarimax_model1"].run(ctx)
    assert len(result["forecast"]) == 36
    assert "rmse" in result["metrics"]


def test_sarimax_model2_runs(tmp_path):
    ctx = _make_context(tmp_path)
    result = MODEL_REGISTRY["sarimax_model2"].run(ctx)
    assert len(result["forecast"]) == 36
    assert "rmse" in result["metrics"]


def test_lstm_tensorflow_runs(tmp_path):
    ctx = _make_context(tmp_path)
    result = MODEL_REGISTRY["lstm_tensorflow"].run(ctx)
    assert len(result["forecast"]) > 0
    assert "rmse" in result["metrics"]


def test_lstm_pytorch_runs(tmp_path):
    ctx = _make_context(tmp_path)
    result = MODEL_REGISTRY["lstm_pytorch"].run(ctx)
    assert len(result["forecast"]) > 0
    assert "rmse" in result["metrics"]
    # sanity: PyTorch LSTM should be in a comparable error range to the
    # TensorFlow LSTM on this dataset, not wildly diverging (e.g. broken scaling)
    assert result["metrics"]["rmse"] < 10.0


def test_full_pipeline_seed_run(tmp_path, monkeypatch):
    """Runs run_pipeline.main() end-to-end (all 5 models + EDA) and asserts outputs exist."""
    import json
    import os

    monkeypatch.setenv("DATA_PATH", str(BACKEND_DIR / "data" / "GlobalLandTemperaturesByMajorCity.csv"))
    monkeypatch.setenv("MODEL_PATH", str(BACKEND_DIR / "models" / "TemperatureForecastingModel.keras"))
    monkeypatch.setenv(
        "MODEL_PATH_PYTORCH", str(BACKEND_DIR / "models" / "TemperatureForecastingModel_pytorch.pt")
    )
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("LSTM_RETRAIN", "false")
    monkeypatch.setenv("LSTM_EPOCHS", "1")

    import run_pipeline

    run_pipeline.main()

    assert (tmp_path / "eda.json").exists()
    for model_key in MODEL_REGISTRY:
        result_path = tmp_path / "results" / f"{model_key}.json"
        assert result_path.exists(), f"missing result for {model_key}"
        with open(result_path) as f:
            data = json.load(f)
        assert data.get("forecast"), f"empty forecast for {model_key}"
