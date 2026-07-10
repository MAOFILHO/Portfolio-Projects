# Changelog

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
