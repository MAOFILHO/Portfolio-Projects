# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A full-stack time-series forecasting showcase, evolved from a local batch
dashboard into a small event-driven ML platform: Bombay (Mumbai) surface
temperature, 1970–2012. Five models — auto-tuned ARIMA, two SARIMAX
configurations, and the *same* LSTM architecture implemented twice (once in
TensorFlow/Keras, once in PyTorch) — run against an identical
train/test split and are compared side by side. Backend is a **PySpark**
data pipeline + FastAPI service with on-demand live model runs; a **Kafka +
Spark Structured Streaming** layer demonstrates live telemetry ingestion; an
**Airflow** DAG orchestrates the same pipeline as a scheduled, observable
job. Frontend is a React/TypeScript dashboard (Vite, Recharts). Everything
runs locally, $0 cost — no managed cloud services anywhere in this project.

Full system design lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) —
read it before making non-trivial changes to the pipeline, model layer, or
job-execution model. The README's "Quickstart" and "Environment variables"
sections are also authoritative for local setup.

## Commands

### Backend (Python 3.12, from `backend/`)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # defaults work out of the box
# JDK 17 must be on PATH -- spark_session.py auto-detects JAVA_HOME from
# `java` on PATH, so any JDK 17 install works, nothing to export manually.

pytest tests/                           # everything: Spark ETL, smoke, Kafka unit tests
pytest tests/test_smoke.py -k arima     # run a single test by keyword

python run_pipeline.py                  # seeds all 5 models' results (first-load data)

python -m uvicorn api.main:app --reload --reload-dir api --reload-dir src --port 8010
# --reload-dir scopes the watcher to api/ + src/ only — plain --reload
# watches all of backend/ including .venv/, which can trigger endless
# restart loops from package installs/.pyc writes in site-packages.
```

Five test modules, all broker/orchestrator-free (no live Kafka or Airflow
needed to run any of them):

- `tests/test_smoke.py` — every model in `MODEL_REGISTRY` directly plus the
  full `run_pipeline.py` seed run, end-to-end, against the real dataset and
  pre-trained checkpoints. Fast because both LSTMs load their committed
  checkpoints (`backend/models/*.keras`, `*.pt`) instead of retraining.
- `tests/test_spark_etl.py` — Spark ETL parity against a golden pandas-pipeline
  fixture, index contract (`freq='MS'`), and validation error cases.
- `tests/test_kafka_producer.py` / `test_kafka_consumer.py` — pure-function
  unit tests (row serialization, windowing/aggregation logic) against static
  data, no broker.
- `tests/test_streaming_endpoint.py` — the streaming API endpoint against a
  fixture Parquet file, including the "nothing streaming yet" empty state.

### Kafka streaming layer (from repo root / `backend/`)

```bash
docker compose up -d                        # local Kafka broker, KRaft mode
python src/kafka_consumer.py                # start before the producer
python src/kafka_producer.py --limit 2000   # quick smoke run
```

`kafka_consumer.py` creates the topic itself if it doesn't exist yet
(`ensure_topic_exists()`) — don't rely on `KAFKA_AUTO_CREATE_TOPICS_ENABLE`
alone, it only fires on the first *produce*, and Spark's Kafka source fails
hard (no retry) if the topic isn't there when it subscribes.

### Airflow orchestration (from `airflow/`)

```bash
docker compose build              # ~7GB image, first time only
docker compose up -d
docker compose exec airflow-scheduler airflow dags trigger forecasting_pipeline
```

`dags/forecasting_pipeline_dag.py` is bind-mounted, not baked into the image
— edit it and re-trigger, no rebuild needed. Same for `backend/src`,
`backend/data`, `backend/models`, `backend/outputs`.

### Frontend (Node.js + npm, from `frontend/`)

```bash
npm install
cp .env.example .env       # optional: point VITE_API_BASE_URL elsewhere
npm run dev                # Vite dev server on :5173, proxies /api -> :8010
npm run build               # tsc -b && vite build — this is also the CI check
npm run lint                 # tsc --noEmit (there is no separate ESLint)
```

The dev server proxies `/api` to `http://localhost:8010` (`vite.config.ts`),
so no CORS setup is needed locally — CORS is still configured on the backend
(`API_CORS_ORIGIN` in `backend/.env`) for non-proxied deployments.

### CI

The monorepo's shared
`.github/workflows/event-driven-ml-forecasting-platform-ci.yml` runs on every
push/PR to `main` that touches this folder (path-filtered, same convention as
every other project in `Portfolio-Projects`): a `backend` job runs the Spark
ETL parity suite, the pytest smoke suite, and the Kafka layer's broker-free
unit tests; a `frontend` job runs `npm run build`. Both LSTM checkpoints are
committed so CI doesn't retrain from scratch; if a checkpoint is ever
missing, `run_lstm()` / `run_lstm_pytorch()` fall back to training
automatically.

### Project history

This project began as `TensorFlow-PyTorch-Forecasting-Dashboard`, a sibling
folder in the `Portfolio-Projects` monorepo. This folder is a separate,
self-contained project in that same monorepo — copied from the original as a
starting point, then built up with Spark, Kafka, and Airflow (event-driven ML
platform). `TensorFlow-PyTorch-Forecasting-Dashboard` remains unchanged,
in place, alongside this folder in `github.com/MAOFILHO/Portfolio-Projects`.

## Architecture

### Data pipeline (`backend/src/`) — Spark ETL, one path for every model

```
data_loading.py → validation.py → preprocessing.py → eda.py
(Spark ingest,    (Spark SQL      (Spark clean/trim,   (trend/seasonality/
 explicit schema)  fail-fast)      ONE .toPandas()      stationarity —
                                    handoff, rebuild     ADF/KPSS, pandas
                                    DatetimeIndex         from here on)
                                    freq='MS' contract)
```

PySpark (`spark_session.py`'s singleton) is the sole ingest/ETL engine — not
pandas. Every model — statistical or deep learning — consumes the same
validated, preprocessed `pd.Series` produced by the single `.toPandas()`
handoff at the end of `preprocessing.py`, so correctness is enforced once
upstream rather than per model. `validation.py` raises `DataValidationError`
fast on missing columns, empty city slices, unparseable dates, or >50%
missing values, so failures surface immediately instead of deep inside
statsmodels/Keras/PyTorch. Train/test split (≤2009 train, 2010+ test) is
built once in `run_pipeline.py` / `api/main.py` (`_build_context`) / each
Airflow task and shared by every model for an apples-to-apples comparison.

### Model layer — `model_registry.py` is the single dispatch table

`MODEL_REGISTRY: dict[str, ModelSpec]` maps each `model_key` (`arima`,
`sarimax_model1`, `sarimax_model2`, `lstm_tensorflow`, `lstm_pytorch`) to
metadata and a `run: Callable[[RunContext], dict]`. Every model function has
the uniform shape `RunContext → dict` (a `ModelResult`-shaped dict with
forecast, metrics, etc.). This registry is the *only* place that knows how
to run each model — both `run_pipeline.py` (seeds all 5 up front) and
`backend/api/jobs.py` (runs one on demand) call through it. Adding a model
means adding one entry here, not touching the pipeline/API/job runner.

The two LSTM implementations (`lstm_model.py` TensorFlow, `lstm_pytorch_model.py`
PyTorch) intentionally share the exact same architecture (3 stacked LSTM
layers 100→50→10, Dense/Linear 64→32→1) and window size (60), so they're a
fair framework comparison, not just two different models. Keep them in sync
if you touch the architecture in one.

### Execution + persistence (`backend/api/`)

Model fitting/training is CPU-bound and slow (seconds for SARIMAX, up to
~2 min for ARIMA's `auto_arima` grid search, tens of seconds per LSTM) — too
slow for a single request. `POST /api/models/{key}/run` submits to a
`ThreadPoolExecutor`-based job runner (`jobs.py`) and returns a `job_id`
immediately; the frontend polls `GET /api/jobs/{job_id}` every ~1.5s.
Job state is in-memory only (lost on backend restart, by design — no
Redis/Celery for this single-process local app). Each completed run is
persisted to `backend/outputs/results/{model_key}.json` via
`results_store.py`, so `GET /api/models/{key}/result` and the Compare view
always reflect the last completed run, independent of in-memory job state.

Key endpoints (`api/main.py`): `/api/models`, `/api/models/{key}/run`,
`/api/jobs/{id}`, `/api/comparison`, `/api/eda/*`.

### Streaming (`backend/src/kafka_producer.py`, `kafka_consumer.py`)

Separate from the batch pipeline entirely — a producer replays the full
dataset (all cities) onto a Kafka topic; a PySpark Structured Streaming
consumer (its own `SparkSession`, not `spark_session.py`'s batch singleton —
see the module docstring for why) windows it by ingestion time, not the
payload's historical `dt`, into per-city tumbling-window aggregates written
to Parquet. `api/main.py`'s `GET /api/streaming/windowed-features` just
`pandas.read_parquet()`s that snapshot — no Spark inside the API process.

### Orchestration (`dags/`, `airflow/`)

`dags/forecasting_pipeline_dag.py` runs the identical pipeline
`run_pipeline.py` runs manually, as an Airflow DAG (LocalExecutor): validate
→ Spark ETL → 5 parallel training tasks (one per `MODEL_REGISTRY` entry) →
export. Every task calls the same functions listed above — nothing is
reimplemented for Airflow. `airflow/Dockerfile` bakes in only the
dependency layer (JDK, TensorFlow, CPU-only PyTorch, PySpark); code/data/
models/outputs are bind-mounted from the host, so a DAG run's exported
results land in the same `backend/outputs/results/*.json` the dashboard
already reads.

### Frontend (`frontend/src/`)

Sidebar model picker (`layout/Sidebar.tsx`) → `pages/ModelPage.tsx` (run +
view a single model, polling via `hooks/useJobPolling.ts`) →
`pages/ComparePage.tsx` (overlay every model that's been run) →
`pages/EdaPage.tsx` / `pages/LearnPage.tsx` / `pages/StreamingPage.tsx`
(Live Telemetry, polling `hooks/useStreamingPoll.ts`). All backend calls go
through `api/client.ts`. Charts are Recharts (`components/ForecastChart.tsx`).
Styling is a custom Contoso-placeholder corporate theme (`theme.css`), no
CSS framework.

## Conventions and quirks worth knowing

- **Config is env-driven, not hardcoded**: both `backend/.env` and
  `frontend/.env` (copied from their `.env.example`) control paths, ports,
  epochs, retrain behavior, and API URLs — see the tables in `README.md`.
  No API keys/credentials are used anywhere in this project.
- **`LSTM_RETRAIN`** (`backend/.env`): `true` retrains an LSTM every run;
  `false` reuses the committed checkpoint. Affects run time significantly.
- Two notebook-inherited quirks are deliberately preserved and documented
  rather than silently changed — see `backend/src/sarimax_model.py`'s module
  docstring (a copy-paste bug in the original notebook's zoom plot, now moot
  since each SARIMAX model runs independently) and the README's "Notes on
  logic carried over from the original notebook" section. Don't
  refactor these away without checking that context first.
- Model architectures/hyperparameters are intentionally preserved exactly
  from the source notebook for both LSTMs — don't casually adjust layer
  sizes, window size (60), or epoch count (10) as a "cleanup"; that changes
  the framework comparison this project is built to demonstrate.
- `backend/outputs/` (plots, `eda.json`, `results/*.json`, `jobs/*.json`,
  `streaming/`) is generated/regenerable output, not hand-authored — safe to
  regenerate via `run_pipeline.py`, a live run, or an Airflow DAG trigger,
  but treat existing files as build artifacts rather than source when
  reviewing diffs.
- **`JAVA_HOME` is auto-detected, never hardcode it.** `spark_session.py`'s
  `_ensure_java_home()` resolves `java` on `PATH` if `JAVA_HOME` is unset or
  invalid — this exists because there's no single JDK-layout convention that
  holds across environments (confirmed the hard way: Debian's
  `/usr/lib/jvm/default-java` symlink, which the Airflow Dockerfile initially
  assumed existed, only appears with the `default-jdk` metapackage, not the
  `openjdk-17-jdk-headless` package actually installed there). Don't
  reintroduce a hardcoded `JAVA_HOME` path anywhere in this project.
- **Kafka's consumer must create its own topic before subscribing** —
  `kafka_consumer.py`'s `ensure_topic_exists()`. `KAFKA_AUTO_CREATE_TOPICS_ENABLE=true`
  only creates a topic on the first *produce*, not on a consumer subscribing
  to it, and Spark's Kafka source fails hard (`UnknownTopicOrPartitionException`,
  no retry) if the topic doesn't exist yet — this bit the very first
  consumer-then-producer test run. Don't remove that call as "redundant."
