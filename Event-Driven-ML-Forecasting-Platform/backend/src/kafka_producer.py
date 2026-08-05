"""Replay the full temperature dataset onto Kafka as simulated real-time telemetry.

This is a standalone script, not part of the FastAPI app lifecycle or the
Spark ETL pipeline (src/data_loading.py) -- it exists purely to generate a
live event stream for kafka_consumer.py to demonstrate against. Every city in
the CSV is replayed (~239k rows), not just Bombay, since the streaming layer
is a general-purpose telemetry demo independent of the dashboard's Bombay
forecasting scope.

Usage:
    python src/kafka_producer.py                # full replay, ~8 min at the default rate
    python src/kafka_producer.py --limit 2000    # quick smoke run

Row-building is split into a pure function (_row_to_message) precisely so it
can be unit-tested without a running broker -- see tests/test_kafka_producer.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
from confluent_kafka import KafkaException, Producer
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_PATH = Path(os.getenv("DATA_PATH", BACKEND_DIR / "data" / "GlobalLandTemperaturesByMajorCity.csv"))
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "temperature-telemetry")
DEFAULT_RATE = float(os.getenv("KAFKA_PRODUCER_RATE", "500"))  # messages/sec


def _row_to_message(row: pd.Series) -> dict:
    """Convert one CSV row to the JSON payload published to Kafka.

    A pure function so producer logic is testable without a broker: given a
    row, this always returns the same dict, independent of Kafka, timing, or
    I/O. `dt` is carried through as a plain string field (the historical
    observation date) -- kafka_consumer.py deliberately does NOT window on it
    (see its module docstring); windowing uses Kafka ingestion time instead.
    NaN AverageTemperature values (present in the raw dataset) are passed
    through as JSON null rather than dropped, matching upstream row fidelity.
    """
    value = row["AverageTemperature"]
    return {
        "dt": None if pd.isna(row["dt"]) else str(row["dt"]),
        "AverageTemperature": None if pd.isna(value) else float(value),
        "City": None if pd.isna(row["City"]) else str(row["City"]),
        "Country": None if pd.isna(row["Country"]) else str(row["Country"]),
    }


def _make_producer() -> Producer:
    return Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})


def _delivery_callback(err, msg) -> None:
    if err is not None:
        logger.error("Delivery failed for record %s: %s", msg.key(), err)


def replay(
    producer: Producer,
    data_path: Path,
    *,
    topic: str = TOPIC,
    rate_per_sec: float = DEFAULT_RATE,
    limit: int | None = None,
) -> int:
    """Stream rows from `data_path` onto `topic` at approximately `rate_per_sec` msg/s.

    Returns the number of messages successfully queued for delivery.
    """
    df = pd.read_csv(data_path)
    if limit is not None:
        df = df.head(limit)

    interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
    sent = 0

    logger.info("Replaying %d rows from %s onto topic '%s' at ~%.0f msg/s", len(df), data_path, topic, rate_per_sec)

    for _, row in df.iterrows():
        message = _row_to_message(row)
        producer.produce(
            topic,
            key=message["City"] or "unknown",
            value=json.dumps(message),
            callback=_delivery_callback,
        )
        sent += 1

        # poll(0) drains delivery-report callbacks without blocking, which
        # also keeps producer.produce()'s internal queue from filling up on
        # a long replay.
        producer.poll(0)

        if interval:
            time.sleep(interval)

        if sent % 10_000 == 0:
            logger.info("Sent %d/%d rows", sent, len(df))

    producer.flush(timeout=30)
    logger.info("Replay complete: %d messages sent", sent)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Replay only the first N rows (for a quick smoke test).")
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE, help="Target messages per second.")
    parser.add_argument("--topic", type=str, default=TOPIC)
    args = parser.parse_args()

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}. Set DATA_PATH to the correct location.")

    producer = _make_producer()
    try:
        replay(producer, DATA_PATH, topic=args.topic, rate_per_sec=args.rate, limit=args.limit)
    except KafkaException as exc:
        logger.error(
            "Could not reach Kafka at %s (%s). Is the broker running? Try: docker compose up -d", BOOTSTRAP_SERVERS, exc
        )
        raise


if __name__ == "__main__":
    main()
