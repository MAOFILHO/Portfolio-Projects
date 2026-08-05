"""Parity and contract tests for the PySpark ETL layer.

The load-bearing test here is test_spark_output_matches_pandas_golden: the
Spark pipeline must reproduce, exactly, what the original pandas pipeline
produced. tests/fixtures/preprocessed_golden.pkl was captured from the pandas
implementation immediately before the migration.

This matters because both LSTM modules refit their StandardScaler from `train`
on every run, including runs that reuse the committed .keras/.pt checkpoints
(lstm_model.py:136-139). Any drift in the series' values, ordering or length
would silently shift predictions against those frozen checkpoints rather than
failing loudly -- so parity is asserted directly, not inferred from model
metrics.

Pickle rather than parquet for the fixture: parquet does not round-trip
DatetimeIndex.freq, and freq='MS' is precisely the contract under test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pyspark.sql.types import DoubleType, StringType, StructField, StructType  # noqa: E402

from src.data_loading import load_bombay_data  # noqa: E402
from src.preprocessing import preprocess  # noqa: E402
from src.spark_session import get_spark, stop_spark  # noqa: E402
from src.validation import DataValidationError, validate_city_slice, validate_raw_data  # noqa: E402

DATA_PATH = BACKEND_DIR / "data" / "GlobalLandTemperaturesByMajorCity.csv"
GOLDEN_PATH = BACKEND_DIR / "tests" / "fixtures" / "preprocessed_golden.pkl"

CITY_SCHEMA = StructType(
    [
        StructField("dt", StringType(), nullable=True),
        StructField("AverageTemperature", DoubleType(), nullable=True),
        StructField("City", StringType(), nullable=True),
        StructField("Country", StringType(), nullable=True),
    ]
)


@pytest.fixture(scope="module")
def spark():
    session = get_spark()
    yield session
    stop_spark()


@pytest.fixture(scope="module")
def preprocessed(spark) -> pd.DataFrame:
    """The Spark pipeline's output, computed once for the whole module."""
    return preprocess(load_bombay_data(DATA_PATH))


@pytest.fixture(scope="module")
def golden() -> pd.DataFrame:
    return pd.read_pickle(GOLDEN_PATH)


# --- the parity check ------------------------------------------------------


def test_spark_output_matches_pandas_golden(preprocessed, golden):
    """Parity with the pre-migration pandas implementation.

    Not check_exact: Spark's CSV double-parser and pandas' C parser convert the
    same decimal string ("29.348") to float64 via different algorithms, landing
    a handful of values one ULP apart (e.g. 29.348000000000006 vs
    29.34800000000001, a ~1e-15 relative difference) -- a parsing artifact, not
    a data discrepancy. rtol=1e-9 catches any real drift (which would show up
    at the 1e-3+ magnitude a genuinely different value or row would produce)
    while tolerating float64 parsing noise many orders of magnitude smaller.
    """
    pd.testing.assert_frame_equal(preprocessed, golden, check_freq=True, rtol=1e-9)


# --- the index contract downstream code depends on -------------------------


def test_index_contract(preprocessed):
    index = preprocessed.index
    # eda.py calls seasonal_decompose(data) with no period=, relying on this freq
    assert index.freqstr == "MS"
    assert index.name == "Date"
    assert isinstance(index, pd.DatetimeIndex)
    assert index.is_monotonic_increasing
    assert not index.has_duplicates


def test_shape_and_column(preprocessed):
    # a single-column DataFrame, not a Series (preprocessing.py's original contract)
    assert list(preprocessed.columns) == ["AverageTemperature"]
    assert preprocessed["AverageTemperature"].dtype == "float64"
    assert len(preprocessed) == 516


def test_trim_bounds_are_end_inclusive(preprocessed):
    assert preprocessed.index[0] == pd.Timestamp("1970-01-01")
    assert preprocessed.index[-1] == pd.Timestamp("2012-12-01")


def test_no_missing_values_in_trimmed_window(preprocessed):
    # adfuller/kpss in eda.py error on NaN, and report_missing_values only reports
    assert preprocessed["AverageTemperature"].isna().sum() == 0


def test_train_test_split_yields_36_test_points(preprocessed):
    """The == 36 assertions in test_smoke.py are a direct function of this split."""
    y = preprocessed["AverageTemperature"]
    assert len(y[:"2009"]) == 480
    assert len(y["2010":]) == 36


# --- validation still fails fast, with unchanged messages ------------------


def test_validate_raw_data_rejects_missing_columns(spark):
    df = spark.createDataFrame([("1970-01-01", 24.5)], schema="dt string, AverageTemperature double")
    with pytest.raises(DataValidationError, match="missing required column"):
        validate_raw_data(df, source="test")


def test_validate_raw_data_rejects_empty_dataset(spark):
    df = spark.createDataFrame([], schema=CITY_SCHEMA)
    with pytest.raises(DataValidationError, match="is empty"):
        validate_raw_data(df, source="test")


def test_validate_city_slice_rejects_unknown_city(spark):
    df = spark.createDataFrame([], schema=CITY_SCHEMA)
    with pytest.raises(DataValidationError, match="No rows found for city"):
        validate_city_slice(df, city="Atlantis", source="test")


def test_validate_city_slice_rejects_unparseable_dates(spark):
    rows = [("not-a-date", 24.5, "Bombay", "India")]
    df = spark.createDataFrame(rows, schema=CITY_SCHEMA)
    with pytest.raises(DataValidationError, match="cannot be parsed as dates"):
        validate_city_slice(df, city="Bombay", source="test")


def test_validate_city_slice_rejects_too_sparse_series(spark):
    rows = [
        ("1970-01-01", 24.5, "Bombay", "India"),
        ("1970-02-01", None, "Bombay", "India"),
        ("1970-03-01", None, "Bombay", "India"),
    ]
    df = spark.createDataFrame(rows, schema=CITY_SCHEMA)
    with pytest.raises(DataValidationError, match="too sparse to forecast reliably"):
        validate_city_slice(df, city="Bombay", source="test")


def test_validate_city_slice_accepts_healthy_series(spark):
    rows = [
        ("1970-01-01", 24.5, "Bombay", "India"),
        ("1970-02-01", 25.1, "Bombay", "India"),
        ("1970-03-01", None, "Bombay", "India"),
    ]
    df = spark.createDataFrame(rows, schema=CITY_SCHEMA)
    validate_city_slice(df, city="Bombay", source="test")  # must not raise
