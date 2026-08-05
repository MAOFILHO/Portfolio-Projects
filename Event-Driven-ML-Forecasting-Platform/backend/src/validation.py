"""Fail-fast data quality checks for the raw temperature dataset.

Runs once, right after the CSV is read by Spark, so a malformed or unexpected
input file surfaces a clear error immediately (in a well-labeled exception)
rather than failing deep inside statsmodels/Keras/PyTorch with a confusing
stack trace several pipeline stages later. This is what makes the pipeline
"robust" across every downstream model (statistical and both DL frameworks
consume the same validated, structured data).

These checks operate on Spark DataFrames -- Spark is the sole ingest engine
(see spark_session.py). Each function deliberately collects its checks into a
single .agg() pass so validation costs one Spark job rather than one per rule.
The exception type and every message string are unchanged from the original
pandas implementation.
"""
from __future__ import annotations

import logging

from pyspark.sql import DataFrame, functions as F

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"dt", "AverageTemperature", "City", "Country"}
MAX_MISSING_TEMPERATURE_RATIO = 0.5

# The dataset's 'dt' column is ISO date text ("1849-01-01"). Parsed with an
# explicit format under CORRECTED time-parser policy, anything malformed
# becomes NULL rather than being silently coerced -- which is what lets the
# unparseable-date check below actually detect bad input.
DATE_FORMAT = "yyyy-MM-dd"


class DataValidationError(ValueError):
    """Raised when the raw dataset fails a structural or quality check."""


def _is_empty(df: DataFrame) -> bool:
    """Cheap emptiness test -- stops after one row instead of counting all of them."""
    return len(df.take(1)) == 0


def validate_raw_data(df: DataFrame, source: str) -> None:
    if _is_empty(df):
        raise DataValidationError(f"Dataset at {source} is empty.")

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise DataValidationError(
            f"Dataset at {source} is missing required column(s): {sorted(missing_columns)}. "
            f"Expected at least: {sorted(REQUIRED_COLUMNS)}."
        )

    logger.info("Validated raw dataset schema (%d rows) from %s", df.count(), source)


def validate_city_slice(df: DataFrame, city: str, source: str) -> None:
    if _is_empty(df):
        raise DataValidationError(
            f"No rows found for city='{city}' in {source}. Check the City column values."
        )

    parsed = F.to_timestamp(F.col("dt"), DATE_FORMAT)

    # One pass for every remaining check.
    stats = df.agg(
        F.count(F.lit(1)).alias("n_rows"),
        # 'dt' present but unparseable as a date
        F.sum(F.when(F.col("dt").isNotNull() & parsed.isNull(), 1).otherwise(0)).alias("n_unparseable"),
        F.countDistinct(F.col("dt")).alias("n_distinct_dt"),
        F.sum(F.col("AverageTemperature").isNull().cast("int")).alias("n_missing_temp"),
    ).collect()[0]

    if stats["n_unparseable"] > 0:
        raise DataValidationError(
            f"Column 'dt' for city='{city}' contains values that cannot be parsed as dates."
        )

    # pandas' Series.duplicated().sum() counts every row that repeats an earlier
    # one, which is exactly (total rows - distinct values).
    n_duplicates = stats["n_rows"] - stats["n_distinct_dt"]
    if n_duplicates > 0:
        logger.warning(
            "City='%s' has %d duplicate date entries -- later rows will overwrite earlier "
            "ones once 'dt' is set as the index.",
            city,
            int(n_duplicates),
        )

    missing_ratio = stats["n_missing_temp"] / stats["n_rows"]
    if missing_ratio > MAX_MISSING_TEMPERATURE_RATIO:
        raise DataValidationError(
            f"City='{city}' has {missing_ratio:.0%} missing AverageTemperature values "
            f"(threshold {MAX_MISSING_TEMPERATURE_RATIO:.0%}) -- too sparse to forecast reliably."
        )

    logger.info(
        "Validated city='%s' slice (%d rows, %.1f%% missing temperature values)",
        city,
        stats["n_rows"],
        missing_ratio * 100,
    )
