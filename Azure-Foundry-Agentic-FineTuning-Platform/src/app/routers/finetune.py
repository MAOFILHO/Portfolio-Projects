"""Workflow 2 endpoints — supervised fine-tuning."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.mcp_clients.registry import call_tool
from app.schemas.training import validate_jsonl_text

router = APIRouter(prefix="/finetune", tags=["workflow2-finetune"])

#: Guard against someone uploading a huge file into a demo. The lab's own
#: training file is 8.4 KB.
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("/datasets")
async def list_datasets() -> dict[str, Any]:
    """The full selectable dataset catalog — the lab's own travel dataset plus
    any additional datasets converted into Azure's fine-tuning format."""
    return await call_tool("list_datasets")


@router.get("/validate")
async def validate_bundled_dataset(
    path: str = "travel-finetune-hotel.jsonl", dataset_id: str = ""
) -> dict[str, Any]:
    args: dict[str, Any] = {"dataset_id": dataset_id} if dataset_id else {"path": path}
    result = await call_tool("validate_jsonl", args)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/validate/upload")
async def validate_uploaded_dataset(file: UploadFile = File(...)) -> dict[str, Any]:
    """Validate a user-supplied JSONL file.

    Schema violations are returned as data with HTTP 200 — the UI renders them
    as a demonstrated feature rather than an opaque error.
    """
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file exceeds {_MAX_UPLOAD_BYTES // 1024 // 1024} MB limit",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="file must be UTF-8 encoded JSONL") from exc

    report = validate_jsonl_text(text, file.filename or "uploaded.jsonl")
    payload = report.model_dump()
    payload["is_valid"] = report.is_valid
    payload["has_consistent_system_prompt"] = report.has_consistent_system_prompt
    return payload


@router.post("/estimate")
async def estimate_cost(
    billed_tokens: int = Query(0, ge=0),
    epochs: int = Query(0, ge=0, le=50),
    training_type: str = "",
    dataset_id: str = "",
) -> dict[str, Any]:
    # billed_tokens defaults to 0 (not 16000) so a dataset_id can drive the
    # per-dataset heuristic estimate instead of always falling back to the
    # travel dataset's recorded figure — see estimate_training_cost's own
    # dataset_id handling for the reasoning.
    return await call_tool(
        "estimate_training_cost",
        {
            "billed_tokens": billed_tokens,
            "epochs": epochs,
            "training_type": training_type,
            "dataset_id": dataset_id,
        },
    )


@router.post("/jobs")
async def create_job(
    base_model: str = "",
    suffix: str = "",
    n_epochs: int = Query(0, ge=0, le=50),
    dataset_id: str = "",
) -> dict[str, Any]:
    upload = await call_tool("upload_training_file", {"dataset_id": dataset_id})
    if "error" in upload:
        raise HTTPException(status_code=422, detail=upload)
    return await call_tool(
        "create_sft_job",
        {
            "training_file_id": upload["file_id"],
            "base_model": base_model,
            "suffix": suffix,
            "n_epochs": n_epochs,
        },
    )


@router.get("/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, Any]:
    return await call_tool("get_job_status", {"job_id": job_id})


@router.get("/jobs/{job_id}/logs")
async def job_logs(
    job_id: str,
    limit: int = Query(20, ge=1, le=500),
    metrics_only: bool = False,
) -> dict[str, Any]:
    return await call_tool(
        "get_job_logs", {"job_id": job_id, "limit": limit, "metrics_only": metrics_only}
    )


@router.get("/jobs/{job_id}/checkpoints")
async def job_checkpoints(job_id: str) -> dict[str, Any]:
    result = await call_tool("list_checkpoints", {"job_id": job_id})
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.post("/deploy")
async def deploy(model_name: str = "", deployment_type: str = "") -> dict[str, Any]:
    return await call_tool(
        "deploy_finetuned_model",
        {"model_name": model_name, "deployment_type": deployment_type},
    )
