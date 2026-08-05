"""Clean and prepare the Bombay temperature series for time-series modelling.

Converted from notebook cells 20, 22, 24, 28, 30, 34, 36 (execution order
8-16), then migrated from pandas to PySpark.

This module is the boundary of the Spark layer. Spark does the date parsing,
column selection and period trim; preprocess() then performs the project's
single .toPandas() handoff and rebuilds the pandas index contract that
everything downstream depends on:

    a single-column DataFrame named 'AverageTemperature', indexed by a
    DatetimeIndex named 'Date' with freq='MS'

That freq is load-bearing, not cosmetic. eda.py calls seasonal_decompose(data)
with no explicit period= and relies on it to infer period=12, and statsmodels'
get_forecast(steps=36) uses it to emit a real future monthly DatetimeIndex --
without it, series_utils.series_to_points() hits a RangeIndex and raises
AttributeError on .strftime.
"""
from __future__ import annotations

import logging

import pandas as pd
from pyspark.sql import DataFrame, functions as F

from .validation import DATE_FORMAT, DataValidationError

logger = logging.getLogger(__name__)

TEMPERATURE_COLUMN = "AverageTemperature"
DATE_COLUMN = "Date"
FREQUENCY = "MS"


def set_date_index(data: DataFrame) -> DataFrame:
    """Parse the 'dt' column to a timestamp column named 'Date'.

    Spark has no row index, so the pandas notion of "set the index" is deferred
    to the handoff in preprocess(); here we only materialise the parsed column.
    """
    return data.withColumn(DATE_COLUMN, F.to_timestamp(F.col("dt"), DATE_FORMAT))


def select_temperature_column(data: DataFrame) -> DataFrame:
    """Keep only the Date and AverageTemperature columns."""
    return data.select(DATE_COLUMN, TEMPERATURE_COLUMN)


def trim_to_reliable_period(data: DataFrame, start: str = "1970", end: str = "2012") -> DataFrame:
    """Drop pre-1970s readings, which used less reliable manual mercury-thermometer measurements.

    `start`/`end` are years, and the range is inclusive of both -- matching the
    end-inclusive semantics of the pandas partial-string slice data["1970":"2012"]
    this replaced. That bound is what yields exactly 36 test points for 2010+.
    """
    return data.filter(F.year(F.col(DATE_COLUMN)).between(int(start), int(end)))


def report_missing_values(data: DataFrame) -> pd.DataFrame:
    """Compute count and percentage of missing values per column."""
    columns = [c for c in data.columns if c != DATE_COLUMN]
    aggregations = [F.count(F.lit(1)).alias("__n_rows")]
    for column in columns:
        aggregations.append(F.sum(F.col(column).isNull().cast("int")).alias(column))
    stats = data.agg(*aggregations).collect()[0]

    n_rows = stats["__n_rows"]
    totals = {column: int(stats[column]) for column in columns}
    percentages = {
        column: (totals[column] * 100 / n_rows) if n_rows else 0.0 for column in columns
    }

    missing_data = pd.concat(
        [
            pd.Series(totals, name="Total"),
            pd.Series(percentages, name="Percentage of Missing Values"),
        ],
        axis=1,
    ).sort_values("Total", ascending=False)
    logger.info("Missing value report:\n%s", missing_data)
    return missing_data


def _to_pandas_series_frame(data: DataFrame) -> pd.DataFrame:
    """The single Spark -> pandas handoff, plus index-contract reconstruction."""
    # Spark makes no ordering guarantee; without this the DatetimeIndex comes
    # back shuffled and the freq assignment below fails outright.
    pdf = data.orderBy(DATE_COLUMN).toPandas()

    # Arrow-enabled toPandas() (spark.sql.execution.arrow.pyspark.enabled) hands
    # back timestamps as datetime64[us] under pandas 2.x, and pd.to_datetime()
    # on an already-datetime column preserves that unit rather than coercing to
    # the project's original datetime64[ns]. Cast explicitly so the index dtype
    # matches what every consumer (and the golden fixture) was built against.
    pdf[DATE_COLUMN] = pd.to_datetime(pdf[DATE_COLUMN]).astype("datetime64[ns]")
    pdf = pdf.set_index(DATE_COLUMN).sort_index()

    n_observations = len(pdf)
    # asfreq both stamps freq='MS' and proves the series is gap-free: any missing
    # month would appear here as an inserted all-NaN row.
    pdf = pdf.asfreq(FREQUENCY)
    if len(pdf) != n_observations:
        raise DataValidationError(
            f"Temperature series is not contiguous at monthly ('{FREQUENCY}') frequency: "
            f"{len(pdf) - n_observations} month(s) are missing between "
            f"{pdf.index[0]:%Y-%m} and {pdf.index[-1]:%Y-%m}. "
            "Downstream seasonal decomposition and forecasting require a gap-free series."
        )

    return pdf[[TEMPERATURE_COLUMN]]


def preprocess(data: DataFrame) -> pd.DataFrame:
    """End-to-end preprocessing for the Bombay temperature series.

    Takes a Spark DataFrame (from data_loading.load_bombay_data) and returns the
    pandas single-column DataFrame every downstream consumer expects.
    """
    data = set_date_index(data)
    data = select_temperature_column(data)
    data = trim_to_reliable_period(data)
    report_missing_values(data)
    result = _to_pandas_series_frame(data)
    logger.info("Preprocessed data preview:\n%s", result.head())
    return result
