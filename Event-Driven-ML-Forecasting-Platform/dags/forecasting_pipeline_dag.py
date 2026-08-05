"""Airflow orchestration for the Bombay temperature forecasting pipeline.

Every task here is a thin wrapper around functions that already exist and are
already tested elsewhere in this project -- src/data_loading.py,
src/preprocessing.py, src/eda.py, src/model_registry.py, src/results_store.py
-- the same functions backend/run_pipeline.py and backend/api/main.py's
_build_context() already call. This DAG reimplements no model, ETL, or
result-shape logic; it only sequences and observes the existing pipeline.

Pipeline shape:

    validate_raw_data -> run_pyspark_etl -> train_forecasting_models (5 parallel
    tasks, one per MODEL_REGISTRY entry) -> export_dashboard_results

Each training task independently recomputes load_bombay_data() + preprocess()
rather than passing the preprocessed DataFrame through XCom -- this matches
how every other entry point in this project (run_pipeline.py, api/main.py,
the test suite) already recomputes preprocessing fresh each time, it's fast
(a few seconds via Spark), and it avoids serializing a pandas DataFrame with
a DatetimeIndex through Airflow's metadata DB (XCom is for small values, not
DataFrames). Each task instead pushes its spec.run(ctx) result dict via XCom
-- small (forecast arrays + metrics), well within XCom's size expectations.

This is a manually-triggered demo pipeline (schedule=None), not a recurring
production job -- consistent with the rest of this project's "on-demand, not
automatic" philosophy (the dashboard's own model runs are triggered by a
button, not a timer).
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup

# /opt/backend is where backend/src, backend/data, backend/models, and
# backend/outputs are bind-mounted (see airflow/docker-compose.yml) -- same
# sys.path convention every other entry point in this project uses
# (run_pipeline.py, api/main.py, tests/test_smoke.py all do this identically).
BACKEND_DIR = os.getenv("BACKEND_DIR", "/opt/backend")
sys.path.insert(0, BACKEND_DIR)

logger = logging.getLogger(__name__)

DATA_PATH = os.path.join(BACKEND_DIR, "data", "GlobalLandTemperaturesByMajorCity.csv")
MODEL_PATH_TF = os.path.join(BACKEND_DIR, "models", "TemperatureForecastingModel.keras")
MODEL_PATH_PYTORCH = os.path.join(BACKEND_DIR, "models", "TemperatureForecastingModel_pytorch.pt")
OUTPUT_DIR = os.path.join(BACKEND_DIR, "outputs")
LSTM_EPOCHS = int(os.getenv("LSTM_EPOCHS", "10"))
LSTM_RETRAIN = os.getenv("LSTM_RETRAIN", "false").strip().lower() in ("1", "true", "yes", "on")


def _preprocessed_dataframe():
    """load_bombay_data() + preprocess() -- the exact Phase 1 Spark ETL path."""
    from pathlib import Path

    from src.data_loading import load_bombay_data
    from src.preprocessing import preprocess

    data = load_bombay_data(Path(DATA_PATH))
    return preprocess(data)


def _build_context():
    """Same RunContext construction as run_pipeline.py / api/main.py's _build_context()."""
    from pathlib import Path

    from src.model_registry import RunContext

    data = _preprocessed_dataframe()
    y = data["AverageTemperature"]
    return RunContext(
        train=y[:"2009"],
        test=y["2010":],
        y=y,
        output_dir=Path(OUTPUT_DIR),
        epochs=LSTM_EPOCHS,
        retrain=LSTM_RETRAIN,
        model_path_tf=Path(MODEL_PATH_TF),
        model_path_pytorch=Path(MODEL_PATH_PYTORCH),
    )


def validate_raw_data(**_context) -> None:
    """load_raw_data() already calls validate_raw_data() internally and raises
    DataValidationError on failure -- this task just fails loudly if it does,
    same fail-fast contract as everywhere else in this project."""
    from pathlib import Path

    from src.data_loading import load_raw_data

    raw = load_raw_data(Path(DATA_PATH))
    logger.info("Raw dataset validated (%d rows).", raw.count())


def run_pyspark_etl(**_context) -> None:
    """The Phase 1 Spark ETL path, plus EDA -- writes eda.json, same as run_pipeline.py."""
    import json
    from pathlib import Path

    from src.eda import run_eda

    output_dir = Path(OUTPUT_DIR)
    data = _preprocessed_dataframe()
    output_dir.mkdir(parents=True, exist_ok=True)
    # run_eda() does output_dir / "..." internally, so it needs a real Path,
    # not the plain string OUTPUT_DIR -- same as run_pipeline.py/api/main.py
    # already pass it.
    eda_results = run_eda(data, output_dir)
    with open(output_dir / "eda.json", "w") as f:
        json.dump(eda_results, f, indent=2)
    logger.info("EDA complete, preprocessed shape=%s", data.shape)


def _train_model(model_key: str, ti, **_context) -> None:
    from src.model_registry import get_model_spec

    spec = get_model_spec(model_key)
    ctx = _build_context()
    logger.info("Running %s (%s)...", spec.display_name, model_key)
    result = spec.run(ctx)
    ti.xcom_push(key=model_key, value=result)
    logger.info("%s complete.", spec.display_name)


def export_dashboard_results(ti, **_context) -> None:
    """Pulls each training task's XCom result and writes outputs/results/{key}.json
    -- the literal 'Writes JSON metrics to backend/outputs/results/' step. Since
    outputs/ is bind-mounted from the host, these are the same files the FastAPI
    dashboard already reads via results_store.load_result()."""
    from pathlib import Path

    from src.model_registry import MODEL_REGISTRY
    from src.results_store import save_result

    output_dir = Path(OUTPUT_DIR)
    written = []
    for model_key in MODEL_REGISTRY:
        result = ti.xcom_pull(task_ids=f"train_forecasting_models.train_{model_key}", key=model_key)
        if result is None:
            raise RuntimeError(f"No XCom result found for '{model_key}' -- its training task may have failed.")
        save_result(output_dir, model_key, result)
        written.append(model_key)
    logger.info("Exported results for: %s", written)


with DAG(
    dag_id="forecasting_pipeline",
    description="Validate -> Spark ETL -> train 5 forecasting models -> export dashboard results",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["forecasting", "spark", "pyspark"],
) as dag:
    validate_task = PythonOperator(task_id="validate_raw_data", python_callable=validate_raw_data)

    etl_task = PythonOperator(task_id="run_pyspark_etl", python_callable=run_pyspark_etl)

    with TaskGroup(group_id="train_forecasting_models") as train_group:
        # One task per MODEL_REGISTRY entry -- 5, not 4, since SARIMAX has two
        # independent configurations. Imported at DAG-parse time only to build
        # the task list; the actual run() call happens inside _train_model at
        # task-execution time.
        sys.path.insert(0, BACKEND_DIR)
        from src.model_registry import MODEL_REGISTRY  # noqa: E402

        for key in MODEL_REGISTRY:
            PythonOperator(
                task_id=f"train_{key}",
                python_callable=_train_model,
                op_kwargs={"model_key": key},
            )

    export_task = PythonOperator(task_id="export_dashboard_results", python_callable=export_dashboard_results)

    validate_task >> etl_task >> train_group >> export_task
