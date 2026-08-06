# Cloud image for the FastAPI backend (and, with an overridden `command:`,
# the Kafka producer/consumer -- they're the same Python environment, just a
# different entrypoint, see docker-compose.cloud.yml).
#
# Same dependency-layer-only philosophy as ../../airflow/Dockerfile: this
# image contains only the Python/JDK dependency layer. `backend/src`,
# `backend/api`, `backend/data`, `backend/models`, and `backend/outputs` are
# bind-mounted at runtime from the VM's git checkout (see
# cloud-init/bootstrap.sh.tmpl) -- the exact same bind-mount pattern the
# local docker-compose stacks already use, just with "the VM's clone" in
# place of "your Mac". This means a `git pull` + `docker compose restart` on
# the VM picks up code changes without an image rebuild.
FROM python:3.12-slim

# PySpark (src/spark_session.py) needs a JVM, same as airflow/Dockerfile.
# Deliberately no ENV JAVA_HOME here for the same reason documented there:
# src/spark_session.py's _ensure_java_home() resolves it at runtime by
# following `java` on PATH.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless curl \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/backend

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# CPU-only PyTorch, installed separately from its dedicated wheel index --
# same rationale as airflow/Dockerfile: requirements.txt's plain
# `torch==2.3.1` pin resolves to the CPU-only macOS wheel automatically on a
# Mac, but a Linux container build pulls the default CUDA-bundled Linux
# wheel unless overridden here. Docker Desktop/Azure VMs have no GPU
# passthrough regardless, so CUDA is dead weight either way.
RUN pip uninstall -y torch \
    && pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
