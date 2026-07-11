# TensorFlow vs. PyTorch: Forecasting Dashboard
### Bombay Surface Temperature, 1970–2012

[![CI](https://github.com/MAOFILHO/Portfolio-Projects/actions/workflows/tensorflow-pytorch-forecasting-dashboard-ci.yml/badge.svg)](https://github.com/MAOFILHO/Portfolio-Projects/actions/workflows/tensorflow-pytorch-forecasting-dashboard-ci.yml)

An interactive full-stack showcase of time-series forecasting with
**statistical models (ARIMA/SARIMAX)** and **LSTM neural networks in both
TensorFlow/Keras and PyTorch**, converted from a Jupyter notebook into a
self-contained, runnable project: a Python backend (data pipeline + FastAPI,
with on-demand live model runs) and a React/TypeScript dashboard styled with
a Contoso-placeholder corporate theme.

This folder is fully self-contained — move or rename it anywhere and it will
still run, since all paths are relative and configurable via `.env` files.

## Why this project exists

Beyond the modelling itself, the value here is in the pipeline discipline
around it:

- **Translating raw temporal data into structured, model-ready inputs** —
  fail-fast schema/quality validation (`backend/src/validation.py`), then
  consistent scaling and rolling-window construction feeding every model,
  statistical or deep learning, identically.
- **Identifying patterns that inform operational decisions** — trend,
  seasonality, and stationarity are surfaced explicitly (EDA + ADF/KPSS
  tests) before any model is fit, not left implicit in a black box.
- **Comparing model classes to balance interpretability vs. performance** —
  ARIMA/SARIMAX (transparent, coefficient-level explainable) run side by
  side with LSTM in both TensorFlow and PyTorch (higher-capacity, less
  interpretable), evaluated on the identical held-out period.
- **Delivering forecasts that support planning, risk mitigation, and
  resource allocation** — every model's forecast, confidence interval, and
  error metrics are exposed through the same API/dashboard shape, regardless
  of which model produced them.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system
design, data pipeline stages, and framework trade-off discussion.

## What it does

Historical monthly surface temperature data for Bombay (Mumbai), 1970–2012,
is used to:

1. Explore trends, seasonality, and stationarity (moving averages, seasonal
   decomposition, ADF/KPSS tests).
2. Fit an `auto_arima`-selected ARIMA model and two SARIMAX models, each
   forecasting 36 months ahead.
3. Train the same LSTM architecture (3 stacked LSTM layers + 2 dense layers)
   **twice** — once in TensorFlow/Keras, once in PyTorch — to produce a
   rolling forecast over the same test period.
4. Compare all five models' forecast accuracy (MSE/RMSE) side by side.

From the dashboard's sidebar you can select any of the 5 models, **run it
live** (real fitting/training happens on the backend, not a canned replay),
watch its status update, and see its forecast chart and metrics as soon as
it completes. A "Compare All" view overlays every model that's been run, and
a "Learn: PyTorch vs. TensorFlow" page explains the core deep-learning
concepts (tensors, model building, training loops, data loading,
regularization, evaluation, hyperparameter tuning, saving/loading, CNNs vs.
RNNs/LSTMs, visualization) using this project's actual code as the running
example.

## Project layout

```
backend/    Python pipeline (converted from the notebook) + FastAPI service
            with an on-demand job runner for live model execution
frontend/   React + TypeScript dashboard (Vite, Recharts, react-router,
            Contoso theme) — sidebar model picker, run/compare/EDA/learn pages
```

## Quickstart

### 1. Backend — Set up the Environment

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # adjust paths if needed; defaults work out of the box
```

### 2. Backend — Tests

```bash
cd backend
pytest tests/test_smoke.py
```

Runs every model in the registry (ARIMA, both SARIMAX models, both LSTM
variants) directly, plus the full `run_pipeline.py` seed run end-to-end,
against the real dataset and pre-trained checkpoints (fast — LSTMs reuse
their checkpoints instead of retraining in the test).


### 3. Backend — seed initial results 

```bash
cd backend
python run_pipeline.py                                  
# seeds all 5 models once, so the dashboard has
# data on first load (a few minutes, mostly the
# auto-ARIMA search and the two LSTMs' training)
```

### 4. Backend — Start the API

```bash
cd backend
python -m uvicorn api.main:app --reload --reload-dir api --reload-dir src --port 8000
```

`--reload-dir` scopes the file watcher to just `api/` and `src/` — without it,
`--reload` watches the whole `backend/` directory including `.venv/`, and
package installs/`.pyc` writes inside `site-packages` can trigger an endless
restart loop that makes the API effectively unreachable. If you don't need
auto-reload, just drop `--reload` (and the two `--reload-dir` flags)
entirely.

The API is now available at `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`). From here, every model can also be re-run live
from the dashboard itself (see below) — `run_pipeline.py` is just a
convenience seed step, not a required one.

### 5. Frontend — run the dashboard

```bash
cd frontend
npm install
cp .env.example .env            # optional: point at a non-default API URL
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` requests to
the backend on port 8000 (see `vite.config.ts`), so no CORS configuration is
needed for local development. Pick a model from the sidebar, click **Run
Model**, and watch it fit/train live; open **Compare All** once a few models
have run, or **Learn: PyTorch vs. TensorFlow** any time.


### 6. Continuous Integration (CI) GitHub Actions

[`tensorflow-pytorch-forecasting-dashboard-ci.yml`](../.github/workflows/tensorflow-pytorch-forecasting-dashboard-ci.yml)
(at the repo root, scoped to this folder via a `paths:` filter) runs on every
push and pull request to `main`: a `backend` job installs `requirements.txt` and
runs the full smoke suite above, and a `frontend` job installs with `npm ci`
and runs `npm run build` (TypeScript + Vite). Both LSTM checkpoints
(TensorFlow and PyTorch) are committed to the repo, so CI loads them directly
rather than retraining from scratch. If either checkpoint is ever missing
(e.g. deleted locally, or on a fresh clone before the first pipeline run),
`run_lstm()` / `run_lstm_pytorch()` both fall back to training automatically
— verified by simulating a missing checkpoint locally.

<img width="1420" height="698" alt="Screenshot 2026-07-10 at 7 01 11 PM" src="https://github.com/user-attachments/assets/df6a2040-b384-4f28-9239-559f47e95fde" />


## Data pipeline robustness

Every model — statistical or deep learning, TensorFlow or PyTorch — is fed
by the same pipeline (`backend/src/data_loading.py` →
`backend/src/validation.py` → `backend/src/preprocessing.py`), so data
quality is enforced once, upstream, rather than re-implemented per model.
`validation.py` fails fast with a clear `DataValidationError` if the input
CSV is missing required columns, has no rows for the target city, contains
unparseable dates, or is too sparse (>50% missing temperature values) to
forecast reliably — surfacing a diagnosable error immediately instead of a
confusing failure several pipeline stages later inside statsmodels/Keras/
PyTorch.

## How live model runs work

Model fits/training are blocking, CPU-bound work (seconds for SARIMAX, up to
a couple of minutes for `auto_arima`'s full grid search, tens of seconds for
either LSTM's training epochs) — too slow to run inside a single HTTP
request. `POST /api/models/{key}/run` kicks the run off in a background
thread and returns a `job_id` immediately; the frontend polls
`GET /api/jobs/{job_id}` every ~1.5s until it completes, then displays the
result. Job state lives in memory (a `ThreadPoolExecutor` + dict in
`backend/api/jobs.py`) — simple and sufficient for a local/single-process
app, but a job's status is lost if the backend restarts mid-run.

Each model's result is also persisted to
`backend/outputs/results/{model_key}.json`, so `GET /api/models/{key}/result`
and the Compare All view always show the *last completed* run for that
model, even before you've triggered anything from the UI in this session
(as long as `run_pipeline.py` has been run at least once, or you've run that
model live before).

## Environment variables

### backend/.env

| Variable             | Default                                              | Purpose                                                        |
|-----------------------|-------------------------------------------------------|------------------------------------------------------------------|
| `DATA_PATH`           | `data/GlobalLandTemperaturesByMajorCity.csv`          | Source CSV dataset                                                |
| `MODEL_PATH`          | `models/TemperatureForecastingModel.keras`            | TensorFlow/Keras LSTM checkpoint save/load location                |
| `MODEL_PATH_PYTORCH`  | `models/TemperatureForecastingModel_pytorch.pt`       | PyTorch LSTM checkpoint save/load location                         |
| `OUTPUT_DIR`          | `outputs`                                              | Where per-model results, `eda.json`, and plot PNGs are written      |
| `LSTM_EPOCHS`         | `10`                                                    | Training epochs for both LSTMs (10 matches the original notebook)  |
| `LSTM_RETRAIN`        | `true`                                                  | Retrain LSTMs each run, or reuse the existing checkpoints           |
| `API_CORS_ORIGIN`     | `http://localhost:5173`                                | Allowed origin for the FastAPI CORS policy                          |

### frontend/.env

| Variable              | Default (unset)                  | Purpose                                                      |
|-----------------------|------------------------------------|----------------------------------------------------------------|
| `VITE_API_BASE_URL`   | *(empty → uses Vite dev proxy)*    | Base URL of the FastAPI backend, for non-local deployments |

No API keys, tokens, or credentials are required anywhere in this project.

## Notes on logic carried over from the original notebook

Model architectures, hyperparameters, and window sizes are preserved exactly
from the source notebook (both LSTM implementations use the same 3-layer
100→50→10 LSTM + 64→32→1 Dense architecture, for a fair comparison).

Two pre-existing quirks in the source notebook are called out here rather
than silently fixed:

- **`backend/src/sarimax_model.py`**: the notebook's "zoom in on SARIMAX
  model 2's forecast" plot (cell 93) actually rendered **model 1**'s forecast
  due to what looks like a copy-paste bug (`pred` instead of `pred2`). Now
  that each SARIMAX model runs independently on demand rather than
  sequentially in one notebook pass, this is resolved by construction — each
  model's zoom plot correctly uses its own forecast. See the module
  docstring for details.
- Cells 72/74 in the notebook produced two near-identical ARIMA forecasts
  plots; both are still preserved as separate output images
  (`arima_forecast_1.png` / `arima_forecast_2.png`).

## Re-running with fresh data

Replace `backend/data/GlobalLandTemperaturesByMajorCity.csv` and either
re-run `python run_pipeline.py` to reseed everything, or just click **Run
Model** on whichever models you want refreshed from the dashboard.

## Publishing to GitHub

Everything needed to run this project is already inside this folder and
committed to the repo, including the dataset (~14 MB) and both pre-trained
model checkpoints — TensorFlow (~1 MB) and PyTorch (~0.3 MB) — so both
frameworks show completed results immediately after cloning, with no
training required to explore the dashboard. All three are well under
GitHub's file size limits, so no Git LFS is required. `.env` files are
git-ignored; only `.env.example` files are committed.


## Web App Screenshots

<img width="1426" height="649" alt="Screenshot 2026-07-10 at 5 46 01 PM" src="https://github.com/user-attachments/assets/f2a80b9f-4918-4b07-ae73-d63d76ea161d" />
<br><br>
<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1421" height="643" alt="Screenshot 2026-07-10 at 5 46 19 PM" src="https://github.com/user-attachments/assets/4b2e0e8d-6646-4604-bc73-5a99d4eef2e3" />
<br><br>
<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1419" height="692" alt="Screenshot 2026-07-10 at 5 48 04 PM" src="https://github.com/user-attachments/assets/1320e989-d4ea-4d55-9e42-f94703e1c3a4" />
<br><br>
<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1420" height="698" alt="Screenshot 2026-07-10 at 5 48 15 PM" src="https://github.com/user-attachments/assets/3937b08a-6f7c-46a5-ac90-a577df9e59e9" />
<br><br>
<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1430" height="702" alt="Screenshot 2026-07-10 at 5 47 01 PM" src="https://github.com/user-attachments/assets/69a92e83-06eb-42fb-8fa1-a160a0c92c15" />
<br><br>
<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1427" height="704" alt="Screenshot 2026-07-10 at 5 47 24 PM" src="https://github.com/user-attachments/assets/b374322c-3226-44f3-878c-442de90023b1" />
<br><br>
<img width="100%" height="1" alt="" src="https://github.com/user-attachments/assets/f2af28ee-a373-4488-89e5-2b84d5da9620" />
<br><br>
<img width="1434" height="701" alt="Screenshot 2026-07-10 at 5 47 49 PM" src="https://github.com/user-attachments/assets/73ed7ef3-8568-44d4-843b-a217e2cacc86" />
<br><br>
