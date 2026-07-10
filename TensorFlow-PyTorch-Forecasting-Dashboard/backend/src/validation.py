"""Fail-fast data quality checks for the raw temperature dataset.

Runs once, right after the CSV is loaded, so a malformed or unexpected input
file surfaces a clear error immediately (in a well-labeled exception) rather
than failing deep inside pandas/statsmodels/Keras/PyTorch with a confusing
stack trace several pipeline stages later. This is what makes the pipeline
"robust" across every downstream model (statistical and both DL frameworks
consume the same validated, structured DataFrame).
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"dt", "AverageTemperature", "City", "Country"}
MAX_MISSING_TEMPERATURE_RATIO = 0.5


class DataValidationError(ValueError):
    """Raised when the raw dataset fails a structural or quality check."""


def validate_raw_data(df: pd.DataFrame, source: str) -> None:
    if df.empty:
        raise DataValidationError(f"Dataset at {source} is empty.")

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise DataValidationError(
            f"Dataset at {source} is missing required column(s): {sorted(missing_columns)}. "
            f"Expected at least: {sorted(REQUIRED_COLUMNS)}."
        )

    logger.info("Validated raw dataset schema (%d rows) from %s", len(df), source)


def validate_city_slice(df: pd.DataFrame, city: str, source: str) -> None:
    if df.empty:
        raise DataValidationError(
            f"No rows found for city='{city}' in {source}. Check the City column values."
        )

    try:
        parsed_dates = pd.to_datetime(df["dt"], errors="raise")
    except (ValueError, TypeError) as exc:
        raise DataValidationError(
            f"Column 'dt' for city='{city}' contains values that cannot be parsed as dates."
        ) from exc

    if parsed_dates.duplicated().any():
        logger.warning(
            "City='%s' has %d duplicate date entries -- later rows will overwrite earlier "
            "ones once 'dt' is set as the index.",
            city,
            int(parsed_dates.duplicated().sum()),
        )

    missing_ratio = df["AverageTemperature"].isna().mean()
    if missing_ratio > MAX_MISSING_TEMPERATURE_RATIO:
        raise DataValidationError(
            f"City='{city}' has {missing_ratio:.0%} missing AverageTemperature values "
            f"(threshold {MAX_MISSING_TEMPERATURE_RATIO:.0%}) -- too sparse to forecast reliably."
        )

    logger.info(
        "Validated city='%s' slice (%d rows, %.1f%% missing temperature values)",
        city,
        len(df),
        missing_ratio * 100,
    )
