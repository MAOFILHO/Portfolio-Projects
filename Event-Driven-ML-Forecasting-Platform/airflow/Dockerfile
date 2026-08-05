# Custom Airflow image for dags/forecasting_pipeline_dag.py: adds a JDK (for
# PySpark, src/spark_session.py) and the scientific/ML stack the DAG's tasks
# import (TensorFlow, PyTorch, PySpark, statsmodels, pmdarima, scikit-learn).
#
# Code, data, model checkpoints, and outputs are NOT baked in -- they're
# bind-mounted at runtime (see docker-compose.yml), so editing DAG/pipeline
# code never requires an image rebuild. Only the dependency layer lives here.
FROM apache/airflow:2.11.2-python3.12

USER root

# PySpark (src/spark_session.py) needs a JVM. Deliberately no ENV JAVA_HOME
# here: Debian's /usr/lib/jvm/default-java symlink only exists if the
# default-jdk metapackage is installed, not a specific openjdk-*-jdk package
# like this one -- so a hardcoded ENV JAVA_HOME would point nowhere.
# src/spark_session.py's _ensure_java_home() resolves it at runtime instead,
# by following `java` on PATH (which apt's update-alternatives correctly
# registers as part of this install), the same way a shell would.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt

# CPU-only PyTorch, installed separately from its dedicated wheel index. A
# plain `pip install torch==2.3.1` inside a Linux container pulls the default
# PyPI Linux wheel, which bundles CUDA libraries (multiple GB) -- dead weight
# here, since Docker Desktop on macOS has no GPU passthrough to Linux
# containers regardless. The CPU-only wheel is ~10x smaller and behaves
# identically for this project's CPU-bound training.
RUN pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu
