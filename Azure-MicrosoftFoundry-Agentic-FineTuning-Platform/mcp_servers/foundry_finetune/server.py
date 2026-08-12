"""MCP server: supervised fine-tuning lifecycle.

Automates §8–§10 of *Fine-tune a language model* — upload, validate, submit,
monitor, and deploy.

In mock mode the job replays the recorded 100-step run from the guide; in live
mode it drives the real Azure fine-tuning API. Tool schemas are identical either
way, so callers never branch on mode.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

from app.config import DATA_DIR, get_settings
from app.schemas.dataset import DATASET_REGISTRY, dataset_relative_path, get_dataset
from app.schemas.finetune import FineTuneJobConfig, JobStatus, TrainingCostEstimate
from app.schemas.training import validate_jsonl_text
from app.services import fixtures

server = MCPServer(
    name="foundry-finetune",
    version="0.1.0",
    instructions=(
        "Manage Azure AI Foundry supervised fine-tuning: validate a JSONL "
        "training file, submit an SFT job, monitor progress, and deploy the "
        "resulting model."
    ),
)

#: Documented Azure rate for gpt-4.1 global SFT training, per 1M tokens.
#: Developer-tier training is half this — see COSTS.md.
_TRAINING_PRICE_PER_1M_USD = 2.0

#: In-process cache of the most recently created live job id, so a later
#: get_job_status({}) call (e.g. from the comparison agent) in the same
#: `run-all` process can resolve "the job we just submitted" without the
#: caller needing to thread an id through. Mock mode doesn't need this — its
#: fixture always returns the same recorded job regardless of input. This is
#: intentionally process-local, not persisted; a live SFT job takes ~60 min
#: to reach `succeeded`, so a single `run-all` pass will typically observe it
#: still `running`/`queued`, with no deployment yet — Workflow 3 must be
#: re-run later, once the job (and its auto-deploy) has actually completed.
_last_live_job_id: str = ""

#: In-process cache of the most recently created live deployment. Azure's
#: fine-tuning job object carries no deployment_name/deployment_status field
#: of its own (a deployment is a separate ARM resource) — this bridges that
#: gap the same way _last_live_job_id bridges job continuity, so a later
#: get_job_status({}) call (e.g. from the comparison agent) can resolve "the
#: deployment we just created" without the caller threading a name through.
_last_live_deployment: dict[str, str] = {}


def _resolve(path: str) -> Path:
    """Resolve a training-file path, defaulting to the bundled dataset."""
    candidate = Path(path)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (Path.cwd(), DATA_DIR, DATA_DIR.parent):
        resolved = base / path
        if resolved.exists():
            return resolved
    return DATA_DIR / "travel-finetune-hotel.jsonl"


@server.tool(
    description=(
        "List every selectable fine-tuning dataset (the lab's own "
        "travel-finetune-hotel.jsonl plus any additional datasets converted into "
        "Azure's fine-tuning format). Pass an id from this list as `dataset_id` "
        "to validate_jsonl / upload_training_file / estimate_training_cost."
    )
)
async def list_datasets() -> dict[str, Any]:
    return {
        "count": len(DATASET_REGISTRY),
        "datasets": [d.model_dump() for d in DATASET_REGISTRY],
    }


@server.tool(
    description=(
        "Validate a JSONL training file against the supervised fine-tuning schema. "
        "Returns per-line errors rather than failing on the first bad row. Pass "
        "`dataset_id` (from list_datasets) to validate a specific catalog dataset "
        "instead of a raw `path`."
    )
)
async def validate_jsonl(
    path: str = "travel-finetune-hotel.jsonl", dataset_id: str = ""
) -> dict[str, Any]:
    if dataset_id:
        try:
            path = dataset_relative_path(dataset_id)
        except KeyError as exc:
            return {"error": str(exc)}
    target = _resolve(path)
    if not target.exists():
        return {"error": f"file not found: {target}"}
    report = validate_jsonl_text(target.read_text(encoding="utf-8"), target.name)
    payload = report.model_dump()
    payload["is_valid"] = report.is_valid
    payload["has_consistent_system_prompt"] = report.has_consistent_system_prompt
    return payload


@server.tool(
    description=(
        "Upload a training file for fine-tuning. Returns a file id. Pass "
        "`dataset_id` (from list_datasets) to upload a specific catalog dataset "
        "instead of a raw `path`."
    )
)
async def upload_training_file(
    path: str = "travel-finetune-hotel.jsonl", dataset_id: str = ""
) -> dict[str, Any]:
    settings = get_settings()
    if dataset_id:
        try:
            path = dataset_relative_path(dataset_id)
        except KeyError as exc:
            return {"error": str(exc)}
    target = _resolve(path)
    if not target.exists():
        return {"error": f"file not found: {target}"}

    report = validate_jsonl_text(target.read_text(encoding="utf-8"), target.name)
    if not report.is_valid:
        return {
            "error": "refusing to upload an invalid training file",
            "errors": [e.model_dump() for e in report.errors],
        }

    if settings.is_mock:
        return {
            "file_id": f"file-mock-{target.stem}",
            "file_name": target.name,
            "size_bytes": report.size_bytes,
            "rows": report.valid_rows,
            "mode": "mock",
        }

    from app.services import azure_foundry

    return {
        "file_id": await asyncio.to_thread(azure_foundry.upload_training_file, str(target)),
        "file_name": target.name,
        "size_bytes": report.size_bytes,
        "rows": report.valid_rows,
        "mode": "live",
    }


@server.tool(
    description=(
        "Submit a supervised fine-tuning job. Hyperparameters are pinned "
        "explicitly for reproducibility rather than left at service defaults."
    )
)
async def create_sft_job(
    training_file_id: str = "file-mock-travel-finetune-hotel",
    base_model: str = "",
    suffix: str = "",
    n_epochs: int = 0,
) -> dict[str, Any]:
    settings = get_settings()
    config = FineTuneJobConfig(
        base_model=base_model or settings.model_baseline,
        base_model_version=settings.model_baseline_version,
        training_type=settings.ft_training_type,
        suffix=suffix or settings.ft_suffix,
        deployment_type=settings.ft_deployment_type,
    )
    if n_epochs:
        config.hyperparameters.n_epochs = n_epochs

    if settings.is_mock:
        job = fixtures.get_finetune_job()
        job.config = config
        job.status = JobStatus.QUEUED
        job.logs = []
        return {
            "job_id": job.id,
            "status": job.status.value,
            "config": config.model_dump(),
            "mode": "mock",
            "note": "Live runs take 60 minutes or longer; mock replays the recorded run.",
        }

    from app.services import azure_foundry

    job = await asyncio.to_thread(azure_foundry.create_sft_job, config, training_file_id)
    global _last_live_job_id
    _last_live_job_id = job.id
    return {
        "job_id": job.id,
        "status": job.status.value,
        "config": config.model_dump(),
        "mode": "live",
    }


@server.tool(description="Get the current status, metrics, and progress of a fine-tuning job.")
async def get_job_status(job_id: str = "") -> dict[str, Any]:
    settings = get_settings()
    if settings.is_mock:
        job = fixtures.get_finetune_job()
        return {
            "job_id": job.id,
            "status": job.status.value,
            "progress_pct": job.progress_pct,
            "duration_seconds": job.duration_seconds,
            "metrics": job.metrics.model_dump(),
            "fine_tuned_model": job.fine_tuned_model,
            "deployment_name": job.deployment_name,
            "deployment_status": job.deployment_status,
            "is_terminal": job.status.is_terminal,
        }

    from app.services import azure_foundry

    job_id = job_id or _last_live_job_id
    if not job_id:
        # No in-memory record of a job in *this* process — normal after a
        # restart, not evidence nothing was ever deployed. Check Azure
        # directly for an existing fine-tuned deployment before giving up;
        # otherwise a perfectly good, already-paid-for deployment becomes
        # invisible to Workflow 3 just because the backend process restarted.
        deployments = await asyncio.to_thread(azure_foundry.list_finetuned_deployments)
        ready = [d for d in deployments if d["provisioning_state"] == "Succeeded"]
        if not ready:
            return {"error": "no job_id given and no job has been created yet this run"}
        top = ready[0]
        return {
            "job_id": None,
            "status": "succeeded",
            "progress_pct": 100.0,
            "metrics": {
                "final_train_loss": None,
                "final_train_mean_token_accuracy": None,
                "trained_tokens": None,
                "total_steps": None,
            },
            "fine_tuned_model": top["model_name"],
            "deployment_name": top["deployment_name"],
            "deployment_status": top["provisioning_state"],
            "is_terminal": True,
            "note": (
                "resolved from an existing Azure deployment, not this process's "
                "job history (no job_id given and none cached — likely a server "
                "restart since this job completed)"
            ),
        }
    job = await asyncio.to_thread(azure_foundry.get_job_status, job_id)
    return {
        "job_id": job.id,
        "status": job.status.value,
        "progress_pct": job.progress_pct,
        "metrics": job.metrics.model_dump(),
        "fine_tuned_model": job.fine_tuned_model,
        # None until the job reaches `succeeded` and auto-deploy has run —
        # a live SFT job takes ~60 min, so this will typically still be None
        # within the same `run-all` pass that submitted it.
        "deployment_name": job.deployment_name or _last_live_deployment.get("name"),
        "deployment_status": job.deployment_status or _last_live_deployment.get("status"),
        "is_terminal": job.status.is_terminal,
    }


@server.tool(description="Get job logs, including per-step training loss.")
async def get_job_logs(
    job_id: str = "", limit: int = 20, metrics_only: bool = False
) -> dict[str, Any]:
    settings = get_settings()
    if settings.is_mock:
        entries = fixtures.get_finetune_job().logs
    else:
        from app.services import azure_foundry

        entries = await asyncio.to_thread(azure_foundry.get_job_logs, job_id, max(limit, 50))

    if metrics_only:
        entries = [e for e in entries if e.type == "metrics"]
    tail = entries[-limit:] if limit else entries
    return {
        "job_id": job_id or "ftjob-mock",
        "count": len(tail),
        "total_available": len(entries),
        "logs": [e.model_dump(mode="json") for e in tail],
    }


@server.tool(description="List the checkpoints written during training.")
async def list_checkpoints(job_id: str = "") -> dict[str, Any]:
    settings = get_settings()
    if not settings.is_mock:
        return {"error": "checkpoint listing is only recorded in mock mode"}
    job = fixtures.get_finetune_job()
    return {
        "job_id": job.id,
        "checkpoints": [c.model_dump(mode="json") for c in job.checkpoints],
    }


@server.tool(
    description=(
        "Deploy a fine-tuned model. Defaults to Developer tier, which has no "
        "hourly hosting fee and is removed automatically after 24 hours."
    )
)
async def deploy_finetuned_model(
    job_id: str = "", deployment_name: str = "", deployment_type: str = ""
) -> dict[str, Any]:
    settings = get_settings()
    sku = deployment_type or settings.ft_deployment_type

    warning = None
    if sku in {"Standard", "GlobalStandard"}:
        warning = (
            f"{sku} deployments bill $1.70/hour (~$1,224/month) even when idle. "
            "Developer tier costs $0/hour."
        )

    if settings.is_mock:
        job = fixtures.get_finetune_job()
        return {
            "deployment_name": deployment_name or job.deployment_name,
            "deployment_type": sku,
            "status": "Succeeded",
            "hourly_cost_usd": 0.0 if sku == "Developer" else 1.70,
            "auto_removed_after_hours": 24 if sku == "Developer" else None,
            "warning": warning,
            "mode": "mock",
        }

    from app.services import azure_foundry

    job_id = job_id or _last_live_job_id
    if not job_id:
        return {"error": "no job_id given and no job has been created yet this run"}
    job = await asyncio.to_thread(azure_foundry.get_job_status, job_id)
    if not job.fine_tuned_model:
        return {
            "error": (
                f"job {job_id} has status {job.status.value}, not succeeded yet — "
                "nothing to deploy. Check get_job_status first."
            )
        }

    name = deployment_name or f"{settings.ft_suffix}-{job_id[-8:]}"
    result = await asyncio.to_thread(azure_foundry.deploy_model, name, job.fine_tuned_model, sku)
    status = result.get("properties", {}).get("provisioningState", "Creating")

    global _last_live_deployment
    _last_live_deployment = {"name": name, "status": status}

    return {
        "deployment_name": name,
        "deployment_type": sku,
        "status": status,
        "fine_tuned_model": job.fine_tuned_model,
        "hourly_cost_usd": 0.0 if sku == "Developer" else 1.70,
        "auto_removed_after_hours": 24 if sku == "Developer" else None,
        "warning": warning,
        "mode": "live",
    }


@server.tool(
    description=(
        "Estimate supervised fine-tuning training cost using Microsoft's formula: "
        "tokens-per-epoch x epochs x price-per-token. Pass billed_tokens instead "
        "when quoting the job log's already-multiplied 'Training tokens billed' "
        "figure, which would otherwise double-count the epochs."
    )
)
async def estimate_training_cost(
    training_tokens: int = 0,
    billed_tokens: int = 0,
    epochs: int = 0,
    training_type: str = "",
    dataset_id: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    epoch_count = epochs or settings.ft_n_epochs
    kind = training_type or settings.ft_training_type
    note = (
        "Developer-tier training is 50% cheaper than global. The lab's own "
        "$0.032 figure corresponds to global-tier pricing on 16,000 billed tokens."
    )

    no_tokens_given = not (training_tokens or billed_tokens)
    if dataset_id and dataset_id != "travel-finetune-hotel" and no_tokens_given:
        # Any dataset other than the lab's own has no recorded Azure job to
        # quote a real billed-token count from, so estimate per-epoch tokens
        # with the same char/4 heuristic OpenAI's own docs use for rough
        # sizing, rather than reusing the travel job's unrelated 16,000 figure.
        target = _resolve(dataset_relative_path(dataset_id))
        text = target.read_text(encoding="utf-8")
        training_tokens = max(1, len(text) // 4)
        note = (
            f"Heuristic estimate (~4 chars/token) over {get_dataset(dataset_id).label}'s "
            "training file, since only the lab's travel dataset has a real recorded "
            "Azure training run to quote an exact billed-token count from."
        )

    if billed_tokens or not training_tokens:
        # Default to the lab's observed billed total of 16,000 tokens.
        estimate = TrainingCostEstimate.from_billed_tokens(
            billed_tokens or 16000, epoch_count, _TRAINING_PRICE_PER_1M_USD, kind
        )
    else:
        estimate = TrainingCostEstimate(
            training_tokens=training_tokens,
            epochs=epoch_count,
            price_per_1m_tokens_usd=_TRAINING_PRICE_PER_1M_USD,
            training_type=kind,
        )

    return {**estimate.model_dump(), "note": note}


if __name__ == "__main__":
    server.run(transport="stdio")
