"""Compare SARIMAX and LSTM forecasts against the observed data.

Converted from notebook cells 126, 128 (execution order 54-55).

NOTE: matching the original notebook's cell 126, the comparison plot below
overlays SARIMAX **model 1**'s forecast (`pred`, not `pred2`) against the LSTM
forecast -- carried over unchanged, see sarimax_model.py's module docstring
for the related cell-93 quirk. The `/api/metrics` endpoint still reports both
SARIMAX models' RMSE distinctly so this does not create ambiguity in the API.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _points_to_series(points: list[dict], column: str = "value") -> pd.Series:
    index = pd.to_datetime([p["date"] for p in points])
    values = [p["value"] for p in points]
    return pd.Series(values, index=index, name=column)


def plot_comparison(
    y: pd.Series,
    sarimax_model1_forecast_points: list[dict],
    lstm_forecast_points: list[dict],
    output_dir: Path,
) -> None:
    sarimax_series = _points_to_series(sarimax_model1_forecast_points, "SARIMAX Forecast")
    lstm_series = _points_to_series(lstm_forecast_points, "LSTM Forecast")

    plt.figure(figsize=(15, 6))
    ax5 = y["2000":].plot(label="Observed", linewidth=2)
    ax5.fill_between(
        y["2010":].index, [22 for _ in y["2010":]], [36 for _ in y["2010":]], color="k", alpha=0.2
    )
    sarimax_series.plot(ax=ax5, label="SARIMAX Forecast", linewidth=2, linestyle="dashed")
    lstm_series.plot(ax=ax5, label="LSTM Forecast", linewidth=2, linestyle="dashed", color="green")
    ax5.set_xlabel("Date")
    ax5.set_ylabel("Average Temperature")
    plt.legend()
    plt.savefig(output_dir / "comparison_sarimax_vs_lstm.png")
    plt.close()


def summarize(sarimax_rmse: float, lstm_rmse: float) -> str:
    summary = (
        "The SARIMAX Model had an RMSE value of {} whereas the LSTM model had "
        "an RMSE value of {}."
    ).format(round(sarimax_rmse, 2), round(lstm_rmse, 2))
    logger.info(summary)
    return summary


def run_comparison(
    y: pd.Series,
    sarimax_model1_forecast_points: list[dict],
    sarimax_model2_rmse: float,
    lstm_forecast_points: list[dict],
    lstm_rmse: float,
    output_dir: Path,
) -> dict:
    plot_comparison(y, sarimax_model1_forecast_points, lstm_forecast_points, output_dir)
    # The notebook's final printed summary (cell 128) uses whichever SARIMAX
    # RMSE variable was last assigned -- model 2's -- so we mirror that here.
    summary_text = summarize(sarimax_model2_rmse, lstm_rmse)
    return {"summary": summary_text}
