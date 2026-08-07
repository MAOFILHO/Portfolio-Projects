"""Shared helpers for turning pandas time series into JSON-friendly structures."""
from __future__ import annotations

import numpy as np
import pandas as pd


def series_to_points(series: pd.Series) -> list[dict]:
    """Convert a pandas Series with a DatetimeIndex into [{date, value}, ...], dropping NaNs."""
    clean = series.dropna()
    return [
        {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
        for idx, val in clean.items()
    ]


def evaluate_forecast(forecast_mean: pd.Series, truth: pd.Series) -> dict:
    """MSE/RMSE of a forecast against the held-out truth series.

    Shared by every model that scores itself so the comparison across
    ARIMA/SARIMAX/LSTM is genuinely like-for-like -- one definition of the
    metric, not one per model module. Both arguments are expected to carry
    the same DatetimeIndex; pandas aligns on it, so a misaligned forecast
    surfaces as NaN rather than silently scoring against the wrong months.
    """
    aligned_error = (forecast_mean - truth).dropna()
    if aligned_error.empty:
        raise ValueError(
            "Forecast and truth series share no overlapping dates -- cannot score. "
            f"forecast: {forecast_mean.index.min()}..{forecast_mean.index.max()}, "
            f"truth: {truth.index.min()}..{truth.index.max()}"
        )
    mse = float((aligned_error**2).mean())
    return {"mse": mse, "rmse": float(np.sqrt(mse))}
