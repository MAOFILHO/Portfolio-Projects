"""PySpark Structured Streaming consumer: maintains live windowed temperature
features per city from the Kafka telemetry topic.

Standalone script, own SparkSession, own process -- run with
`python src/kafka_consumer.py`, independent of the FastAPI app and the batch
ETL pipeline (src/data_loading.py / src/preprocessing.py).

Why a separate SparkSession from spark_session.get_spark(): that singleton is
used on every dashboard request (api/main.py's cached preprocessing), and
adding this module's Kafka connector packages there would force every
API-serving session to resolve spark-sql-kafka-0-10 and its transitive jars
via Maven on first use -- slow, and unnecessary for anyone not streaming. This
module's session is built once, here, for the lifetime of this process only.

Why windowing is on Kafka ingestion time, not the payload's historical `dt`:
the CSV's `dt` values span 1743-2013. Replayed at demo speed, using `dt` as
Spark's event-time watermark would mean each micro-batch jumps centuries,
which breaks watermarking outright (every batch would arrive "late" relative
to the last watermark). Windowing on ingestion time instead measures what a
telemetry pipeline actually monitors: real throughput and per-city stats
arriving over wall-clock time. `dt` is carried through as a payload field for
display, not used for windowing.

build_windowed_aggregation() is a pure DataFrame -> DataFrame transform,
deliberately decoupled from the Kafka read, so it can be unit-tested against
a static batch DataFrame with the same schema -- no live broker needed. See
tests/test_kafka_consumer.py.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from confluent_kafka.admin import AdminClient, NewTopic
from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "temperature-telemetry")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BACKEND_DIR / "outputs"))
STREAMING_OUTPUT_DIR = Path(os.getenv("STREAMING_OUTPUT_DIR", OUTPUT_DIR / "streaming"))
WINDOWED_FEATURES_PATH = STREAMING_OUTPUT_DIR / "windowed_features"
CHECKPOINT_PATH = STREAMING_OUTPUT_DIR / "_checkpoints" / "windowed_features"

# spark-sql-kafka-0-10's Scala/Spark version must match the pyspark build
# exactly (requirements.txt pins pyspark[sql]==3.5.9, Scala 2.12).
KAFKA_CONNECTOR_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9"

WINDOW_DURATION = "10 seconds"

# Matches src/kafka_producer.py's _row_to_message() output exactly.
MESSAGE_SCHEMA = StructType(
    [
        StructField("dt", StringType(), nullable=True),
        StructField("AverageTemperature", DoubleType(), nullable=True),
        StructField("City", StringType(), nullable=True),
        StructField("Country", StringType(), nullable=True),
    ]
)


def ensure_topic_exists(bootstrap_servers: str = BOOTSTRAP_SERVERS, topic: str = TOPIC, timeout: float = 15.0) -> None:
    """Explicitly create the topic if it doesn't exist yet, and block until it's visible.

    KAFKA_AUTO_CREATE_TOPICS_ENABLE=true (docker-compose.yml) only creates a
    topic on the first *produce* to it -- a consumer subscribing before any
    message has ever been sent hits UnknownTopicOrPartitionException, and
    Spark's Kafka source treats that as fatal (it does not wait/retry), which
    kills the whole streaming query. Creating the topic explicitly here makes
    consumer startup correct regardless of whether the producer has run yet.
    """
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})

    if topic in admin.list_topics(timeout=timeout).topics:
        return

    futures = admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
    for created_topic, future in futures.items():
        try:
            future.result(timeout=timeout)
            logger.info("Created topic '%s'", created_topic)
        except Exception as exc:  # noqa: BLE001 - includes the "already exists" race, which is fine
            if "already exists" not in str(exc).lower():
                raise


def get_streaming_spark() -> SparkSession:
    """Build the SparkSession for this consumer process, with the Kafka connector."""
    driver_memory = os.getenv("SPARK_DRIVER_MEMORY", "2g")
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    spark = (
        SparkSession.builder.appName("bombay-temperature-streaming-consumer")
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.driver.host", "localhost")
        .config("spark.driver.memory", driver_memory)
        .config("spark.jars.packages", KAFKA_CONNECTOR_PACKAGE)
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_kafka_stream(spark: SparkSession, *, bootstrap_servers: str = BOOTSTRAP_SERVERS, topic: str = TOPIC) -> DataFrame:
    """readStream from Kafka, decoded from JSON into MESSAGE_SCHEMA columns."""
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap_servers)
        .option("subscribe", topic)
        .option("startingOffsets", "earliest")
        .load()
    )
    return raw.select(
        F.from_json(F.col("value").cast("string"), MESSAGE_SCHEMA).alias("payload"),
        F.col("timestamp").alias("kafka_ingest_time"),
    ).select("payload.*", "kafka_ingest_time")


def build_windowed_aggregation(source_df: DataFrame) -> DataFrame:
    """Tumbling-window aggregation by city over Kafka ingestion time.

    Pure transform: works identically whether `source_df` came from a live
    Kafka readStream (has a `kafka_ingest_time` column, as read_kafka_stream
    produces) or a static batch DataFrame with the same schema, which is what
    makes this testable without a broker.
    """
    return (
        source_df.filter(F.col("AverageTemperature").isNotNull() & F.col("City").isNotNull())
        .groupBy(F.window(F.col("kafka_ingest_time"), WINDOW_DURATION), F.col("City"))
        .agg(
            F.avg("AverageTemperature").alias("avg_temperature"),
            F.min("AverageTemperature").alias("min_temperature"),
            F.max("AverageTemperature").alias("max_temperature"),
            F.count(F.lit(1)).alias("event_count"),
        )
        .select(
            F.col("City").alias("city"),
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "avg_temperature",
            "min_temperature",
            "max_temperature",
            "event_count",
        )
    )


def _write_batch_to_parquet(batch_df: DataFrame, batch_id: int) -> None:
    """foreachBatch sink: overwrite the windowed-features snapshot with the complete current state.

    outputMode="complete" means batch_df already contains every window/city
    seen so far, not just this micro-batch's delta -- overwriting (rather
    than appending) each time keeps the Parquet directory a single coherent
    "latest known state" snapshot for api/main.py's streaming endpoint to
    read directly with pandas.
    """
    count = batch_df.count()
    logger.info("Batch %d: writing %d windowed rows to %s", batch_id, count, WINDOWED_FEATURES_PATH)
    (
        batch_df.write.mode("overwrite")
        .parquet(str(WINDOWED_FEATURES_PATH))
    )


def run() -> None:
    WINDOWED_FEATURES_PATH.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.mkdir(parents=True, exist_ok=True)

    spark = get_streaming_spark()
    ensure_topic_exists()
    logger.info("Consuming topic '%s' from %s", TOPIC, BOOTSTRAP_SERVERS)

    source_df = read_kafka_stream(spark)
    windowed = build_windowed_aggregation(source_df)

    query = (
        windowed.writeStream.outputMode("complete")
        .foreachBatch(_write_batch_to_parquet)
        .option("checkpointLocation", str(CHECKPOINT_PATH))
        .start()
    )

    logger.info("Streaming query started. Ctrl+C to stop.")
    query.awaitTermination()


if __name__ == "__main__":
    run()
