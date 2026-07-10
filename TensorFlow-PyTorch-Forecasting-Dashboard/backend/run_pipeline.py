"""Seed all five forecasting models once, so the dashboard has data to show on
first load (before the user triggers any live re-run from the UI).

Converted from the notebook `9_5_Bombay_Surface_Temperature_Forecasting.ipynb`.
Writes each model's result to outputs/results/{model_key}.json and all plots
as PNGs into outputs/. Also writes eda.json (independent of any model run).

Usage:
    python run_pipeline.py

Configuration is via environment variables (see .env.example):
    DATA_PATH             path to GlobalLandTemperaturesByMajorCity.csv
    MODEL_PATH             path to save/load the TensorFlow LSTM checkpoint
    MODEL_PATH_PYTORCH     path to save/load the PyTorch LSTM checkpoint
    LSTM_EPOCHS            number of LSTM training epochs (default 10, matches notebook)
    LSTM_RETRAIN           "true"/"false" -- retrain LSTMs or reuse existing checkpoints
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from src.data_loading import load_bombay_data
from src.eda import run_eda
from src.model_registry import MODEL_REGISTRY, RunContext
from src.preprocessing import preprocess
from src.results_store import save_result

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def main() -> None:
    load_dotenv(BACKEND_DIR / ".env")

    data_path = Path(os.getenv("DATA_PATH", BACKEND_DIR / "data" / "GlobalLandTemperaturesByMajorCity.csv"))
    model_path_tf = Path(os.getenv("MODEL_PATH", BACKEND_DIR / "models" / "TemperatureForecastingModel.keras"))
    model_path_pytorch = Path(
        os.getenv("MODEL_PATH_PYTORCH", BACKEND_DIR / "models" / "TemperatureForecastingModel_pytorch.pt")
    )
    output_dir = Path(os.getenv("OUTPUT_DIR", BACKEND_DIR / "outputs"))
    lstm_epochs = int(os.getenv("LSTM_EPOCHS", "10"))
    lstm_retrain = _env_bool("LSTM_RETRAIN", True)

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading and preprocessing data from %s", data_path)
    data = load_bombay_data(data_path)
    data = preprocess(data)

    logger.info("Running exploratory data analysis")
    eda_results = run_eda(data, output_dir)
    with open(output_dir / "eda.json", "w") as f:
        json.dump(eda_results, f, indent=2)

    y = data["AverageTemperature"]
    train = y[:"2009"]
    test = y["2010":]

    ctx = RunContext(
        train=train,
        test=test,
        y=y,
        output_dir=output_dir,
        epochs=lstm_epochs,
        retrain=lstm_retrain,
        model_path_tf=model_path_tf,
        model_path_pytorch=model_path_pytorch,
    )

    for model_key, spec in MODEL_REGISTRY.items():
        logger.info("Running %s (%s)...", spec.display_name, model_key)
        result = spec.run(ctx)
        save_result(output_dir, model_key, result)
        logger.info("%s complete, result saved.", spec.display_name)

    logger.info("Pipeline seed run complete. Results in %s/results/", output_dir)


if __name__ == "__main__":
    main()
