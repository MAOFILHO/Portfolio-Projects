"""Single source of truth mapping model_key -> metadata + run function.

Used by both run_pipeline.py (seeds all models once) and the FastAPI job
layer (api/jobs.py, runs a single model on demand) so there is exactly one
place that knows how to run each model.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from . import arima_model, lstm_model, lstm_pytorch_model, sarimax_model


@dataclass
class RunContext:
    train: pd.Series
    test: pd.Series
    y: pd.Series
    output_dir: Path
    epochs: int = 10
    retrain: bool = True
    model_path_tf: Path | None = None
    model_path_pytorch: Path | None = None


@dataclass
class ModelSpec:
    key: str
    display_name: str
    framework: str
    hyperparams: dict
    run: Callable[[RunContext], dict]


def _run_arima(ctx: RunContext) -> dict:
    return arima_model.run_arima(ctx.train, ctx.y, ctx.output_dir)


def _run_sarimax_model1(ctx: RunContext) -> dict:
    return sarimax_model.run_sarimax_model1(ctx.train, ctx.test, ctx.y, ctx.output_dir)


def _run_sarimax_model2(ctx: RunContext) -> dict:
    return sarimax_model.run_sarimax_model2(ctx.train, ctx.test, ctx.y, ctx.output_dir)


def _run_lstm_tensorflow(ctx: RunContext) -> dict:
    return lstm_model.run_lstm(
        ctx.train,
        ctx.test,
        ctx.y,
        ctx.model_path_tf,
        ctx.output_dir,
        epochs=ctx.epochs,
        retrain=ctx.retrain,
    )


def _run_lstm_pytorch(ctx: RunContext) -> dict:
    return lstm_pytorch_model.run_lstm_pytorch(
        ctx.train,
        ctx.test,
        ctx.y,
        ctx.model_path_pytorch,
        ctx.output_dir,
        epochs=ctx.epochs,
        retrain=ctx.retrain,
    )


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "arima": ModelSpec(
        key="arima",
        display_name="ARIMA (auto-tuned)",
        framework="statsmodels + pmdarima",
        hyperparams={
            "order": "selected by auto_arima (seasonal, m=12, stationary=True)",
            "forecast_horizon_months": 36,
        },
        run=_run_arima,
    ),
    "sarimax_model1": ModelSpec(
        key="sarimax_model1",
        display_name="SARIMAX Model 1",
        framework="statsmodels",
        hyperparams={
            "order": [1, 1, 2],
            "seasonal_order": [1, 0, 1, 12],
            "forecast_horizon_months": 36,
        },
        run=_run_sarimax_model1,
    ),
    "sarimax_model2": ModelSpec(
        key="sarimax_model2",
        display_name="SARIMAX Model 2",
        framework="statsmodels",
        hyperparams={
            "order": [0, 0, 2],
            "seasonal_order": [1, 0, 1, 12],
            "forecast_horizon_months": 36,
        },
        run=_run_sarimax_model2,
    ),
    "lstm_tensorflow": ModelSpec(
        key="lstm_tensorflow",
        display_name="LSTM (TensorFlow / Keras)",
        framework="tensorflow.keras",
        hyperparams={
            "layers": "LSTM(100) -> LSTM(50) -> LSTM(10) -> Dense(64) -> Dense(32) -> Dense(1)",
            "window_size": 60,
            "epochs": 10,
            "optimizer": "adam",
            "loss": "mse",
        },
        run=_run_lstm_tensorflow,
    ),
    "lstm_pytorch": ModelSpec(
        key="lstm_pytorch",
        display_name="LSTM (PyTorch)",
        framework="torch.nn",
        hyperparams={
            "layers": "LSTM(100) -> LSTM(50) -> LSTM(10) -> Linear(64) -> Linear(32) -> Linear(1)",
            "window_size": 60,
            "epochs": 10,
            "optimizer": "Adam",
            "loss": "MSELoss",
        },
        run=_run_lstm_pytorch,
    ),
}


def get_model_spec(model_key: str) -> ModelSpec:
    if model_key not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model_key '{model_key}'. Known keys: {list(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[model_key]
