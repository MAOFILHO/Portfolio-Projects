"""Unit tests for the Kafka consumer's windowing/aggregation logic.

No broker, no live streaming query, and no Kafka connector jar: these tests
exercise build_windowed_aggregation() directly against a static batch
DataFrame with the same schema src.kafka_consumer.read_kafka_stream() would
produce from a live source. This is exactly why that function is a pure
transform in the first place -- see its module docstring.

Uses the existing ETL SparkSession singleton (src.spark_session.get_spark),
not get_streaming_spark(), because these tests never touch Kafka and so don't
need the spark-sql-kafka-0-10 connector package or its Maven resolution.
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.kafka_consumer import MESSAGE_SCHEMA, build_windowed_aggregation  # noqa: E402
from src.spark_session import get_spark, stop_spark  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    session = get_spark()
    yield session
    stop_spark()


def _batch_df(spark, rows):
    """rows: list of (dt, temp, city, country, kafka_ingest_time) tuples."""
    from pyspark.sql.types import StructField, StructType, TimestampType

    schema = StructType(MESSAGE_SCHEMA.fields + [StructField("kafka_ingest_time", TimestampType(), True)])
    return spark.createDataFrame(rows, schema=schema)


def test_groups_by_city_and_window(spark):
    t = datetime.datetime(2026, 1, 1, 0, 0, 0)
    rows = [
        ("1970-01-01", 24.0, "Bombay", "India", t),
        ("1970-02-01", 26.0, "Bombay", "India", t + datetime.timedelta(seconds=1)),
        ("1970-01-01", 10.0, "London", "UK", t),
    ]
    result = build_windowed_aggregation(_batch_df(spark, rows)).collect()

    by_city = {row["city"]: row for row in result}
    assert set(by_city) == {"Bombay", "London"}
    assert by_city["Bombay"]["event_count"] == 2
    assert by_city["Bombay"]["avg_temperature"] == pytest.approx(25.0)
    assert by_city["Bombay"]["min_temperature"] == pytest.approx(24.0)
    assert by_city["Bombay"]["max_temperature"] == pytest.approx(26.0)
    assert by_city["London"]["event_count"] == 1


def test_filters_out_null_temperature_and_city(spark):
    t = datetime.datetime(2026, 1, 1, 0, 0, 0)
    rows = [
        ("1970-01-01", 24.0, "Bombay", "India", t),
        ("1970-01-01", None, "Bombay", "India", t),  # missing reading, must be excluded
        ("1970-01-01", 30.0, None, "India", t),  # missing city, must be excluded
    ]
    result = build_windowed_aggregation(_batch_df(spark, rows)).collect()

    assert len(result) == 1
    assert result[0]["city"] == "Bombay"
    assert result[0]["event_count"] == 1
    assert result[0]["avg_temperature"] == pytest.approx(24.0)


def test_separate_tumbling_windows_stay_separate(spark):
    """Two events 20s apart (> the 10s window) land in different windows, not merged."""
    t = datetime.datetime(2026, 1, 1, 0, 0, 0)
    rows = [
        ("1970-01-01", 20.0, "Bombay", "India", t),
        ("1970-01-01", 40.0, "Bombay", "India", t + datetime.timedelta(seconds=20)),
    ]
    result = build_windowed_aggregation(_batch_df(spark, rows)).collect()

    assert len(result) == 2
    for row in result:
        assert row["event_count"] == 1
    windows = sorted((row["window_start"], row["window_end"]) for row in result)
    assert windows[0][1] <= windows[1][0]  # first window ends at/before the second starts


def test_output_schema(spark):
    t = datetime.datetime(2026, 1, 1, 0, 0, 0)
    result = build_windowed_aggregation(_batch_df(spark, [("1970-01-01", 24.0, "Bombay", "India", t)]))
    assert result.columns == [
        "city",
        "window_start",
        "window_end",
        "avg_temperature",
        "min_temperature",
        "max_temperature",
        "event_count",
    ]


def test_empty_source_yields_empty_result(spark):
    result = build_windowed_aggregation(_batch_df(spark, []))
    assert result.count() == 0
