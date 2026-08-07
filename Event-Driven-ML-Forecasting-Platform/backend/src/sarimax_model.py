"""SARIMAX modelling: two candidate models, diagnostics, forecasts, and MSE/RMSE evaluation.

Converted from notebook cells 78, 80, 83, 85, 87, 89, 91, 93, 95
(execution order 34-42).

NOTE on a carried-over notebook quirk, and how this interactive phase changes
it: in the original notebook, cell 93 ("Visualize Alternative SARIMAX Forecast
on Test Data", intended to zoom in on model 2's forecast) actually plots
`pred.predicted_mean` (model 1's forecast) instead of `pred2.predicted_mean| --
a copy-paste bug, since both models were fit sequentially in one notebook run
and `pred` was still in scope. Now that the dashboard runs each SARIMAX model
independently and on demand (`run_sarimax_model1` / `run_sarimax_model2` below
are separate, independently invocable functions), there is no `pred1` in scope
when model 2 runs on its own, so the zoom plot correctly uses each model's own
forecast. This resolves the earlier-flagged quirk by construction rather than
reproducing it -- documented here and in the project README/CHANGELOG.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .series_utils import evaluate_forecast, series_to_points

logger = logging.getLogger(__name__)

MODEL1_ORDER = (1, 1, 2)
MODEL1_SEASONAL_ORDER = (1, 0, 1, 12)
MODEL2_ORDER = (0, 0, 2)
MODEL2_SEASONAL_ORDER = (1, 0, 1, 12)


def _fit(train: pd.Series, order: tuple, seasonal_order: tuple):
    model = SARIMAX(
        train,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(maxiter=200)
    logger.info("SARIMAX%s x %s summary:\n%s", order, seasonal_order, fitted.summary())
    return fitted


def _plot_diagnostics(fitted_model, output_dir: Path, name: str) -> None:
    fitted_model.plot_diagnostics(figsize=(15, 12))
    plt.savefig(output_dir / f"sarimax_{name}_diagnostics.png")
    plt.close()


def _plot_full_forecast(y: pd.Series, pred, output_dir: Path, filename: str) -> None:
    pred_ci = pred.conf_int()
    ax1 = y["2000":].plot(label="Observed")
    pred.predicted_mean.plot(ax=ax1, label="SARIMAX Forecast", figsize=(15, 6), linestyle="dashed")
    ax1.fill_between(pred_ci.index, pred_ci.iloc[:, 0], pred_ci.iloc[:, 1], color="k", alpha=0.2)
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Average Temperature")
    plt.legend(loc="upper left")
    plt.savefig(output_dir / filename)
    plt.close()


def _plot_zoom_forecast(y: pd.Series, pred, output_dir: Path, filename: str) -> None:
    pred_ci = pred.conf_int()
    ax2 = y["2010":].plot(label="Observed")
    pred.predicted_mean.plot(ax=ax2, label="SARIMAX Forecast", figsize=(15, 6), linestyle="dashed")
    ax2.fill_between(pred_ci.index, pred_ci.iloc[:, 0], pred_ci.iloc[:, 1], color="k", alpha=0.2)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Average Temperature")
    plt.legend()
    plt.savefig(output_dir / filename)
    plt.close()


def _run_one(
    train: pd.Series,
    test: pd.Series,
    y: pd.Series,
    output_dir: Path,
    order: tuple,
    seasonal_order: tuple,
    name: str,
) -> dict:
    fitted = _fit(train, order, seasonal_order)
    _plot_diagnostics(fitted, output_dir, name)
    pred = fitted.get_forecast(steps=36)
    _plot_full_forecast(y, pred, output_dir, f"sarimax_{name}_forecast.png")
    _plot_zoom_forecast(y, pred, output_dir, f"sarimax_{name}_forecast_zoom.png")
    metrics = evaluate_forecast(pred.predicted_mean, test)

    return {
        "order": list(order),
        "seasonal_order": list(seasonal_order),
        "forecast": series_to_points(pred.predicted_mean),
        "confidence_interval_lower": series_to_points(pred.conf_int().iloc[:, 0]),
        "confidence_interval_upper": series_to_points(pred.conf_int().iloc[:, 1]),
        "metrics": metrics,
    }


def run_sarimax_model1(train: pd.Series, test: pd.Series, y: pd.Series, output_dir: Path) -> dict:
    return _run_one(train, test, y, output_dir, MODEL1_ORDER, MODEL1_SEASONAL_ORDER, "model1")


def run_sarimax_model2(train: pd.Series, test: pd.Series, y: pd.Series, output_dir: Path) -> dict:
    return _run_one(train, test, y, output_dir, MODEL2_ORDER, MODEL2_SEASONAL_ORDER, "model2")


def run_sarimax(train: pd.Series, test: pd.Series, y: pd.Series, output_dir: Path) -> dict:
    """Convenience wrapper that runs both SARIMAX models (used by run_pipeline.py's seed run)."""
    return {
        "model1": run_sarimax_model1(train, test, y, output_dir),
        "model2": run_sarimax_model2(train, test, y, output_dir),
    }
