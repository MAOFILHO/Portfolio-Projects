"""Azure ML online endpoint scoring script.

This file is intentionally named `main.py` because Azure ML's inference server
looks for that entry script by default in many deployment flows.
"""

import json
import logging
import os
from pathlib import Path

import mlflow.pytorch
import torch

logger = logging.getLogger(__name__)
model = None


def _resolve_model_path() -> str:
    """Resolve model directory that contains MLmodel metadata."""
    model_root = Path(os.environ.get("AZUREML_MODEL_DIR", "/var/azureml-app/azureml-models"))

    # For registered models, AZUREML_MODEL_DIR usually points directly at
    # <model_name>/<version>. Prefer the direct path if it is an MLflow model.
    if (model_root / "MLmodel").is_file():
        return str(model_root)

    # Fallback: search one level down (e.g. artifact subfolder).
    for path in model_root.rglob("MLmodel"):
        return str(path.parent)

    raise FileNotFoundError(f"Could not find MLmodel under {model_root}")


def init():
    """Load model once at startup."""
    global model
    model_path = _resolve_model_path()
    logger.info("Loading model from %s", model_path)
    model = mlflow.pytorch.load_model(model_path)
    model.eval()


def run(raw_data):
    """Score inference requests."""
    try:
        payload = raw_data
        if isinstance(raw_data, bytes):
            payload = raw_data.decode("utf-8")
        if isinstance(payload, str):
            payload = json.loads(payload)

        inputs = payload.get("input") or payload.get("instances") or payload.get("data") or payload
        if isinstance(inputs, dict) and "input" in inputs:
            inputs = inputs["input"]
        if not isinstance(inputs, list):
            inputs = [inputs]

        tensor = torch.tensor(inputs, dtype=torch.float32)
        if torch.cuda.is_available():
            tensor = tensor.cuda()
            model_to_use = model.cuda()
        else:
            model_to_use = model

        with torch.no_grad():
            predictions = model_to_use(tensor)
            if isinstance(predictions, torch.Tensor):
                predictions = predictions.cpu().numpy().tolist()

        return {"predictions": predictions}
    except Exception as exc:
        logger.exception("Scoring failed: %s", exc)
        return {"error": str(exc)}
