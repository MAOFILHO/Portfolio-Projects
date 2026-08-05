"""Exploratory data analysis: trend plots, moving averages, seasonal decomposition,
and stationarity tests (ADF + KPSS).

Converted from notebook cells 41, 43, 45, 47, 50 (execution order 18, 19, 20, 21, 22).
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # non-interactive backend; notebook's inline display becomes savefig()
import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller, kpss

from .series_utils import series_to_points

logger = logging.getLogger(__name__)


def plot_observed_temperature(data: pd.DataFrame, output_dir: Path) -> None:
    data.plot(figsize=(15, 6), legend=None)
    plt.xlabel("Date", fontsize=14)
    plt.ylabel("Temperature", fontsize=14)
    plt.title("Observed Monthly Average Temperature", fontsize=15)
    plt.savefig(output_dir / "observed_temperature.png")
    plt.close()


def compute_moving_averages(data: pd.DataFrame, output_dir: Path) -> dict:
    yearly = data["AverageTemperature"].rolling(window=12).mean()
    fiveyearly = data["AverageTemperature"].rolling(window=60).mean()

    ma_ax = yearly["1975":].plot(figsize=(15, 6), label="12-Month Moving Average")
    fiveyearly["1975":].plot(ax=ma_ax, color="red", label="5-Year Moving Average")
    plt.xlabel("Date", fontsize=14)
    plt.ylabel("Temperature", fontsize=14)
    plt.title("Surface Temperature Moving Averages", fontsize=15)
    plt.legend()
    plt.savefig(output_dir / "moving_averages.png")
    plt.close()

    return {
        "twelve_month": series_to_points(yearly["1975":]),
        "five_year": series_to_points(fiveyearly["1975":]),
    }


def compute_seasonal_decomposition(data: pd.DataFrame, output_dir: Path) -> dict:
    decomposition = seasonal_decompose(data)

    for name, component, color in [
        ("observed", decomposition.observed, None),
        ("trend", decomposition.trend, "green"),
        ("seasonal", decomposition.seasonal, "black"),
        ("residual", decomposition.resid, "red"),
    ]:
        plt.figure(figsize=(15, 4))
        plt.plot(component, label=name.capitalize(), color=color)
        plt.xlabel("Date", fontsize=14)
        plt.ylabel("Monthly Average", fontsize=14)
        plt.legend(loc="best")
        plt.title(f"{name.capitalize()} Component", fontsize=15)
        plt.savefig(output_dir / f"seasonal_decompose_{name}.png")
        plt.close()

    return {
        "observed": series_to_points(decomposition.observed),
        "trend": series_to_points(decomposition.trend),
        "seasonal": series_to_points(decomposition.seasonal),
        "residual": series_to_points(decomposition.resid),
    }


def adf_test(timeseries: pd.DataFrame) -> dict:
    """Augmented Dickey-Fuller stationarity test."""
    result = adfuller(timeseries, autolag="AIC")
    stats = pd.Series(
        result[0:4],
        index=["Test Statistic", "p-value", "No. of Lags Used", "Number of Observations Used"],
    )
    logger.info("ADF test results:\n%s", stats)
    is_stationary = result[1] <= 0.05
    return {
        "test_statistic": float(result[0]),
        "p_value": float(result[1]),
        "lags_used": int(result[2]),
        "num_observations": int(result[3]),
        "is_stationary": bool(is_stationary),
    }


def kpss_test(timeseries: pd.DataFrame) -> dict:
    """Kwiatkowski-Phillips-Schmidt-Shin stationarity test."""
    kpss_result = kpss(timeseries, regression="c", nlags="legacy")
    output = {
        "test_statistic": float(kpss_result[0]),
        "p_value": float(kpss_result[1]),
        "lags_used": int(kpss_result[2]),
        "critical_values": {k: float(v) for k, v in kpss_result[3].items()},
        "is_stationary": bool(kpss_result[1] > 0.05),
    }
    logger.info("KPSS test results: %s", output)
    return output


def run_eda(data: pd.DataFrame, output_dir: Path) -> dict:
    """Run the full EDA stage and return everything needed for the API/frontend."""
    plot_observed_temperature(data, output_dir)
    moving_averages = compute_moving_averages(data, output_dir)
    seasonal_decomposition = compute_seasonal_decomposition(data, output_dir)
    stationarity = {
        "adf": adf_test(data),
        "kpss": kpss_test(data),
    }
    return {
        "observed": series_to_points(data["AverageTemperature"]),
        "moving_averages": moving_averages,
        "seasonal_decomposition": seasonal_decomposition,
        "stationarity": stationarity,
    }
