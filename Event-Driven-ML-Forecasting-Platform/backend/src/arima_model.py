"""ARIMA / auto-ARIMA hyperparameter search and a plain ARIMA(0,0,2) forecast.

Converted from notebook cells 60, 64, 66, 70, 72, 74 (execution order 25, 27, 28, 30-32).
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from pmdarima.arima import auto_arima
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.arima.model import ARIMA

from .series_utils import evaluate_forecast, series_to_points

logger = logging.getLogger(__name__)


def run_auto_arima(train: pd.Series) -> dict:
    """Find optimal seasonal ARIMA hyperparameters via a full grid search."""
    model = auto_arima(
        train, seasonal=True, m=12, stationary=True, stepwise=False, trace=1, random_state=10
    )
    logger.info("auto_arima selected order=%s seasonal_order=%s", model.order, model.seasonal_order)
    return {"order": list(model.order), "seasonal_order": list(model.seasonal_order)}


def plot_acf_pacf(train: pd.Series, output_dir: Path, lags: int = 40) -> None:
    plot_acf(train, title="Autocorrelation plot for q values", lags=lags)
    plt.savefig(output_dir / "acf.png")
    plt.close()

    plot_pacf(train, title="Partial Autocorrelation: To determine p value", lags=lags, method="ywm")
    plt.savefig(output_dir / "pacf.png")
    plt.close()


def fit_and_forecast_arima(
    train: pd.Series, test: pd.Series, y: pd.Series, output_dir: Path, steps: int = 36
) -> dict:
    """Fit ARIMA(0,0,2) on the training data and forecast `steps` months ahead.

    The notebook plots this forecast twice (cells 72 and 74) with near-identical
    code; both are preserved here as separate saved images.

    Scored against `test` with the same shared `evaluate_forecast()` helper
    SARIMAX and both LSTMs use -- the notebook never computed error metrics
    for this model, which left ARIMA as the one entry in the dashboard's
    comparison view with no MSE/RMSE to compare against.
    """
    model = ARIMA(train, order=(0, 0, 2))
    results = model.fit()
    pred = results.get_forecast(steps=steps)
    pred_ci = pred.conf_int()

    for suffix in ("1", "2"):
        ax1 = y["2000":].plot(label="Observed")
        pred.predicted_mean.plot(ax=ax1, label="ARIMA Forecast", figsize=(15, 6), linestyle="dashed")
        ax1.fill_between(pred_ci.index, pred_ci.iloc[:, 0], pred_ci.iloc[:, 1], color="k", alpha=0.2)
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Average Temperature")
        plt.legend(loc="upper left")
        plt.savefig(output_dir / f"arima_forecast_{suffix}.png")
        plt.close()

    return {
        "forecast": series_to_points(pred.predicted_mean),
        "confidence_interval_lower": series_to_points(pred_ci.iloc[:, 0]),
        "confidence_interval_upper": series_to_points(pred_ci.iloc[:, 1]),
        "metrics": evaluate_forecast(pred.predicted_mean, test),
    }


def run_arima(train: pd.Series, test: pd.Series, y: pd.Series, output_dir: Path) -> dict:
    auto_arima_result = run_auto_arima(train)
    plot_acf_pacf(train, output_dir)
    forecast = fit_and_forecast_arima(train, test, y, output_dir)
    return {"auto_arima": auto_arima_result, **forecast}
