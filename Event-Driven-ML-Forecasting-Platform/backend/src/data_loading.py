"""Load the global temperature dataset and narrow it down to Bombay (Mumbai).

Converted from notebook cells 10, 12, 14, 16, 18 (execution order 3-7), then
migrated from pandas to PySpark -- Spark is the sole ingest engine for this
project (see spark_session.py and docs/ARCHITECTURE.md).

Every function here returns a Spark DataFrame. The single handoff back to
pandas happens at the end of preprocessing.preprocess(), because everything
downstream (eda.py, statsmodels, both LSTM modules) requires real pandas
objects.
"""
from __future__ import annotations

import logging
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

from .spark_session import get_spark
from .validation import validate_city_slice, validate_raw_data

logger = logging.getLogger(__name__)

# Declared rather than inferred: inferSchema costs a second full pass over the
# file, and an explicit DoubleType pins AverageTemperature to the same float64
# pandas produced before the migration. 'dt' stays a string so validation.py
# can detect values that fail to parse as dates -- reading it as DateType
# would silently null them out before validation ever saw them.
RAW_SCHEMA = StructType(
    [
        StructField("dt", StringType(), nullable=True),
        StructField("AverageTemperature", DoubleType(), nullable=True),
        StructField("AverageTemperatureUncertainty", DoubleType(), nullable=True),
        StructField("City", StringType(), nullable=True),
        StructField("Country", StringType(), nullable=True),
        StructField("Latitude", StringType(), nullable=True),
        StructField("Longitude", StringType(), nullable=True),
    ]
)


def _log_preview(df: DataFrame, label: str, n: int = 5) -> None:
    """Log the first n rows, but only if INFO logging would actually emit it.

    Spark is lazy, so an unconditional preview would trigger a real job on every
    call just to produce a log line nobody reads.
    """
    if logger.isEnabledFor(logging.INFO):
        logger.info("%s:\n%s", label, df.limit(n).toPandas())


def load_raw_data(data_path: str | Path) -> DataFrame:
    """Read the raw GlobalLandTemperaturesByMajorCity CSV into a Spark DataFrame."""
    data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {data_path}. Set DATA_PATH to the correct location."
        )
    spark = get_spark()
    raw_data = spark.read.csv(str(data_path), header=True, schema=RAW_SCHEMA)
    validate_raw_data(raw_data, source=str(data_path))
    logger.info("Loaded raw dataset: columns=%s", raw_data.columns)
    _log_preview(raw_data, "Raw data preview")
    return raw_data


def filter_india(raw_data: DataFrame) -> DataFrame:
    """Filter the dataset to rows where Country == 'India'."""
    ind_df = raw_data.filter(raw_data["Country"] == "India")
    if logger.isEnabledFor(logging.INFO):
        cities = sorted(row["City"] for row in ind_df.select("City").distinct().collect())
        logger.info("India cities available: %s", cities)
    return ind_df


def select_bombay(raw_data: DataFrame, source: str = "<unknown>") -> DataFrame:
    """Filter the full dataset down to Bombay (Mumbai) records.

    The result is cached: it is small (~2.6k rows) and is read several times --
    once by validation, then again by preprocessing -- so caching avoids
    re-scanning the 13MB source CSV for each.
    """
    data = raw_data[raw_data.City == "Bombay"].cache()
    validate_city_slice(data, city="Bombay", source=source)
    _log_preview(data, "Bombay data preview")
    return data


def load_bombay_data(data_path: str | Path) -> DataFrame:
    """End-to-end: read CSV, filter to India, select Bombay, return a Spark DataFrame."""
    raw_data = load_raw_data(data_path)
    filter_india(raw_data)  # kept for parity with notebook's exploratory step / logging
    return select_bombay(raw_data, source=str(data_path))
