"""Process-wide SparkSession singleton for the ETL layer.

Spark is the only ingest/clean engine in this project (see docs/ARCHITECTURE.md),
so every entry point -- run_pipeline.py, the FastAPI service, and pytest -- goes
through get_spark() rather than building its own session.

Why a singleton, and why locked:
- JVM startup costs ~5-8s. The API caches the preprocessed frame for the process
  lifetime (api/main.py:_get_preprocessed), so that cost is paid once.
- Model runs execute on a ThreadPoolExecutor (api/jobs.py), so two requests can
  race into session creation concurrently. SparkSession.getOrCreate() is not
  documented as thread-safe on first call, hence the explicit lock.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading

from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

APP_NAME = "bombay-temperature-etl"

_session: SparkSession | None = None
_lock = threading.Lock()


def _running_under_pytest() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or "PYTEST_VERSION" in os.environ


def _ensure_java_home() -> None:
    """Set JAVA_HOME if it's unset or points nowhere.

    Every entry point in this project (the API, run_pipeline.py, pytest, and
    the Airflow DAG's container) needs a JVM for PySpark, but "the right
    JAVA_HOME" varies by environment -- macOS's JDK layout, a Debian
    container's, etc. -- and there is no single conventional symlink reliably
    present everywhere (e.g. Debian's /usr/lib/jvm/default-java only exists
    if the default-jdk metapackage was installed, not a specific
    openjdk-*-jdk package, which is what the Airflow image installs). This
    only acts if JAVA_HOME is missing or already broken -- an operator's own
    correct JAVA_HOME is never overridden.

    macOS gets special handling: `/usr/bin/java` is Apple's own launcher
    stub, not a JDK, and it is *not* a symlink (`os.path.realpath` on it
    returns itself unchanged) -- so naively resolving `java` on PATH and
    stripping `/bin/java` computes JAVA_HOME=/usr, which spark-class then
    re-expands right back into `/usr/bin/java`, the same stub, disguised as
    a fix. That stub has been observed to hang indefinitely (JVM launched,
    but the process never proceeds) rather than erroring, which silently
    defeats the whole point of this function. `/usr/libexec/java_home` is
    macOS's own authoritative JDK resolver -- it inspects registered JVMs
    directly and is what a shell prompt would use -- so it wins over PATH
    resolution here.
    """
    current = os.environ.get("JAVA_HOME")
    if current and os.path.exists(os.path.join(current, "bin", "java")):
        return

    if sys.platform == "darwin":
        java_home_tool = "/usr/libexec/java_home"
        if os.path.exists(java_home_tool):
            try:
                result = subprocess.run(
                    [java_home_tool], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    os.environ["JAVA_HOME"] = result.stdout.strip()
                    logger.info(
                        "JAVA_HOME auto-detected as %s (via /usr/libexec/java_home)",
                        os.environ["JAVA_HOME"],
                    )
                    return
            except (subprocess.SubprocessError, OSError):
                pass  # fall through to the PATH-based resolution below

    java_binary = shutil.which("java")
    if not java_binary:
        return  # nothing we can do here; the JVM launch will fail with its own clear error

    real_binary = os.path.realpath(java_binary)
    java_home = os.path.dirname(os.path.dirname(real_binary))  # strip /bin/java
    os.environ["JAVA_HOME"] = java_home
    logger.info("JAVA_HOME auto-detected as %s (resolved from `java` on PATH)", java_home)


def get_spark() -> SparkSession:
    """Return the process-wide SparkSession, creating it on first use."""
    global _session
    if _session is not None:
        return _session

    with _lock:
        if _session is not None:  # another thread won the race
            return _session

        _ensure_java_home()

        master = os.getenv("SPARK_MASTER", "local[*]")
        driver_memory = os.getenv("SPARK_DRIVER_MEMORY", "2g")

        # local[*] spawns each worker as a `python3` subprocess resolved from
        # PATH, independently of the interpreter running this driver process.
        # On a machine with pyenv (or any second Python) ahead of the venv on
        # PATH, that resolves to a different minor version than this venv's
        # 3.12, and PySpark refuses to run mismatched driver/worker versions
        # (PYTHON_VERSION_MISMATCH). Pinning both to sys.executable makes the
        # worker use this exact interpreter, regardless of shell PATH.
        os.environ["PYSPARK_PYTHON"] = sys.executable
        os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

        # macOS commonly fails to resolve its own hostname for the Spark driver,
        # which surfaces as a confusing "Service 'sparkDriver' failed after 16
        # retries" at startup. Pinning to loopback avoids it; this is a local
        # single-process engine, so there is no remote executor to reach us.
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

        builder = (
            SparkSession.builder.appName(APP_NAME)
            .master(master)
            .config("spark.driver.host", "localhost")
            .config("spark.driver.memory", driver_memory)
            # The Bombay slice is ~2.6k rows; the default 200 shuffle partitions
            # would spawn 200 near-empty tasks per shuffle.
            .config("spark.sql.shuffle.partitions", "1")
            .config("spark.default.parallelism", "1")
            # Makes the single toPandas() handoff in preprocessing.py cheap.
            .config("spark.sql.execution.arrow.pyspark.enabled", "true")
            # Reject ambiguous/legacy date parsing instead of silently coercing,
            # so validation.py can actually detect unparseable 'dt' values.
            .config("spark.sql.legacy.timeParserPolicy", "CORRECTED")
        )

        if _running_under_pytest():
            # Avoids port-binding churn and 4040/4041 warnings across test runs.
            builder = builder.config("spark.ui.enabled", "false")

        _session = builder.getOrCreate()
        _session.sparkContext.setLogLevel("WARN")

        logger.info(
            "Started SparkSession (master=%s, driver_memory=%s, version=%s)",
            master,
            driver_memory,
            _session.version,
        )
        return _session


def stop_spark() -> None:
    """Tear down the SparkSession, if one was started."""
    global _session
    with _lock:
        if _session is not None:
            _session.stop()
            _session = None
            logger.info("Stopped SparkSession")
