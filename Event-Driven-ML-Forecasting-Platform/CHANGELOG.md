# Changelog

## v0.7.0 — Airflow DAG orchestration

Copied from `TensorFlow-PyTorch-Forecasting-Dashboard` (see README's
"Project history") into this new sibling folder,
`Event-Driven-ML-Forecasting-Platform`, in the same `Portfolio-Projects`
monorepo, to add Spark, Kafka, and Airflow without touching the original
folder's contents or history. The three phases below (v0.5.0–v0.7.0) were all
built in this new folder.

- Added `dags/forecasting_pipeline_dag.py`: validate_raw_data → run_pyspark_etl
  → train_forecasting_models (5 parallel tasks, one per `MODEL_REGISTRY`
  entry) → export_dashboard_results. Every task wraps existing, already-tested
  functions (`data_loading`, `preprocessing`, `eda`, `model_registry`,
  `results_store`) — no model/ETL/result logic is reimplemented for Airflow.
- Added `airflow/Dockerfile` (`apache/airflow:2.11.2-python3.12` + JDK 17 +
  a slimmed `requirements-airflow.txt` + CPU-only PyTorch from its own wheel
  index — avoids pulling multi-GB CUDA libraries that are dead weight
  without GPU passthrough) and `airflow/docker-compose.yml` (LocalExecutor,
  not the 7-service CeleryExecutor stack — no benefit on one machine).
  Code/data/models/outputs are bind-mounted, not baked into the image.
- `backend/src/spark_session.py` now auto-detects `JAVA_HOME` by resolving
  `java` on `PATH` when it's unset or invalid, instead of assuming a
  per-environment convention. Fixes JVM startup inside the Airflow container
  (Debian's `/usr/lib/jvm/default-java` symlink turned out not to exist for
  the specific JDK package installed there) and makes every other entry
  point (API, `run_pipeline.py`, pytest) more robust too.
- Verified end-to-end: image built, stack up, DAG triggered via
  `airflow dags trigger`, all 8 tasks succeeded, `backend/outputs/results/*.json`
  refreshed on the host via the bind mount, and the dashboard's
  `/api/comparison` confirmed to serve the DAG-produced forecasts — metrics
  matching the pre-existing baseline to the decimal.

## v0.6.0 — Kafka streaming ingestion layer

- Added `docker-compose.yml` (repo root): a local, single-node Kafka broker
  in KRaft mode (`apache/kafka:3.9.0`, no Zookeeper) — not `bitnami/kafka`,
  which deprecated most of its free-tier image catalog in 2025.
- Added `backend/src/kafka_producer.py`: replays the full dataset (every
  city, not just Bombay) onto a `temperature-telemetry` topic as simulated
  real-time telemetry, at a configurable rate.
- Added `backend/src/kafka_consumer.py`: a PySpark Structured Streaming
  consumer, its own `SparkSession` (separate from the batch ETL singleton,
  so the Kafka connector's Maven-resolved jars don't slow down ordinary
  dashboard requests), maintaining 10-second tumbling per-city windows
  (avg/min/max/count) written to Parquet. Windows on Kafka ingestion time,
  not the payload's historical date — the dataset spans 1743–2013, which
  would break event-time watermarking at replay speed. Also fixed a
  consumer/topic startup race: Spark's Kafka source fails hard if the
  subscribed topic doesn't exist yet, and `KAFKA_AUTO_CREATE_TOPICS_ENABLE`
  only creates a topic on the first *produce*, not a subscribe — added
  `ensure_topic_exists()` so consumer startup is correct regardless of
  start order.
- Added `GET /api/streaming/windowed-features` (`backend/api/main.py`):
  reads the consumer's Parquet snapshot with plain pandas — no live Spark
  session inside the API process. Returns a graceful `streaming_active: false`
  empty state if nothing has been started yet, rather than an error.
- Added `frontend/src/pages/StreamingPage.tsx` ("Live Telemetry"): polls the
  new endpoint every 3s, shows a per-city windowed-stats table or a
  "not started yet" state with the exact commands to start the pipeline.
- Added `backend/tests/test_kafka_producer.py`, `test_kafka_consumer.py`,
  `test_streaming_endpoint.py` — all broker-free (pure-function/fixture
  tests), so CI runs them without a live Kafka broker.

## v0.5.0 — PySpark as the sole batch ETL engine

- Migrated `backend/src/data_loading.py`, `validation.py`, and
  `preprocessing.py` from pandas to PySpark end-to-end: Spark does ingest,
  schema/quality validation (as Spark SQL), date parsing, column selection,
  and the 1970–2012 trim; a single `.toPandas()` handoff at the end of
  `preprocess()` rebuilds the `DatetimeIndex(freq='MS')` contract every
  downstream model, `eda.py`, and the API depend on. `eda.py` and both LSTM
  modules are unchanged — Spark's reach stops at that one handoff by design.
- Added `backend/src/spark_session.py`: a locked, lazy process-wide
  `SparkSession` singleton (JVM startup is ~5-8s; the API caches the
  preprocessed frame for the process lifetime, so that cost is paid once).
- Captured a golden pandas-pipeline fixture *before* the migration
  (`backend/tests/fixtures/preprocessed_golden.pkl`) and added
  `backend/tests/test_spark_etl.py` to assert Spark's output matches it
  (within float64 parser-noise tolerance — Spark's and pandas' CSV double
  parsers round the same decimal string differently in the 15th digit,
  confirmed to be parser noise, not a real data discrepancy, by reproducing
  the same drift via synthetic jitter on the original pandas pipeline).
- Added `pyspark[sql]==3.5.9` to `backend/requirements.txt`; requires a
  JDK 17 runtime.
- Verified: all Spark ETL parity tests and the full pre-existing smoke suite
  pass unchanged; live-checked `sarimax_model1`/`sarimax_model2` metrics
  against a pre-migration snapshot (matched to float noise for model1; a
  larger drift on model2 was isolated to pre-existing L-BFGS-B optimizer
  sensitivity to last-bit float noise, not a migration regression —
  reproduced by feeding the *original* pandas pipeline the same
  order-of-magnitude synthetic jitter and seeing the identical drift).

## v0.4.2 — Commit both pre-trained checkpoints; repo hygiene for shipping

- `backend/models/TemperatureForecastingModel_pytorch.pt` is now committed
  (previously gitignored/generated-on-first-run) so both the TensorFlow and
  PyTorch LSTM show completed results immediately after cloning, with no
  training required. Updated `README.md`'s CI and "Publishing to GitHub"
  sections to match.
- `backend/outputs/` is now tracked in git (previously ignored) — per-model
  results, EDA data, and plot PNGs are committed as a working snapshot.
- Removed `backend/outputs/results.json`, a stale leftover from the earlier
  single-file results architecture (superseded by `outputs/results/{model_key}.json`).

## v0.4.1 — Fix uvicorn --reload watching .venv

- `README.md`'s quickstart now scopes `uvicorn --reload` to
  `--reload-dir api --reload-dir src`. Without it, `--reload` watches the
  entire `backend/` directory including `.venv/`, and `.pyc`/package-install
  writes inside `site-packages` can trigger a continuous restart loop that
  makes the API effectively unreachable (observed: a new server process
  started every few hundred milliseconds, so the frontend's requests never
  got a stable response and the sidebar was stuck on "Loading models…").

## v0.4.0 — Continuous integration

- Added `.github/workflows/ci.yml`: on every push/PR to `main`, a `backend`
  job installs `requirements.txt` and runs the full `pytest` smoke suite, and
  a `frontend` job runs `npm ci` + `npm run build`. Verified the CI-critical
  path locally: with the (gitignored, not committed) PyTorch checkpoint
  removed to simulate a fresh checkout, `run_lstm_pytorch()`'s
  retrain-if-missing fallback correctly trains from scratch and the smoke
  test still passes (27s).
- Added a CI status badge and a "CI" section to `README.md`.

## v0.3.1 — Bundle size + job store durability fixes

- Code-split the frontend: routes (`ModelPage`, `ComparePage`, `EdaPage`,
  `LearnPage`) are now lazy-loaded (`React.lazy` + `Suspense`), and
  `vite.config.ts` splits `react`/`react-dom`/`react-router-dom` and
  `recharts` into separate vendor chunks. Eliminates the single 577KB bundle
  warning; initial load now only fetches the current route's ~1-15KB chunk.
- `backend/api/jobs.py` now persists every job's state to
  `outputs/jobs/{id}.json` on each transition and reloads it on API startup,
  so job status/history survives a backend restart. A job still
  `queued`/`running` at the moment of a restart is correctly reloaded as
  `failed` with an explanatory error, since its background thread no longer
  exists — verified with a targeted test simulating a mid-run restart.

## v0.3.0 — Production-grade hardening + architecture documentation

- Added `backend/src/validation.py`: fail-fast schema/quality checks
  (required columns, empty slices, unparseable dates, excessive missing
  data) run once at ingestion, shared by every downstream model.
- Added `docs/ARCHITECTURE.md`: system diagram, data pipeline stage
  breakdown, statistical-vs-deep-learning and TensorFlow-vs-PyTorch
  trade-off discussion, live-execution sequence diagram, and the
  data-to-decisions business framing.
- Updated `README.md` with a "Why this project exists" section and a data
  pipeline robustness section, linking to the architecture doc.
- Added a closing framework-trade-offs takeaway to the in-app Learn page.

## v0.2.0 — Interactive dashboard + PyTorch/TensorFlow learning module

- Added a second LSTM implementation in **PyTorch**
  (`backend/src/lstm_pytorch_model.py`), architecturally identical to the
  existing TensorFlow/Keras LSTM (3 stacked LSTM layers 100→50→10, Dense
  64→32→1, window size 60), for direct side-by-side comparison.
- Added `backend/src/model_registry.py`, a single source of truth mapping
  each of the 5 models (ARIMA, SARIMAX model 1 & 2, LSTM TensorFlow, LSTM
  PyTorch) to its display metadata and run function.
- Added on-demand live model execution: `backend/api/jobs.py` (in-memory
  background job runner) plus new endpoints — `GET /api/models`,
  `POST /api/models/{key}/run`, `GET /api/jobs/{id}`,
  `GET /api/models/{key}/result`, `GET /api/comparison`. EDA endpoints are
  now computed eagerly from the CSV and cached, independent of any model run.
- Split `sarimax_model.py`'s combined `run_sarimax()` into independently
  runnable `run_sarimax_model1()` / `run_sarimax_model2()`, which resolves
  the previously-flagged cell-93 plotting quirk by construction (see README).
- Rewrote `run_pipeline.py` to seed all 5 models via the registry and persist
  per-model JSON results (`outputs/results/{model_key}.json`) plus a
  standalone `outputs/eda.json`, replacing the old single monolithic
  `results.json`.
- Recreated the frontend as a multi-page, router-based dashboard
  (`react-router-dom`): a persistent sidebar (model picker with live status
  dots), per-model pages with a **Run Model** button and live polling
  (`useJobPolling`), a **Compare All** page, an **EDA** page, and a new
  **Learn: PyTorch vs. TensorFlow** page covering tensor creation, model
  building, training/backprop, data loading, transfer learning,
  regularization, evaluation, hyperparameter tuning, saving/loading, and
  CNNs/RNNs — grounded in this project's actual code.
- Added `torch==2.3.1` to `backend/requirements.txt`; pinned
  `setuptools<81` (newer setuptools dropped the `distutils` compatibility
  shim that TensorFlow 2.16.1 depends on under Python 3.12).
- Extended `backend/tests/test_smoke.py` to exercise every model in the
  registry individually (including the new PyTorch LSTM) plus the full
  seed-run pipeline.

## v0.1.0 — Initial conversion

- Converted `9_5_Bombay_Surface_Temperature_Forecasting.ipynb` into a modular
  Python backend (`backend/src/`) covering data loading, preprocessing, EDA,
  ARIMA/auto-ARIMA, two SARIMAX models, and an LSTM neural network, preserving
  original model logic, hyperparameters, and random seeds.
- Added `backend/run_pipeline.py` to orchestrate the full pipeline and emit
  `outputs/results.json` plus plot PNGs.
- Added a FastAPI service (`backend/api/`) exposing the pipeline results as
  REST endpoints.
- Added a React + TypeScript dashboard (`frontend/`) with a Contoso
  placeholder theme, rendering interactive charts (Recharts) for observed
  vs. forecast temperatures, moving averages, seasonal decomposition, and
  stationarity test results.
- Removed hardcoded absolute Windows path for the LSTM checkpoint; both the
  dataset and model paths are now environment-configurable via `.env`.
- Added `backend/tests/test_smoke.py` end-to-end smoke test.
