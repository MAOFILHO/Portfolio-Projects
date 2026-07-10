"""Clean and prepare the Bombay temperature series for time-series modelling.

Converted from notebook cells 20, 22, 24, 28, 30, 34, 36 (execution order 8-16).
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def set_date_index(data: pd.DataFrame) -> pd.DataFrame:
    """Parse the 'dt' column to datetime, set it as index, and assign monthly ('MS') frequency."""
    data = data.copy()
    data["Date"] = pd.to_datetime(data["dt"])
    data.set_index(data["Date"], inplace=True)
    data.index.freq = "MS"
    return data


def select_temperature_column(data: pd.DataFrame) -> pd.DataFrame:
    """Keep only the AverageTemperature column."""
    return pd.DataFrame(data["AverageTemperature"])


def trim_to_reliable_period(data: pd.DataFrame, start: str = "1970", end: str = "2012") -> pd.DataFrame:
    """Drop pre-1970s readings, which used less reliable manual mercury-thermometer measurements."""
    return data[start:end]


def report_missing_values(data: pd.DataFrame) -> pd.DataFrame:
    """Compute count and percentage of missing values per column."""
    total = data.isnull().sum().sort_values(ascending=False)
    percent = (data.isnull().sum() * 100 / data.isnull().count()).sort_values(ascending=False)
    missing_data = pd.concat([total, percent], axis=1, keys=["Total", "Percentage of Missing Values"])
    logger.info("Missing value report:\n%s", missing_data)
    return missing_data


def preprocess(data: pd.DataFrame) -> pd.DataFrame:
    """End-to-end preprocessing pipeline for the Bombay temperature series."""
    data = set_date_index(data)
    data = select_temperature_column(data)
    data = trim_to_reliable_period(data)
    report_missing_values(data)
    logger.info("Preprocessed data preview:\n%s", data.head())
    return data
