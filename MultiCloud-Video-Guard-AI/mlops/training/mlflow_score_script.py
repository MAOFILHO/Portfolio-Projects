# Custom MLflow score script for Azure ML inference.
# Avoids "from azureml.ai.monitoring import Collector" so the container can start
# without the azureml-ai-monitoring package. Compatible with Azure ML inference HTTP server.

import os
import json
import logging
import torch
import mlflow.pytorch

logger = logging.getLogger(__name__)

def init():
    """Load the model once at startup. No azureml.ai imports."""
    global model
    model_dir = os.environ.get("AZUREML_MODEL_DIR", "/var/azureml-app/azureml-models")
    model_path = model_dir
    logger.info("Loading model from %s", model_path)
    try:
        model = mlflow.pytorch.load_model(model_path)
    except Exception as e:
        logger.exception("Failed to load model: %s", e)
        raise
    model.eval()


def run(raw_data, request_headers=None):
    """Score request. raw_data can be JSON string or bytes. Returns JSON string or (body, status_code)."""
    global model
    try:
        if isinstance(raw_data, bytes):
            raw_data = raw_data.decode("utf-8")
        if isinstance(raw_data, str):
            data = json.loads(raw_data)
        else:
            data = raw_data
        inputs = data.get("input") or data.get("instances") or data.get("data") or data
        if isinstance(inputs, dict) and "input" in inputs:
            inputs = inputs["input"]
        if not isinstance(inputs, list):
            inputs = [inputs]
        with torch.no_grad():
            tensor = torch.tensor(inputs, dtype=torch.float32)
            if torch.cuda.is_available():
                tensor = tensor.cuda()
                model_cuda = model.cuda()
            else:
                model_cuda = model
            out = model_cuda(tensor)
            if isinstance(out, torch.Tensor):
                out = out.cpu().numpy().tolist()
        return json.dumps({"predictions": out})
    except Exception as e:
        logger.exception("Scoring failed: %s", e)
        return (json.dumps({"error": str(e)}), 500)
