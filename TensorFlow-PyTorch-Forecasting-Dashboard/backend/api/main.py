"""FastAPI service for the interactive Bombay temperature forecasting dashboard.

Serves:
- EDA data, computed once from the CSV and cached in memory (independent of
  any model run).
- A model registry (GET /api/models) describing the 5 available models.
- On-demand live model runs (POST /api/models/{key}/run -> background job,
  GET /api/jobs/{id} to poll) via api/jobs.py + src/model_registry.py.
- Last-known results per model (GET /api/models/{key}/result) and an
  aggregate comparison view (GET /api/comparison), both backed by
  src/results_store.py so the dashboard has data immediately after
  `python run_pipeline.py` and after every live re-run.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from api.jobs import get_job, init_job_store, latest_job_for_model, submit_job  # noqa: E402
from api.schemas import HealthResponse, MovingAveragesResponse, SeasonalDecompositionResponse, StationarityResponse  # noqa: E402
from src.data_loading import load_bombay_data  # noqa: E402
from src.eda import run_eda  # noqa: E402
from src.model_registry import MODEL_REGISTRY, RunContext, get_model_spec  # noqa: E402
from src.preprocessing import preprocess  # noqa: E402
from src.results_store import load_all_results, load_result, save_result  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

DATA_PATH = Path(os.getenv("DATA_PATH", BACKEND_DIR / "data" / "GlobalLandTemperaturesByMajorCity.csv"))
MODEL_PATH_TF = Path(os.getenv("MODEL_PATH", BACKEND_DIR / "models" / "TemperatureForecastingModel.keras"))
MODEL_PATH_PYTORCH = Path(
    os.getenv("MODEL_PATH_PYTORCH", BACKEND_DIR / "models" / "TemperatureForecastingModel_pytorch.pt")
)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BACKEND_DIR / "outputs"))
LSTM_EPOCHS = int(os.getenv("LSTM_EPOCHS", "10"))
LSTM_RETRAIN = os.getenv("LSTM_RETRAIN", "true").strip().lower() in ("1", "true", "yes", "on")
CORS_ORIGIN = os.getenv("API_CORS_ORIGIN", "http://localhost:5173")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
init_job_store(OUTPUT_DIR)

app = FastAPI(
    title="Bombay Surface Temperature Forecasting API",
    description="Interactive ARIMA/SARIMAX/LSTM (TensorFlow + PyTorch) forecasting for the Contoso dashboard.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_preprocessed_df = None
_eda_cache: dict | None = None


def _get_preprocessed():
    global _preprocessed_df
    if _preprocessed_df is None:
        if not DATA_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=f"Dataset not found at {DATA_PATH}. Set DATA_PATH to the correct location.",
            )
        data = load_bombay_data(DATA_PATH)
        _preprocessed_df = preprocess(data)
    return _preprocessed_df


def _get_eda() -> dict:
    global _eda_cache
    if _eda_cache is None:
        _eda_cache = run_eda(_get_preprocessed(), OUTPUT_DIR)
    return _eda_cache


def _build_context() -> RunContext:
    df = _get_preprocessed()
    y = df["AverageTemperature"]
    return RunContext(
        train=y[:"2009"],
        test=y["2010":],
        y=y,
        output_dir=OUTPUT_DIR,
        epochs=LSTM_EPOCHS,
        retrain=LSTM_RETRAIN,
        model_path_tf=MODEL_PATH_TF,
        model_path_pytorch=MODEL_PATH_PYTORCH,
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/models")
def list_models() -> list[dict]:
    models = []
    for key, spec in MODEL_REGISTRY.items():
        stored = load_result(OUTPUT_DIR, key)
        job = latest_job_for_model(key)
        status = job.status if job else ("completed" if stored else "idle")
        models.append(
            {
                "key": key,
                "display_name": spec.display_name,
                "framework": spec.framework,
                "hyperparams": spec.hyperparams,
                "has_result": stored is not None,
                "metrics": stored.get("metrics") if stored else None,
                "status": status,
            }
        )
    return models


@app.post("/api/models/{model_key}/run")
def run_model(model_key: str) -> dict:
    try:
        spec = get_model_spec(model_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ctx = _build_context()

    def _run() -> dict:
        result = spec.run(ctx)
        save_result(OUTPUT_DIR, model_key, result)
        return result

    job = submit_job(model_key, _run)
    return {"job_id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}")
    return {
        "id": job.id,
        "model_key": job.model_key,
        "status": job.status,
        "result": job.result,
        "error": job.error,
    }


@app.get("/api/models/{model_key}/result")
def model_result(model_key: str) -> dict:
    if model_key not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown model_key '{model_key}'")
    stored = load_result(OUTPUT_DIR, model_key)
    if stored is None:
        raise HTTPException(status_code=404, detail="This model has not been run yet.")
    return stored


@app.get("/api/comparison")
def comparison() -> dict:
    results = load_all_results(OUTPUT_DIR)
    models = []
    for key, spec in MODEL_REGISTRY.items():
        if key in results:
            models.append(
                {
                    "key": key,
                    "display_name": spec.display_name,
                    "framework": spec.framework,
                    "forecast": results[key].get("forecast", []),
                    "metrics": results[key].get("metrics"),
                }
            )
    return {"models": models}


@app.get("/api/temperature/observed")
def observed_temperature() -> list[dict]:
    return _get_eda()["observed"]


@app.get("/api/eda/moving-averages", response_model=MovingAveragesResponse)
def moving_averages() -> dict:
    return _get_eda()["moving_averages"]


@app.get("/api/eda/seasonal-decomposition", response_model=SeasonalDecompositionResponse)
def seasonal_decomposition() -> dict:
    return _get_eda()["seasonal_decomposition"]


@app.get("/api/eda/stationarity", response_model=StationarityResponse)
def stationarity() -> dict:
    return _get_eda()["stationarity"]
